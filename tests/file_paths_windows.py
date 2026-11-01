#!/usr/bin/env python3
"""Check complete file-module objects and native Windows parent-path helpers."""
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
pub fn test_parent(path:*const u8,output:*u8) i32 {
  if realpath(path,output)!=nil { return 1 }
  return 0
}
pub fn test_normalize(path:*const u8,length:usize,output:*u8,capacity:usize) usize {
  return #len(file_normalize_path(path[..length],output[..capacity]))
}
fn main() {}
'''


def native_tests(binary, work):
    lib = c.CDLL(str(binary))
    lib.test_parent.argtypes = [c.c_char_p, c.c_void_p]
    lib.test_normalize.argtypes = [c.c_char_p, c.c_size_t, c.c_void_p, c.c_size_t]
    lib.test_normalize.restype = c.c_size_t
    def normalize(path, expected):
        output = c.create_string_buffer(4096)
        size = lib.test_normalize(path, len(path), output, len(output))
        assert output.raw[:size] == expected and output.raw[size] == 0
    normalize(b'C:\\folder\\child.txt', b'C:/folder/child.txt')
    normalize(b'C:/folder\\child.txt', b'C:/folder/child.txt')
    normalize(b'\\\\server\\share\\file', b'//server/share/file')
    normalize('café\\日本語.txt'.encode('utf-8'), 'café/日本語.txt'.encode('utf-8'))
    for path, capacity in ((b'long', 0), (b'long', 1), (b'long', 4), (b'a\x00b', 8)):
        guarded = c.create_string_buffer(b'\xa5' * (capacity + 32))
        assert lib.test_normalize(path, len(path), c.byref(guarded, 16), capacity) == 0
        assert guarded.raw[:16] == b'\xa5' * 16
        assert guarded.raw[16+capacity:16+capacity+16] == b'\xa5' * 16
        if capacity:
            assert guarded.raw[16] == 0
    root = work / 'parent café 日本語'
    root.mkdir()
    link = work / 'parent junction'
    subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(root)], check=True, capture_output=True)
    source = root / 'existing.txt'
    source.write_bytes(b'file')
    output = c.create_string_buffer(4096)
    def canonical(path, expected):
        assert lib.test_parent(os.fsencode(path), output) == 1, ('parent canonicalization', str(path))
        actual = output.value.decode('utf-8')
        assert '\\' not in actual and not actual.startswith('//?/'), actual
        assert os.path.samefile(actual, expected), (actual, str(expected))
        return actual
    try:
        canonical(root, root)
        alias = c.create_string_buffer(4096)
        alias.value = os.fsencode(root)
        assert lib.test_parent(c.cast(alias, c.c_char_p), alias) == 1
        assert os.path.samefile(alias.value.decode('utf-8'), root)
        canonical(str(root).replace('\\', '/'), root)
        canonical(link, root)
        canonical('.', work)
        # This seam accepts parents only; the caller retains its final filename.
        assert lib.test_parent(os.fsencode(source), output) == 0 and output.value == b''
        assert lib.test_parent(os.fsencode(root / 'missing'), output) == 0 and output.value == b''
        assert lib.test_parent(b'\xff', output) == 0 and output.value == b''
        assert lib.test_parent(None, output) == 0
        assert lib.test_parent(os.fsencode(root), None) == 0
        kernel = c.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = c.c_void_p
        kernel.GetProcessHandleCount.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
        count = c.c_uint32()
        assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
        before = count.value
        for _ in range(128):
            canonical(link, root)
            assert lib.test_parent(os.fsencode(root / 'missing'), output) == 0
            assert lib.test_parent(os.fsencode(source), output) == 0
        assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
        assert count.value == before, ('parent path handle leak', before, count.value)
    finally:
        os.rmdir(link)
    print('PASS Windows file paths: Unicode parents/cwd, junction canonicalization, slash normalization, invalid paths, bounded writes and handle cleanup', flush=True)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--native-library':
        native_tests(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first.')
    environment = sdk_environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-file-paths-windows-') as temporary:
        work = Path(temporary)
        stage = work / 'helpers'
        stage.mkdir()
        shutil.copyfile(ROOT / 'src/files/c_windows.dyn', stage / 'c_windows.dyn')
        (stage / 'main.dyn').write_text(FIXTURE, encoding='utf-8')
        complete = work / 'complete'
        complete.mkdir()
        for module in ('files', 'buffer', 'filesystem', 'host', 'cstring', 'owned_arena'):
            shutil.copytree(ROOT / 'src' / module, complete / module)
        (complete / 'main.dyn').write_text('use "./files"\nfn main() {\n output:[4096]u8=[]\n _=files.resolve("C:/parent/file.txt",output[..])\n}\n', encoding='utf-8')
        for target in ('x86_64-windows', 'aarch64-windows'):
            for mode in ('debug', 'release'):
                for name, source in (('helpers', stage), ('complete', complete)):
                    command = [sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler), 'build', str(source), '--'+mode, '--target', target, '--emit-object', '--no-link', '--output', str(work / (name + '-' + target + '-' + mode))]
                    subprocess.run(command, check=True, env=environment, timeout=120)
            print(f'PASS Windows file paths helpers and complete files module objects: {target} debug/release', flush=True)
        if os.name != 'nt':
            print('QUALIFICATION GAP: objects do not prove native Windows path canonicalization.', flush=True)
            return
        kits = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits/10/Lib'
        libraries = work / 'lib'
        libraries.mkdir()
        for name, folder in (('kernel32', 'um'), ('ucrt', 'ucrt')):
            candidates = sorted(kits.glob('*/' + folder + '/x64/' + name + '.lib'))
            if not candidates:
                raise SystemExit('Windows SDK x64 ' + name + '.lib is required.')
            shutil.copyfile(candidates[-1], libraries / ('lib' + name + '.dll.a'))
        environment['DYN_LIBRARY_PATH'] = str(libraries)
        for mode in ('debug', 'release'):
            binary = work / ('native-' + mode + '.dll')
            subprocess.run([sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler), 'build', str(stage), '--'+mode, '--shared', '--output', str(binary)], check=True, env=environment, timeout=120)
            runtime = work / ('runtime-' + mode)
            runtime.mkdir()
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--native-library', str(binary), str(runtime)], check=True, env=environment, cwd=runtime, timeout=30)


if __name__ == '__main__':
    main()
