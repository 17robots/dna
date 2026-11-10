#!/usr/bin/env python3
"""Run the actual Windows grammar/npm installer and raw managed-server transport.

The grammar archive uses the repository's HTTPS URL and checksum. npm installs a
locally packed, dependency-free package through the real Node/npm programs; only
the pinned pyright package argument is substituted by the test-scoped wrapper.
"""
import contextlib
import ctypes as c
import json
import os
from pathlib import Path
import queue
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


class OwnedChild:
    """Assign a suspended child to a kill-on-close Job before it can spawn."""
    class BasicLimits(c.Structure):
        _fields_ = [('process_time', c.c_int64), ('job_time', c.c_int64),
                    ('flags', c.c_uint32), ('minimum', c.c_size_t),
                    ('maximum', c.c_size_t), ('processes', c.c_uint32),
                    ('affinity', c.c_size_t), ('priority', c.c_uint32),
                    ('scheduling', c.c_uint32)]

    def __init__(self, command, cwd, env):
        self.command = [str(part) for part in command]
        self.cwd, self.env = cwd, env
        self.job = None
        self.process = None
        self.threads = []
        self.chunks = queue.Queue()
        self.stdout = bytearray()
        self.stderr = bytearray()
        self.pending = bytearray()

    def __enter__(self):
        kernel = self.kernel = c.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [c.c_void_p, c.c_wchar_p]
        kernel.CreateJobObjectW.restype = c.c_void_p
        kernel.SetInformationJobObject.argtypes = [c.c_void_p, c.c_int, c.c_void_p, c.c_uint32]
        kernel.AssignProcessToJobObject.argtypes = [c.c_void_p, c.c_void_p]
        kernel.TerminateJobObject.argtypes = [c.c_void_p, c.c_uint32]
        kernel.CloseHandle.argtypes = [c.c_void_p]
        class Limits(c.Structure):
            _fields_ = [('basic', self.BasicLimits), ('io', c.c_uint64 * 6),
                        ('process_memory', c.c_size_t), ('job_memory', c.c_size_t),
                        ('peak_process', c.c_size_t), ('peak_job', c.c_size_t)]
        limits = Limits()
        limits.basic.flags = 0x2000
        self.job = kernel.CreateJobObjectW(None, None)
        if not self.job:
            raise c.WinError(c.get_last_error())
        try:
            if not kernel.SetInformationJobObject(self.job, 9, c.byref(limits), c.sizeof(limits)):
                raise c.WinError(c.get_last_error())
            self.process = subprocess.Popen(self.command, cwd=self.cwd, env=self.env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=0x4 | 0x200)
            if not kernel.AssignProcessToJobObject(self.job, c.c_void_p(int(self.process._handle))):
                raise c.WinError(c.get_last_error())
            native = c.WinDLL('ntdll')
            native.NtResumeProcess.argtypes = [c.c_void_p]
            native.NtResumeProcess.restype = c.c_int32
            status = native.NtResumeProcess(c.c_void_p(int(self.process._handle)))
            if status < 0:
                raise AssertionError(('resume owned installer', status))
            for stream, output, chunks in ((self.process.stdout, self.stdout, self.chunks),
                                           (self.process.stderr, self.stderr, None)):
                thread = threading.Thread(target=self._read, args=(stream, output, chunks))
                thread.start()
                self.threads.append(thread)
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    @staticmethod
    def _read(stream, output, chunks):
        try:
            while True:
                data = os.read(stream.fileno(), 65536)
                if not data:
                    break
                output.extend(data)
                if len(output) > 8 * 1024 * 1024:
                    del output[:-8 * 1024 * 1024]
                if chunks is not None:
                    chunks.put(data)
        finally:
            if chunks is not None:
                chunks.put(None)

    def complete(self, timeout=180):
        self.process.wait(timeout=timeout)
        self._join_readers()
        return subprocess.CompletedProcess(self.command, self.process.returncode,
            bytes(self.stdout), bytes(self.stderr))

    def _join_readers(self):
        for thread in self.threads:
            thread.join(timeout=5)
            assert not thread.is_alive(), 'owned installer stdio reader did not retire'

    def send(self, message):
        payload = json.dumps(message, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.process.stdin.write(b'Content-Length: ' + str(len(payload)).encode('ascii') + b'\r\n\r\n' + payload)
        self.process.stdin.flush()

    def response(self, expected_id, timeout=5):
        deadline = time.monotonic() + timeout
        while True:
            separator = self.pending.find(b'\r\n\r\n')
            if separator >= 0:
                header = bytes(self.pending[:separator])
                match = re.search(rb'(?:^|\r\n)Content-Length: ([0-9]+)(?:\r\n|$)', header, re.I)
                assert match, ('managed server wrote unframed stdout', header)
                length = int(match[1])
                assert length <= 1024 * 1024, 'managed fixture response is unbounded'
                end = separator + 4 + length
                if len(self.pending) >= end:
                    message = json.loads(bytes(self.pending[separator + 4:end]))
                    del self.pending[:end]
                    if message.get('id') == expected_id:
                        assert 'error' not in message, message
                        return message
                    continue
            remaining = deadline - time.monotonic()
            assert remaining > 0, ('managed stdio response deadline', expected_id, bytes(self.stderr[-4000:]))
            try:
                chunk = self.chunks.get(timeout=remaining)
            except queue.Empty:
                raise AssertionError(('managed stdio response deadline', expected_id, bytes(self.stderr[-4000:]))) from None
            assert chunk is not None, ('managed server reached EOF before response', expected_id,
                                       self.process.poll(), bytes(self.stdout[-1000:]), bytes(self.stderr[-4000:]))
            self.pending.extend(chunk)

    def __exit__(self, *unused):
        if self.job:
            self.kernel.TerminateJobObject(self.job, 1)
        if self.process:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=5)
            self._join_readers()
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                if stream:
                    stream.close()
            self.process._handle.Close()
        if self.job:
            self.kernel.CloseHandle(self.job)
            self.job = None


def cli(helper, arguments, work, env, success=True, timeout=180):
    with OwnedChild([helper, *arguments], work, env) as child:
        child.process.stdin.close()
        result = child.complete(timeout)
    diagnostic = (arguments, result.returncode, result.stdout[-6000:].decode('utf-8', 'replace'),
                  result.stderr[-6000:].decode('utf-8', 'replace'))
    assert (result.returncode == 0) == success, diagnostic
    return result.stdout.decode('utf-8', 'replace')


def bind_library(library):
    library.dna_language_resolve_directory.argtypes = [c.c_char_p, c.c_void_p, c.c_size_t]
    library.dna_language_resolve_directory.restype = c.c_ssize_t
    library.dna_syntax_open_named.argtypes = [c.c_char_p, c.c_char_p]
    library.dna_syntax_open_named.restype = c.c_void_p
    library.dna_syntax_update.argtypes = [c.c_void_p, c.c_char_p, c.c_uint32, c.c_uint64]
    library.dna_syntax_colors.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32, c.c_uint64]
    library.dna_syntax_close.argtypes = [c.c_void_p]


def active_directory(library, pointer):
    output = c.create_string_buffer(4096)
    size = library.dna_language_resolve_directory(str(pointer).encode('utf-8'), output, len(output))
    assert 0 < size < len(output), ('active package resolution', str(pointer), size)
    result = Path(output.value.decode('utf-8'))
    assert result.is_dir() and not result.is_symlink()
    return result


def prove_parser(library, worker, revision):
    code = b'int main(void) { return 42; }\n'
    library.dna_syntax_update(worker, code, len(code), revision)
    colors = c.create_string_buffer(len(code))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if library.dna_syntax_colors(worker, colors, len(code), revision) == 1:
            assert any(colors.raw), 'real compiled C grammar/query produced no highlights'
            return
        time.sleep(.005)
    raise AssertionError('real C parser/query deadline')


def grammar_workflow(library, helper, root, work, env):
    assert 'grammar\tc\tavailable' in cli(helper, ['catalog'], work, env)
    assert 'Installed languages:' in cli(helper, ['list'], work, env)
    cli(helper, ['install', 'c'], work, env)
    pointer = root / 'c'
    first = active_directory(library, pointer)
    assert pointer.is_file() and not pointer.is_symlink()
    assert (first / 'parser.so').read_bytes()[:2] == b'MZ', 'UCRT compiler must produce a real Windows PE grammar'
    assert (first / 'highlights.scm').stat().st_size and (first / 'extensions').read_text().strip() == 'c\nh'
    assert 'grammar\tc\tinstalled' in cli(helper, ['catalog'], work, env)
    listed = cli(helper, ['list'], work, env).split('Available to install:', 1)[0]
    assert '  c:' in listed, ('installed grammar missing from list', listed)
    old = library.dna_syntax_open_named(str(root).encode('utf-8'), b'c')
    assert old, 'full DLL must load the freshly compiled C parser and query'
    new = None
    try:
        prove_parser(library, old, 1)
        cli(helper, ['install', 'c'], work, env)
        second = active_directory(library, pointer)
        assert first != second and first.is_dir(), 'updating must retain the immutable previous grammar'
        assert (first / 'parser.so').read_bytes()[:2] == b'MZ'
        new = library.dna_syntax_open_named(str(root).encode('utf-8'), b'c')
        assert new and new != old, 'new syntax worker must resolve the published version'
        prove_parser(library, old, 2)
        prove_parser(library, new, 3)
        config = Path(env['XDG_CONFIG_HOME']) / 'dna/languages.toml'
        config.parent.mkdir(parents=True, exist_ok=True)
        registry = tomllib.loads((ROOT / 'languages/registry.toml').read_text(encoding='utf-8'))['c']
        registry['sha256'] = '0' * 64
        config.write_text('[c]\n' + '\n'.join(key + ' = ' + json.dumps(value) for key, value in registry.items()) + '\n', encoding='utf-8')
        before = pointer.read_bytes()
        try:
            cli(helper, ['install', 'c'], work, env, success=False, timeout=90)
            assert pointer.read_bytes() == before and active_directory(library, pointer) == second
            prove_parser(library, old, 4)
            prove_parser(library, new, 5)
        finally:
            config.unlink()
    finally:
        if new:
            library.dna_syntax_close(new)
        library.dna_syntax_close(old)
    outside = work / 'outside grammar cleanup'
    outside.mkdir()
    sentinel = outside / 'KEEP.txt'
    sentinel.write_bytes(b'outside grammar cleanup survives')
    junction = second / 'outside-junction'
    subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(junction), str(outside)],
                   check=True, capture_output=True, timeout=10)
    cli(helper, ['uninstall', 'c'], work, env)
    assert not pointer.exists() and not second.exists() and first.is_dir()
    assert sentinel.read_bytes() == b'outside grammar cleanup survives'
    assert not library.dna_syntax_open_named(str(root).encode('utf-8'), b'c'), 'retained hidden versions must remain inactive'
    assert 'grammar\tc\tavailable' in cli(helper, ['catalog'], work, env)
    print('PASS actual Windows grammar CLI: pinned HTTPS/hash, UCRT PE/query validation, immutable update, old/new workers, checksum rollback, signed activation, nofollow uninstall and inert retained version', flush=True)


SERVER_JS = r'''#!/usr/bin/env node
const info = require('./package.json');
let pending = Buffer.alloc(0), stopped = false;
function reply(id, result) {
  const body = Buffer.from(JSON.stringify({jsonrpc:'2.0', id, result}));
  process.stdout.write(Buffer.from(`Content-Length: ${body.length}\r\n\r\n`));
  process.stdout.write(body);
}
process.stdin.on('data', data => {
  pending = Buffer.concat([pending, data]);
  while (true) {
    const boundary = pending.indexOf('\r\n\r\n');
    if (boundary < 0) return;
    const match = /Content-Length: ([0-9]+)/i.exec(pending.subarray(0,boundary).toString());
    if (!match) process.exit(80);
    const length = Number(match[1]), end = boundary + 4 + length;
    if (pending.length < end) return;
    const message = JSON.parse(pending.subarray(boundary+4,end));
    pending = pending.subarray(end);
    if (message.method === 'initialize') reply(message.id, {capabilities:{}, serverInfo:{name:'DNA fixture', version:info.version}});
    else if (message.method === 'fixture/argv') reply(message.id, {argv:process.argv.slice(2), cwd:process.cwd()});
    else if (message.method === 'shutdown') { stopped = true; reply(message.id, null); }
    else if (message.method === 'exit') process.exit(stopped ? 0 : 81);
  }
});
process.stdin.on('end', () => process.exit(stopped ? 0 : 82));
'''

FORWARD_JS = r'''const fs = require('fs'), cp = require('child_process'), path = require('path');
const args = process.argv.slice(2), pin = process.env.DNA_FIXTURE_PIN;
if (args[0] !== 'install' || args.filter(x=>x===pin).length !== 1 || !args.includes('--ignore-scripts')) process.exit(83);
const prefix = args[args.indexOf('--prefix')+1];
if (!prefix || !path.basename(prefix).startsWith('.install-')) process.exit(84);
fs.appendFileSync(process.env.DNA_FIXTURE_NPM_LOG, JSON.stringify({args,prefix})+'\n');
const forwarded = args.map(value => value === pin ? process.env.DNA_FIXTURE_TARBALL : value);
const result = cp.spawnSync(process.execPath, [process.env.DNA_FIXTURE_NPM_CLI, ...forwarded], {stdio:'inherit',env:process.env});
if (result.error) { console.error(result.error); process.exit(85); }
process.exit(result.status === null ? 86 : result.status);
'''


def node_tools():
    node = shutil.which('node.exe')
    assert node, 'native node.exe is required to qualify npm installation'
    node = Path(node).resolve()
    candidates = [node.parent / 'node_modules/npm/bin/npm-cli.js']
    npm = shutil.which('npm.cmd')
    if npm:
        candidates.append(Path(npm).parent / 'node_modules/npm/bin/npm-cli.js')
    npm_cli = next((path for path in candidates if path.is_file()), None)
    assert npm_cli, ('real npm-cli.js is required', candidates)
    return node, npm_cli.resolve()


def pack_fixture(version, work, node, npm_cli, env):
    package = work / ('npm fixture ' + version)
    package.mkdir()
    (package / 'server.js').write_text(SERVER_JS, encoding='utf-8', newline='\n')
    (package / 'lifecycle.js').write_text("require('fs').writeFileSync(process.env.DNA_FIXTURE_LIFECYCLE_MARKER,'LIFECYCLE RAN');\n", encoding='utf-8')
    metadata = {'name': 'pyright', 'version': version, 'bin': {'pyright-langserver': 'server.js'},
                'files': ['server.js', 'lifecycle.js'], 'scripts': {name: 'node lifecycle.js'
                for name in ('prepack', 'preinstall', 'install', 'postinstall')}}
    (package / 'package.json').write_text(json.dumps(metadata), encoding='utf-8')
    result = subprocess.run([str(node), str(npm_cli), 'pack', '--json', '--ignore-scripts'],
        cwd=package, env=env, check=True, capture_output=True, timeout=30)
    filename = json.loads(result.stdout)[0]['filename']
    tarball = package / filename
    assert tarball.is_file() and tarball.stat().st_size > 0
    return tarball


def server_handshake(helper, work, env, version):
    with OwnedChild([helper, 'server-run', 'python'], work, env) as child:
        child.send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                    'params': {'processId': os.getpid(), 'rootUri': work.as_uri(), 'capabilities': {}}})
        response = child.response(1)
        assert response['result']['serverInfo']['version'] == version, response
        child.send({'jsonrpc': '2.0', 'id': 2, 'method': 'fixture/argv', 'params': {}})
        response = child.response(2)
        assert response['result']['argv'] == ['--stdio'], response
        assert os.path.samefile(response['result']['cwd'], work), response
        child.send({'jsonrpc': '2.0', 'id': 3, 'method': 'shutdown', 'params': None})
        assert child.response(3)['result'] is None
        child.send({'jsonrpc': '2.0', 'method': 'exit', 'params': None})
        # Keep stdin open until the actual protocol has completed. EOF is not
        # accepted as a substitute for initialize/shutdown transport proof.
        result = child.complete(timeout=5)
        assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)


def server_workflow(library, helper, root, work, env):
    node, npm_cli = node_tools()
    wrapper = work / 'test-only npm wrapper'
    wrapper.mkdir()
    forward = wrapper / 'npm-forward.js'
    forward.write_text(FORWARD_JS, encoding='utf-8')
    # Managed server execution intentionally filters its environment. Keep the
    # fixture's resolved launch targets in the wrappers so runtime Node does not
    # depend on installer-only DNA_FIXTURE variables surviving that boundary.
    node_command = shlex.quote(node.as_posix())
    forward_command = shlex.quote(forward.as_posix())
    for name, text in {
        'node': '#!/usr/bin/env bash\nexec ' + node_command + ' "$@"\n',
        'npm': '#!/usr/bin/env bash\nexec ' + node_command + ' ' + forward_command + ' "$@"\n',
    }.items():
        path = wrapper / name
        path.write_text(text, encoding='utf-8', newline='\n')
        path.chmod(0o755)
    marker = work / 'LIFECYCLE-MUST-NOT-RUN.txt'
    log = work / 'npm-invocations.jsonl'
    servers = (ROOT / 'installer/servers.dyn').read_text(encoding='utf-8')
    pin = re.search(r'packages: "(pyright@[^" ]+)"', servers)
    assert pin, 'the managed Python catalogue must name one pinned pyright package'
    env = dict(env, PATH=str(wrapper) + os.pathsep + env['PATH'],
        DNA_FIXTURE_NPM_CLI=str(npm_cli), DNA_FIXTURE_LIFECYCLE_MARKER=str(marker),
        DNA_FIXTURE_NPM_LOG=str(log), DNA_FIXTURE_PIN=pin[1], npm_config_offline='true',
        npm_config_audit='false', npm_config_fund='false',
        npm_config_cache=str(work / 'npm cache'), npm_config_userconfig=str(work / 'isolated npmrc'))
    first_tarball = pack_fixture('1.0.0', work, node, npm_cli, env)
    second_tarball = pack_fixture('2.0.0', work, node, npm_cli, env)
    assert not marker.exists(), 'npm pack must not execute lifecycle scripts'
    env['DNA_FIXTURE_TARBALL'] = str(first_tarball)
    cli(helper, ['server-install', 'python'], work, env)
    pointer = root / '.servers/python'
    first = active_directory(library, pointer)
    binary = first / 'node_modules/.bin/pyright-langserver'
    assert binary.is_file() and binary.with_suffix('.cmd').is_file() and binary.with_suffix('.ps1').is_file(), 'real Windows npm must create its .bin launchers'
    assert (first / 'package-lock.json').is_file()
    assert json.loads((first / 'node_modules/pyright/package.json').read_text())['version'] == '1.0.0'
    assert 'server\tpython\tinstalled' in cli(helper, ['catalog'], work, env)
    assert not marker.exists(), 'server-install ran an npm lifecycle script'
    server_handshake(helper, work, env, '1.0.0')
    env['DNA_FIXTURE_TARBALL'] = str(second_tarball)
    cli(helper, ['server-update', 'python'], work, env)
    second = active_directory(library, pointer)
    assert second != first and first.is_dir(), 'server-update must retain the previous immutable npm version'
    assert json.loads((first / 'node_modules/pyright/package.json').read_text())['version'] == '1.0.0'
    assert json.loads((second / 'node_modules/pyright/package.json').read_text())['version'] == '2.0.0'
    assert not marker.exists(), 'server-update ran an npm lifecycle script'
    server_handshake(helper, work, env, '2.0.0')
    invocations = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
    assert len(invocations) == 2 and all('--ignore-scripts' in item['args'] and pin[1] in item['args'] for item in invocations)
    for item in invocations:
        prefix = Path(item['prefix'])
        assert prefix.name.startswith('.install-') and os.path.samefile(prefix.parent, root / '.servers'), item
    cli(helper, ['server-uninstall', 'python'], work, env)
    assert not pointer.exists() and not second.exists() and first.is_dir()
    assert 'server\tpython\tavailable' in cli(helper, ['catalog'], work, env)
    assert not marker.exists(), 'managed npm workflow executed a lifecycle script'
    print('PASS actual Windows npm/server CLI: local real npm pack/install, ignored lifecycle scripts, Windows .bin layout, signed immutable updates, raw initialize/shutdown before EOF, inherited stdio and uninstall', flush=True)


def workflow(library_path, helper, work):
    env = dict(os.environ, HOME=str(work), USERPROFILE=str(work),
        XDG_CONFIG_HOME=str(work / 'config café 日本語'), XDG_STATE_HOME=str(work / 'state'),
        DNA_LANGUAGE_DIR=str(work / 'managed languages café 日本語'), DNA_DEFAULT_SERVERS='0')
    root = Path(env['DNA_LANGUAGE_DIR'])
    with contextlib.ExitStack() as directories:
        directories.enter_context(os.add_dll_directory(str(library_path.parent)))
        library = c.CDLL(str(library_path))
        bind_library(library)
        grammar_workflow(library, helper, root, work, env)
        server_workflow(library, helper, root, work, env)


def main():
    if os.name != 'nt':
        raise SystemExit('Native Windows execution is required; this workflow is not a cross-object test')
    if len(sys.argv) == 5 and sys.argv[1] == '--workflow':
        workflow(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
        return
    import native_windows as native
    compiler = native.dependencies()
    env = native.environment(compiler)
    env['DNA_WINDOWS_BASH'] = str(native.prefix().parent / 'usr/bin/bash.exe')
    library = native.DEPS / 'install/lib/dna_native.dll'
    helper = native.DEPS / 'install/bin/dna-language.exe'
    assert helper.is_file() and library.is_file(), 'complete native installer and service DLL are required'
    with tempfile.TemporaryDirectory(prefix='dna-installer-workflow-') as temporary:
        work = Path(temporary) / 'workflow café 日本語'
        work.mkdir()
        # Unload all C parser and service DLLs with the child process before
        # Windows recursively removes the isolated workflow directory.
        subprocess.run([sys.executable, str(Path(__file__).resolve()), '--workflow',
            str(library), str(helper), str(work)], cwd=work, env=env, check=True, timeout=600)
    print('PASS complete native Windows installer workflow', flush=True)


if __name__ == '__main__':
    main()
