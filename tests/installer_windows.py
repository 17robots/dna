#!/usr/bin/env python3
"""Compile the full installer; qualify Windows shell and package host hooks."""
import contextlib
import ctypes as c
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn
from sdk_compat import environment as sdk_environment

FIXTURE = r'''
pub fn test_system(command:*const u8) i32 { return system(command) }
pub fn test_directory(output:*u8,capacity:usize) usize { return installer_directory(output[..capacity]) }
pub fn test_absolute(path:*const u8) i32 {
  if installer_absolute(path[..installer_windows_c.string_length(path,4096)]) { return 1 }
  return 0
}
pub fn test_tools(output:*u8,capacity:usize) usize {
  text:=installer_shell_tools()
  if #len(text)>=capacity { return 0 }
  for index in 0..#len(text) { output[..capacity][index]=text[index] }
  output[..capacity][#len(text)]=0
  return #len(text)
}
pub fn test_temporary(path:*u8) i32 { if temporary(path)!=nil { return 1 }
  return 0 }
pub fn test_pointer(target,path:*const u8) i32 {
  if installer_symbolic_link(target[..installer_windows_c.string_length(target,4096)],path[..installer_windows_c.string_length(path,4096)]).ok { return 1 }
  return 0
}
pub fn test_read(path:*const u8,output:*u8,capacity:usize) isize {
  arena:=installer_windows_mem.arena_create(16384)
  defer installer_windows_mem.arena_release(arena)
  read:=installer_read_link(arena,path[..installer_windows_c.string_length(path,4096)])
  if !read.ok { return read.error }
  if #len(read.value)>=capacity { return -28 }
  for index in 0..#len(read.value) { output[..capacity][index]=read.value[index] }
  output[..capacity][#len(read.value)]=0
  return #cast(isize,#len(read.value))
}
pub fn test_resolve(path:*const u8,output:*u8,capacity:usize) usize {
  return #len(installer_package_path(path[..installer_windows_c.string_length(path,4096)],output[..capacity]))
}
pub fn test_remove(path:*const u8) i32 {
  if installer_remove_tree(path[..installer_windows_c.string_length(path,4096)]).ok { return 1 }
  return 0
}
pub fn test_executable(path:*const u8) i32 {
  if installer_executable(path[..installer_windows_c.string_length(path,4096)]) { return 1 }
  return 0
}
fn main() {}
'''


def native_tests(binary, library, work, scenario):
    os.chdir(work)
    with contextlib.ExitStack() as directories:
        directories.enter_context(os.add_dll_directory(str(library.parent)))
        native = c.CDLL(str(library))
        lib = c.CDLL(str(binary))
        lib.test_system.argtypes = [c.c_char_p]
        if scenario == 'missing-tools':
            assert lib.test_system(b'echo should-not-run') == -1
            print('PASS Windows installer clearly refuses unavailable/oversized configured tools', flush=True)
            return
        lib.test_directory.argtypes = [c.c_void_p, c.c_size_t]
        lib.test_directory.restype = c.c_size_t
        lib.test_absolute.argtypes = [c.c_char_p]
        lib.test_tools.argtypes = [c.c_void_p, c.c_size_t]
        lib.test_tools.restype = c.c_size_t
        lib.test_temporary.argtypes = [c.c_void_p]
        lib.test_pointer.argtypes = [c.c_char_p, c.c_char_p]
        lib.test_read.argtypes = [c.c_char_p, c.c_void_p, c.c_size_t]
        lib.test_read.restype = c.c_ssize_t
        lib.test_resolve.argtypes = [c.c_char_p, c.c_void_p, c.c_size_t]
        lib.test_resolve.restype = c.c_size_t
        for name in ('test_remove', 'test_executable'):
            getattr(lib, name).argtypes = [c.c_char_p]
        output = c.create_string_buffer(49152)
        length = lib.test_directory(output, len(output))
        assert length and '\\' not in output.value.decode('utf-8')
        assert os.path.samefile(output.value.decode('utf-8'), work)
        for path in (b'C:/root', b'C:\\root', b'//server/share/file', b'\\\\server\\share'):
            assert lib.test_absolute(path) == 1
        for path in (b'relative', b'C:relative', b'/root-relative', b'//'):
            assert lib.test_absolute(path) == 0
        assert lib.test_tools(output, len(output)) > 0
        prelude = output.value
        expected = 'Unicode café 日本語; $literal "quotes" apostrophe\''
        command = prelude + ('set -eu\ntest "$DNA_INSTALLER_MARK" = ' + shlex.quote(os.environ['DNA_INSTALLER_MARK']) + '\nprintf %s ' + shlex.quote(expected) + " > 'shell result.txt'\ncommand -v cc > 'compiler-path.txt'\ncommand -v sha256sum >/dev/null\ncommand -v tar >/dev/null\ncommand -v curl >/dev/null\ncommand -v timeout >/dev/null\n").encode('utf-8')
        assert lib.test_system(command) == 0, 'MSYS2 command execution/environment'
        assert (work / 'shell result.txt').read_text(encoding='utf-8') == expected
        compiler = (work / 'compiler-path.txt').read_text(encoding='utf-8').strip().replace('\\', '/')
        expected_prefix = os.environ['DNA_WINDOWS_PREFIX'].replace('\\', '/').rstrip('/')
        if len(expected_prefix) >= 3 and expected_prefix[1] == ':':
            expected_prefix = '/' + expected_prefix[0].lower() + expected_prefix[2:]
        assert compiler.lower().startswith(expected_prefix.lower() + '/bin/'), ('configured UCRT tools must precede System32/MSYS tools', compiler, expected_prefix)
        assert lib.test_system(b'exit 7') == 7
        assert lib.test_executable(os.fsencode(os.environ['DNA_WINDOWS_BASH'])) == 1
        native.dna_make_directories.argtypes = [c.c_char_p]
        managed = work / 'managed languages'
        assert native.dna_make_directories(os.fsencode(managed)) == 1
        pattern = c.create_string_buffer(os.fsencode(managed / '.demo-XXXXXX'), 4096)
        assert lib.test_temporary(pattern) == 1
        version = Path(pattern.value.decode('utf-8'))
        assert version.is_dir() and version.name.startswith('.demo-') and not version.name.endswith('XXXXXX')
        (version / 'parser.so').write_bytes(b'parser-payload')
        (version / 'highlights.scm').write_bytes(b'(identifier) @variable')
        (version / 'extensions').write_bytes(b'demo')
        active = managed / 'demo'
        assert lib.test_pointer(os.fsencode(version), os.fsencode(active)) == 1
        assert active.is_file() and not active.is_symlink(), 'Windows uses a managed private pointer file'
        assert lib.test_read(os.fsencode(active), output, len(output)) > 0
        assert os.path.samefile(output.value.decode('utf-8'), version)
        for path in (version, active):
            assert lib.test_resolve(os.fsencode(path), output, len(output)) > 0
            assert os.path.samefile(output.value.decode('utf-8'), version)
        output.value = os.fsencode(active)
        assert lib.test_resolve(c.cast(output, c.c_char_p), output, len(output)) > 0
        assert os.path.samefile(output.value.decode('utf-8'), version)
        assert lib.test_resolve(os.fsencode(managed / 'missing'), output, len(output)) == 0
        guarded = c.create_string_buffer(b'\xa5' * 33)
        assert lib.test_resolve(os.fsencode(active), c.byref(guarded, 16), 1) == 0
        assert guarded.raw[:16] == b'\xa5' * 16 and guarded.raw[17:33] == b'\xa5' * 16
        active.unlink()
        assert lib.test_remove(os.fsencode(version)) == 1 and not version.exists()
        root = work / 'remove safely'
        outside = work / 'outside'
        outside.mkdir()
        protected = outside / 'keep.txt'
        protected.write_bytes(b'outside survives')
        root.mkdir()
        (root / 'ordinary.txt').write_bytes(b'ordinary')
        junction = root / 'junction'
        subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(junction), str(outside)], check=True, capture_output=True)
        result = lib.test_remove(os.fsencode(root))
        assert protected.read_bytes() == b'outside survives', 'tree removal followed a junction'
        if result == 0:
            if junction.exists():
                os.rmdir(junction)
            assert lib.test_remove(os.fsencode(root)) == 1
        assert not root.exists()
        print('PASS Windows installer hooks: explicit MSYS2 bash, Unicode argv/cwd/env, UCRT tool precedence, private temporaries/pointers, resolution, nofollow removal and executable checks', flush=True)


def main():
    if len(sys.argv) == 6 and sys.argv[1] == '--native-library':
        native_tests(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5])
        return
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first.')
    environment = sdk_environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-installer-windows-') as temporary:
        work = Path(temporary)
        helpers = work / 'helpers'
        helpers.mkdir()
        shutil.copyfile(ROOT / 'installer/files_windows.dyn', helpers / 'files_windows.dyn')
        (helpers / 'main.dyn').write_text(FIXTURE, encoding='utf-8')
        complete = work / 'complete'
        shutil.copytree(ROOT / 'installer', complete)
        for stage in (helpers, complete):
            for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
                shutil.copytree(ROOT / 'src' / module, stage / module)
        for target in ('x86_64-windows', 'aarch64-windows'):
            for mode in ('debug', 'release'):
                for name, stage in (('helpers', helpers), ('complete', complete)):
                    subprocess.run([sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler), 'build', str(stage), '--'+mode, '--target', target, '--emit-object', '--no-link', '--output', str(work / (name + '-' + target + '-' + mode))], check=True, env=environment, timeout=120)
            print(f'PASS Windows installer hooks and complete installer objects: {target} debug/release', flush=True)
        if os.name != 'nt':
            print('QUALIFICATION GAP: installer objects do not prove native MSYS2 commands, package transactions or LSP/npm installations.', flush=True)
            return
        import native_windows as native
        native.dependencies()
        environment = native.environment(compiler)
        environment['DNA_INSTALLER_MARK'] = 'inherited café 日本語'
        environment['DNA_WINDOWS_PREFIX'] = str(native.prefix())
        environment['DNA_WINDOWS_BASH'] = str(native.prefix().parent / 'usr/bin/bash.exe')
        library = native.DEPS / 'install/lib/dna_native.dll'
        for mode in ('debug', 'release'):
            binary = work / ('native-' + mode + '.dll')
            subprocess.run([sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler), 'build', str(helpers), '--'+mode, '--shared', '--output', str(binary)], check=True, env=environment, timeout=120)
            runtime = work / ('runtime café 日本語-' + mode)
            runtime.mkdir()
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--native-library', str(binary), str(library), str(runtime), 'normal'], check=True, env=environment, timeout=60)
            for invalid in ({'DNA_WINDOWS_BASH': str(runtime / 'missing bash.exe')}, {'DNA_WINDOWS_PREFIX': 'C:/' + 'x' * 5000}):
                subprocess.run([sys.executable, str(Path(__file__).resolve()), '--native-library', str(binary), str(library), str(runtime), 'missing-tools'], check=True, env=dict(environment, **invalid), timeout=30)
        print('QUALIFICATION GAP: hook runtime proof does not qualify complete language-server/npm installation workflows.', flush=True)


if __name__ == '__main__':
    main()
