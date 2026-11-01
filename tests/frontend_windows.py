#!/usr/bin/env python3
"""Qualify the exact frontend environment and CPU-clock Windows boundary."""
from pathlib import Path
import base64
import ctypes as c
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn
from sdk_compat import environment

FIXTURE = r'''
use "std/c"
use "./host" host
use "std/fs" frontend_test_fs
struct ThreadTime { seconds, nanoseconds: i64 }
fn command_tests() {
  root_storage:[4096]u8=[]
  helper_storage:[4096]u8=[]
  script_storage:[8192]u8=[]
  root:=host.environment("DNA_COMMAND_ROOT",root_storage[..])
  helper:=host.environment("DNA_COMMAND_HELPER",helper_storage[..])
  script:=host.environment("DNA_COMMAND_SCRIPT",script_storage[..])
  if !root.ok || !root.found || !helper.ok || !helper.found || !script.ok || !script.found { #panic("command fixture environment") }
  command:[32768]u8=[]
  used:usize=0
  if !platform_language_command(command[..],&used,root.value,helper.value,"-c",script.value) || used==0 || command[used]!=0 { #panic("language command builder") }
  for byte in command[..used] { if byte>=128 { #panic("command must contain only ASCII") } }
  if !frontend_test_fs.write_all("language-command.txt",command[..used]).ok { #panic("command fixture write") }
  protocol_storage:[8192]u8=[]
  protocol:=host.environment("DNA_COMMAND_PROTOCOL",protocol_storage[..])
  if !protocol.ok || !protocol.found { #panic("protocol fixture environment") }
  used=0
  if !platform_language_command(command[..],&used,root.value,helper.value,"-c",protocol.value) || !frontend_test_fs.write_all("language-protocol-command.txt",command[..used]).ok { #panic("protocol command builder") }
  used=0
  if !platform_language_command(command[..],&used,root.value,helper.value,"--version","") || !frontend_test_fs.write_all("language-version-command.txt",command[..used]).ok { #panic("optional name omitted") }
  used=0
  if !platform_language_command(command[..],&used,root.value,helper.value,"-c","import sys;sys.exit(7)") || !frontend_test_fs.write_all("language-failure-command.txt",command[..used]).ok { #panic("failure command") }
  rejected:[32]u8=[]
  for at in 0..32 { rejected[at]=90 }
  previous:usize=3
  if platform_language_command(rejected[..],&previous,root.value,helper.value,"-c",script.value) || previous!=3 { #panic("command capacity refusal") }
  for byte in rejected { if byte!=90 { #panic("failed command must preserve output") } }
  nul:[3]u8=[97,0,98]
  invalid:[1]u8=[255]
  for bad in [nul[..],invalid[..]] {
    if platform_language_command(command[..],&previous,root.value,helper.value,"-c",bad) || previous!=3 { #panic("invalid command input") }
  }
  huge:[10000]u8=[]
  for at in 0..10000 { huge[at]=97 }
  if platform_language_command(command[..],&previous,root.value,helper.value,"-c",huge[..]) || previous!=3 { #panic("cmd encoded length bound") }
  directory:[32768]u8=[]
  size:=platform_job_directory(directory[..])
  if size<3 || directory[size]!=0 || directory[1]!=58 || directory[2]!=47 || !frontend_test_fs.write_all("language-directory.txt",directory[..size]).ok { #panic("trusted native job directory") }
  if platform_job_directory(rejected[..1])!=0 || rejected[0]!=90 { #panic("job directory capacity") }
  parent:[64]u8=[]
  value:=host.environment("DNA_LANGUAGE_DIR",parent[..])
  expected:[]const u8="parent unchanged"
  if !value.ok || !value.found || #len(value.value)!=#len(expected) { #panic("parent language environment") }
  for at in 0..#len(expected) { if value.value[at]!=expected[at] { #panic("command builder must not change parent environment") } }
}
fn main() {
  key := "DNA_FRONTEND_QUALIFICATION\0"
  first := "session café 日本語\0"
  second := "changed\0"
  if handoff_setenv(&key[0], &first[0], 1) != 0 { #panic("Unicode environment set") }
  storage: [4096]u8 = []
  value := host.environment(key[..#len(key)-1], storage[..])
  if !value.ok || !value.found || #len(value.value) != #len(first)-1 { #panic("Unicode environment read") }
  for at in 0..#len(value.value) {
    if value.value[at] != first[at] { #panic("Unicode environment bytes") }
  }
  if handoff_setenv(&key[0], &second[0], 0) != 0 { #panic("environment no-overwrite") }
  value = host.environment(key[..#len(key)-1], storage[..])
  if #len(value.value) != #len(first)-1 { #panic("environment must retain original") }
  if handoff_unsetenv(&key[0]) != 0 { #panic("environment removal") }
  value = host.environment(key[..#len(key)-1], storage[..])
  if !value.ok || value.found { #panic("removed environment") }
  thread_before := ThreadTime{}
  process_before := ThreadTime{}
  if thread_clock(3, &thread_before) != 0 || thread_clock(2, &process_before) != 0 { #panic("native CPU clocks") }
  total: u64 = 0
  for at in 0..1000000 { total = #wrap(total + #cast(u64, at)) }
  if total != 499999500000 { #panic("CPU clock workload") }
  thread_after := ThreadTime{}
  process_after := ThreadTime{}
  if thread_clock(3, &thread_after) != 0 || thread_clock(2, &process_after) != 0 || thread_clock(99, &thread_after) == 0 { #panic("CPU clock samples") }
  if thread_after.seconds < thread_before.seconds || process_after.seconds < process_before.seconds || thread_after.nanoseconds < 0 || thread_after.nanoseconds >= 1000000000 || process_after.nanoseconds < 0 || process_after.nanoseconds >= 1000000000 { #panic("CPU clock normalization") }
  _ = frontend_isatty(0)
  _ = frontend_isatty(1)
  _ = frontend_display_available()
  command_tests()
}
'''
def protocol_oracle(line, cwd, env, initial, initial_error):
    """The helper must answer with stdin still open, then preserve raw bytes."""
    process = subprocess.Popen(line, cwd=cwd, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    streams = [bytearray(), bytearray()]
    ready = [threading.Event(), threading.Event()]
    failures = []
    def reader(index, stream, minimum):
        try:
            while True:
                block = os.read(stream.fileno(), 65536)
                if not block:
                    break
                streams[index].extend(block)
                if len(streams[index]) >= minimum:
                    ready[index].set()
        except BaseException as error:
            failures.append(error)
    readers = [threading.Thread(target=reader, args=(0, process.stdout, len(initial)), daemon=True),
               threading.Thread(target=reader, args=(1, process.stderr, len(initial_error)), daemon=True)]
    for worker in readers:
        worker.start()
    writer = None
    payload = (bytes(range(256)) + 'café 日本語🙂\r\n'.encode('utf-8')) * 4096
    def send():
        try:
            process.stdin.write(payload)
            process.stdin.close()
        except BaseException as error:
            failures.append(error)
    try:
        assert ready[0].wait(10), ('helper must reply before stdin EOF', bytes(streams[0][:256]), bytes(streams[1][:256]))
        assert ready[1].wait(10), ('raw initial stderr', bytes(streams[1][:256]))
        assert bytes(streams[0]) == initial and bytes(streams[1]) == initial_error, (bytes(streams[0][:256]), bytes(streams[1][:256]))
        assert process.poll() is None and not process.stdin.closed, 'helper remains interactive before request input'
        writer = threading.Thread(target=send, daemon=True)
        writer.start()
        assert process.wait(timeout=20) == 0
        writer.join(timeout=5)
        for worker in readers:
            worker.join(timeout=5)
        assert not writer.is_alive() and all(not worker.is_alive() for worker in readers)
        assert not failures, failures
        assert bytes(streams[0]) == initial + payload, ('stdout protocol changed', len(streams[0]), len(initial + payload))
        assert bytes(streams[1]) == initial_error + payload, ('stderr protocol changed', len(streams[1]), len(initial_error + payload))
    finally:
        if not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            # Restrict cleanup to this temporary fixture's process tree.
            subprocess.run(['taskkill.exe', '/T', '/F', '/PID', str(process.pid)], capture_output=True)
            process.wait(timeout=5)
        for worker in readers:
            worker.join(timeout=5)
        process.stdout.close()
        process.stderr.close()


compiler = real_dyn()
with tempfile.TemporaryDirectory(prefix='dna-frontend-win-') as temporary:
    stage = Path(temporary)
    for module in ('host', 'cstring', 'owned_arena'):
        shutil.copytree(ROOT / 'src' / module, stage / module)
    shutil.copyfile(ROOT / 'src/c_windows.dyn', stage / 'c_windows.dyn')
    (stage / 'main.dyn').write_text(FIXTURE, encoding='utf-8')
    env = environment(compiler)
    for target in ('x86_64-windows', 'aarch64-windows'):
        for mode in ('debug', 'release'):
            subprocess.run([sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler), 'build', str(stage), '--'+mode,
                '--target', target, '--emit-object', '--no-link', '--output', str(stage/(target+'-'+mode))], env=env, check=True)
        print('PASS frontend Windows objects: '+target, flush=True)
    if os.name == 'nt':
        kits = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits/10/Lib'
        libraries = stage / 'lib'
        libraries.mkdir()
        for name, folder in (('kernel32', 'um'), ('ucrt', 'ucrt')):
            candidates = sorted(kits.glob('*/'+folder+'/x64/'+name+'.lib'))
            if not candidates:
                raise SystemExit('Windows SDK '+name+'.lib required')
            shutil.copyfile(candidates[-1], libraries/('lib'+name+'.dll.a'))
        env['DYN_LIBRARY_PATH'] = str(libraries)
        for mode in ('debug', 'release'):
            output = stage/(mode+'.exe')
            subprocess.run([sys.executable, str(ROOT/'scripts/compile.py'), str(compiler), 'build', str(stage), '--'+mode, '--output', str(output)], env=env, check=True)
            working = stage / ('project café 日本語-' + mode)
            working.mkdir()
            helper_directory = working / "Python %PATH%!&' 日本語 ‘q’"
            plain_junction = working / 'python-junction'
            subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(plain_junction), str(Path(sys.executable).parent)], check=True, capture_output=True)
            # Rename through the native filesystem API so cmd never expands
            # the percent/exclamation characters while preparing the fixture.
            os.rename(plain_junction, helper_directory)
            helper = helper_directory / Path(sys.executable).name
            root = working / "root %PATH%!&' 日本語 ‘a’‚‛"
            root.mkdir()
            code = 'import json,os,sys; print(json.dumps({"root":os.environ["DNA_LANGUAGE_DIR"],"argv":sys.argv,"cwd":os.getcwd(),"executable":sys.executable},ensure_ascii=True)); # trailing slash \\\\'
            body = json.dumps({'ready': 'café 日本語🙂'}, ensure_ascii=False).encode('utf-8')
            initial = b'Content-Length: ' + str(len(body)).encode('ascii') + b'\r\n\r\n' + body
            initial_error = b'stderr-ready\x00\xff' + ' café 日本語🙂'.encode('utf-8')
            protocol = ("import os,msvcrt\nfor fd in (0,1,2): msvcrt.setmode(fd,os.O_BINARY)\n"
                        "def emit(fd,data):\n while data:\n  count=os.write(fd,data)\n  data=data[count:]\n"
                        "emit(1," + repr(initial) + ")\nemit(2," + repr(initial_error) + ")\n"
                        "while True:\n block=os.read(0,8192)\n if not block: break\n emit(1,block)\n emit(2,block)\n")
            child_env = dict(env, DNA_COMMAND_ROOT=str(root), DNA_COMMAND_HELPER=str(helper),
                             DNA_COMMAND_SCRIPT=code, DNA_COMMAND_PROTOCOL=protocol,
                             DNA_LANGUAGE_DIR='parent unchanged')
            try:
                subprocess.run([str(output)], cwd=working, env=child_env, check=True, timeout=30)
                command = (working / 'language-command.txt').read_text(encoding='ascii')
                directory = (working / 'language-directory.txt').read_text(encoding='utf-8')
                kernel = c.WinDLL('kernel32', use_last_error=True)
                kernel.GetSystemDirectoryW.argtypes = [c.c_void_p, c.c_uint32]
                kernel.GetSystemDirectoryW.restype = c.c_uint32
                system = c.create_unicode_buffer(32768)
                assert kernel.GetSystemDirectoryW(system, len(system))
                assert directory == system.value.replace('\\', '/').rstrip('/')
                assert command.startswith('"' + directory + '/WindowsPowerShell/v1.0/powershell.exe" ')
                encoded = command.rsplit(' ', 1)[1]
                decoded = base64.b64decode(encoded, validate=True).decode('utf-16-le')
                assert "EnvironmentVariables['DNA_LANGUAGE_DIR']=" in decoded and "''" in decoded
                assert 'UseShellExecute=$false' in decoded and 'RedirectStandard' not in decoded
                assert '%PATH%' not in command and '日本語' not in command
                cmd = str(Path(system.value) / 'cmd.exe')
                def execute(text, delayed='OFF'):
                    line = '"' + cmd + '" /D /S /V:' + delayed + ' /C "' + text + '"'
                    return subprocess.run(line, cwd=working, env=child_env, capture_output=True, timeout=30)
                for delayed in ('OFF', 'ON'):
                    result = execute(command, delayed)
                    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
                    actual = json.loads(result.stdout.strip())
                    assert actual['root'] == str(root), actual
                    assert actual['argv'] == ['-c'], actual
                    assert Path(actual['cwd']) == working, actual
                    assert Path(actual['executable']).samefile(sys.executable), actual
                optional = execute((working / 'language-version-command.txt').read_text(encoding='ascii'))
                assert optional.returncode == 0 and optional.stdout.startswith(b'Python '), (optional.stdout, optional.stderr)
                failure = execute((working / 'language-failure-command.txt').read_text(encoding='ascii'))
                assert failure.returncode == 7, (failure.returncode, failure.stdout, failure.stderr)
                protocol_command = (working / 'language-protocol-command.txt').read_text(encoding='ascii')
                protocol_line = '"' + cmd + '" /D /S /V:ON /C "' + protocol_command + '"'
                protocol_oracle(protocol_line, working, child_env, initial, initial_error)
                assert child_env['DNA_LANGUAGE_DIR'] == 'parent unchanged'
            finally:
                os.rmdir(helper_directory)
            print('PASS native Windows frontend environment, CPU clocks, trusted job directory, literal commands and interactive raw byte transport ('+mode+')', flush=True)
