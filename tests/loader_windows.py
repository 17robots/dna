#!/usr/bin/env python3
"""Compile Windows syntax loader hooks and exercise real relocated DLL paths."""
import ctypes as c
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn
from sdk_compat import environment as sdk_environment

FIXTURE = r'''
#link("kernel32")
#link("ucrt")
extern fn string_length "strlen"(text:*const u8) usize
pub fn dna_syntax_open(root,filename:*const u8) rawptr { _=root
  _=filename
  return nil }
pub fn test_path(output:*u8,capacity:usize) i32 {
  if syntax_module_path(output,capacity) { return 1 }
  return 0
}
pub fn test_readable(path:*const u8) i32 {
  if syntax_readable(path) { return 1 }
  return 0
}
pub fn test_helper(output:*u8,capacity:usize) usize {
  name:=syntax_helper_name()
  if capacity<=#len(name) { return 0 }
  for index in 0..#len(name) { output[..capacity][index]=name[index] }
  output[..capacity][#len(name)]=0
  return #len(name)
}
fn main() {}
'''


def native_tests(binary, work):
    lib = c.CDLL(str(binary))
    lib.test_path.argtypes = [c.c_void_p, c.c_size_t]
    lib.test_readable.argtypes = [c.c_char_p]
    lib.test_helper.argtypes = [c.c_void_p, c.c_size_t]
    lib.test_helper.restype = c.c_size_t
    expected = str(binary.resolve()).replace('\\', '/').encode('utf-8')
    buffer = c.create_string_buffer(131072)
    assert lib.test_path(buffer, len(buffer)) == 1
    assert os.path.samefile(buffer.value.decode('utf-8'), binary), ('module path must locate the DLL', buffer.value, expected)
    expected = buffer.value
    # Query from a deliberately unrelated cwd, including after relocation.
    unrelated = work / 'unrelated working directory'
    unrelated.mkdir(exist_ok=True)
    original = Path.cwd()
    try:
        os.chdir(unrelated)
        assert lib.test_path(buffer, len(buffer)) == 1 and buffer.value == expected
    finally:
        os.chdir(original)
    for capacity in (0, 1, 2, 15, len(expected), len(expected) + 1):
        guarded = c.create_string_buffer(b'\xa5' * (capacity + 32))
        output = c.byref(guarded, 16)
        result = lib.test_path(output, capacity)
        assert result == int(capacity > len(expected)), ('path capacity result', capacity)
        assert guarded.raw[:16] == b'\xa5' * 16
        assert guarded.raw[16+capacity:16+capacity+16] == b'\xa5' * 16, 'path wrote beyond capacity'
        if capacity > 0 and not result:
            assert guarded.raw[16] == 0, 'failed path must return empty string'
    assert lib.test_path(None, 0) == 0 and lib.test_path(None, 32) == 0
    assert lib.test_helper(buffer, len(buffer)) == len(b'bin/dna-language.exe')
    assert buffer.value == b'bin/dna-language.exe'
    readable = work / 'readable café 日本語.txt'
    readable.write_bytes(b'language payload')
    empty = work / 'empty.txt'
    empty.write_bytes(b'')
    directory = work / 'directory'
    directory.mkdir(exist_ok=True)
    for path in (readable, empty):
        assert lib.test_readable(str(path).encode('utf-8')) == 1
    for path in (directory, work / 'missing.txt'):
        assert lib.test_readable(str(path).encode('utf-8')) == 0
    assert lib.test_readable(None) == 0 and lib.test_readable(b'\xff') == 0
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = c.c_void_p
    kernel.GetProcessHandleCount.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
    count = c.c_uint32()
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    before = count.value
    for _ in range(256):
        assert lib.test_path(buffer, len(buffer)) == 1
        assert lib.test_readable(str(readable).encode('utf-8')) == 1
        assert lib.test_readable(str(directory).encode('utf-8')) == 0
        assert lib.test_readable(str(work / 'missing.txt').encode('utf-8')) == 0
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    assert count.value == before, ('loader/descriptor handle leak', before, count.value)
    print('PASS Windows syntax loader: relocated Unicode module, cwd independence, readable regular files, bounded UTF-8, helper executable and handle cleanup', flush=True)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--native-library':
        native_tests(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first.')
    environment = sdk_environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-loader-windows-') as temporary:
        work = Path(temporary)
        stage = work / 'stage'
        stage.mkdir()
        for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
            shutil.copytree(ROOT / 'src' / module, stage / module)
        for source in ('loader_windows.dyn', 'rec_io_windows.dyn'):
            shutil.copyfile(ROOT / 'src/native/dyn' / source, stage / source)
        (stage / 'main.dyn').write_text(FIXTURE, encoding='utf-8')
        if os.name == 'nt':
            kits = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits/10/Lib'
            libraries = work / 'lib'
            libraries.mkdir()
            for name, folder in (('kernel32', 'um'), ('advapi32', 'um'), ('ucrt', 'ucrt')):
                candidates = sorted(kits.glob('*/' + folder + '/x64/' + name + '.lib'))
                if not candidates:
                    raise SystemExit('Windows SDK x64 ' + name + '.lib is required.')
                shutil.copyfile(candidates[-1], libraries / ('lib' + name + '.dll.a'))
            environment['DYN_LIBRARY_PATH'] = str(libraries)
        targets = ('native',) if os.name == 'nt' else ('x86_64-windows', 'aarch64-windows')
        for target in targets:
            for mode in ('debug', 'release'):
                binary = work / (target + '-' + mode + ('.dll' if target == 'native' else '.o'))
                command = [sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler), 'build', str(stage), '--'+mode, '--output', str(binary)]
                if target == 'native':
                    command += ['--shared']
                else:
                    command += ['--target', target, '--emit-object', '--no-link']
                subprocess.run(command, check=True, env=environment, timeout=120)
                if target == 'native':
                    destination = work / ('relocated café 日本語-' + mode)
                    destination.mkdir()
                    relocated = destination / 'renamed-language-loader.dll'
                    shutil.copyfile(binary, relocated)
                    # Run outside the build process so Windows releases the DLL
                    # mapping before TemporaryDirectory removes its files.
                    subprocess.run([sys.executable, str(Path(__file__).resolve()), '--native-library', str(relocated), str(destination)], check=True, timeout=30, env=environment)
                else:
                    print(f'PASS Windows syntax loader production objects: {target} {mode}', flush=True)
    if os.name != 'nt':
        print('QUALIFICATION GAP: cross objects do not prove native Windows loader execution.', flush=True)


if __name__ == '__main__':
    main()
