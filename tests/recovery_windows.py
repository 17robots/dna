#!/usr/bin/env python3
"""Windows native recovery: atomic process-crash persistence, not power-loss proof."""
import ctypes as c
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn
from sdk_compat import environment as sdk_environment

FIXTURE = r'''#link("ucrt")
extern fn string_length "strlen"(text:*const u8)usize
extern fn copy "memcpy"(output:*u8,input:*const u8,length:usize)rawptr
fn dna_notify() {}
fn native_initialize() {}
pub fn test_snapshot(path:*const u8,bytes:*const u8,length:usize)i32 {
  if rec_snapshot(path,bytes,length) { return 1 }
  return 0
}
pub fn test_parent_limit(path:*const u8)i32 {
  fd:=rec_open(path,589824,0)
  if fd<0 { return 0 }
  defer _=rec_close(fd)
  if rec_sync(fd)!=-1 || rec_errno().*!=95 { return 0 }
  if !rec_sync_parent(fd) || rec_errno().*!=95 { return 0 }
  return 1
}
pub fn test_roots()i32 {
  paths:[11][]const u8=["C:\\", "D:/", "C:\\folder", "\\\\server\\share\\file", "//server/share", "\\\\?\\C:\\file", "\\\\?\\UNC\\server\\share\\file", "C:relative", "\\relative", "relative", "\\\\.\\device"]
  roots:[11]usize=[3,3,3,15,14,7,21,0,0,0,0]
  for index in 0..11 {
    path:=paths[index]
    text:[128]u8=[]
    _=copy(&text[0],&path[0],#len(path))
    if rec_path_root(&text[0],#len(path))!=roots[index] || rec_absolute(&text[0])!=(roots[index]!=0) { return 0 }
  }
  return 1
}
fn main() {}
'''


def configure(binary):
    library = c.CDLL(str(binary))
    library.dna_recovery_open.argtypes = [c.c_char_p]
    library.dna_recovery_open.restype = c.c_void_p
    library.dna_recovery_submit.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t]
    library.dna_recovery_submit.restype = c.c_int
    library.dna_recovery_error.argtypes = [c.c_void_p]
    library.dna_recovery_error.restype = c.c_int
    library.dna_recovery_close.argtypes = [c.c_void_p]
    library.test_snapshot.argtypes = [c.c_char_p, c.c_void_p, c.c_size_t]
    library.test_parent_limit.argtypes = [c.c_char_p]
    assert library.test_roots() == 1, 'drive/UNC roots and relative path rejection'
    return library


def private_acl(path):
    advapi = c.WinDLL('advapi32', use_last_error=True)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    advapi.GetNamedSecurityInfoW.argtypes = [c.c_wchar_p, c.c_uint32, c.c_uint32,
        c.c_void_p, c.c_void_p, c.POINTER(c.c_void_p), c.c_void_p, c.POINTER(c.c_void_p)]
    advapi.GetNamedSecurityInfoW.restype = c.c_uint32
    advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [c.c_void_p,
        c.c_uint32, c.c_uint32, c.POINTER(c.c_void_p), c.POINTER(c.c_uint32)]
    advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = c.c_int
    kernel.LocalFree.argtypes = [c.c_void_p]
    kernel.LocalFree.restype = c.c_void_p
    descriptor, dacl, text = c.c_void_p(), c.c_void_p(), c.c_void_p()
    assert advapi.GetNamedSecurityInfoW(str(path), 1, 4, None, None, c.byref(dacl),
        None, c.byref(descriptor)) == 0
    try:
        length = c.c_uint32()
        assert advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor,
            1, 4, c.byref(text), c.byref(length))
        value = c.wstring_at(text)
        assert value.startswith('D:P') and value.count('(') == 1 and ';;;OW)' in value, value
    finally:
        if text.value:
            kernel.LocalFree(text)
        kernel.LocalFree(descriptor)


def shared_read(path):
    # Python's CRT file open can deny FILE_SHARE_DELETE. Permit replacement
    # while observing an older complete generation, as the editor's readers do.
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [c.c_wchar_p, c.c_uint32, c.c_uint32,
        c.c_void_p, c.c_uint32, c.c_uint32, c.c_void_p]
    kernel.CreateFileW.restype = c.c_void_p
    kernel.GetFileSizeEx.argtypes = [c.c_void_p, c.POINTER(c.c_int64)]
    kernel.ReadFile.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32,
        c.POINTER(c.c_uint32), c.c_void_p]
    kernel.CloseHandle.argtypes = [c.c_void_p]
    handle = kernel.CreateFileW(str(path), 0x80000000, 7, None, 3, 0, None)
    if handle == c.c_void_p(-1).value:
        raise OSError(c.get_last_error(), 'snapshot observation open')
    try:
        length = c.c_int64()
        assert kernel.GetFileSizeEx(handle, c.byref(length)) and 0 <= length.value <= 2097152
        output = c.create_string_buffer(length.value)
        received = c.c_uint32()
        assert kernel.ReadFile(handle, output, length.value, c.byref(received), None)
        assert received.value == length.value
        return output.raw
    finally:
        kernel.CloseHandle(handle)


def wait_snapshot(root, expected):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        paths = [path for path in root.glob('session-*') if path.suffix != '.tmp']
        if paths:
            try:
                if len(paths) == 1 and shared_read(paths[0]) == expected:
                    return paths[0]
            except OSError:
                # Atomic replacement may race this observation; retry the name.
                pass
        time.sleep(.005)
    raise AssertionError('recovery snapshot deadline: ' + str(root))


def native_tests(binary, work):
    lib = configure(binary)
    for path in (b'relative', b'C:relative', b'\\drive-relative'):
        assert not lib.dna_recovery_open(path), 'recovery requires a fully qualified path'
    for slash in (False, True):
        root = work / ('nested café 日本語-' + str(slash)) / 'state' / 'recovery'
        text_path = str(root)
        if slash:
            text_path = text_path.replace('\\', '/')
        state = lib.dna_recovery_open(text_path.encode('utf-8'))
        assert state
        try:
            assert not root.exists(), 'open must defer directory IO to worker'
            for index in range(50):
                text = (str(index) + '\n').encode() * 25000
                assert lib.dna_recovery_submit(state, text, len(text))
            saved = wait_snapshot(root, text)
            assert not lib.dna_recovery_error(state)
            private_acl(root)
            private_acl(saved)
            assert not list(root.glob('*.tmp'))
            assert lib.test_parent_limit(str(root).encode('utf-8')) == 1
        finally:
            lib.dna_recovery_close(state)
        assert list(root.iterdir()) == [], 'clean close removes session and temporary'
    direct = work / 'direct café 日本語'
    direct.mkdir()
    target = direct / 'snapshot'
    for index in range(64):
        payload = bytes((index, 0, 13, 10)) * (1024 + index)
        assert lib.test_snapshot(str(target).encode('utf-8'), payload, len(payload)) == 1
        assert target.read_bytes() == payload and not list(direct.glob('*.tmp'))
    private_acl(target)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = c.c_void_p
    kernel.GetProcessHandleCount.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
    count = c.c_uint32()
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    before = count.value
    for index in range(32):
        root = work / 'lifecycle'
        state = lib.dna_recovery_open(str(root).encode('utf-8'))
        assert state
        payload = ('snapshot-' + str(index)).encode()
        assert lib.dna_recovery_submit(state, payload, len(payload))
        wait_snapshot(root, payload)
        assert not lib.dna_recovery_error(state)
        lib.dna_recovery_close(state)
        assert list(root.iterdir()) == []
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    assert count.value == before, ('recovery handle leak', before, count.value)
    # Run the crashing DLL owner separately; this parent never holds its worker.
    crash = work / 'crash café 日本語' / 'state'
    subprocess.run([sys.executable, str(Path(__file__).resolve()), '--crash', str(binary), str(crash)],
        check=True, timeout=20)
    assert [path.read_bytes() for path in crash.iterdir()] == [b'crash snapshot\x00exact']
    print('PASS Windows recovery: coalescing, Unicode drive paths/backslashes/slashes, '
          'private ACLs, repeated atomic bytes, process-crash survival, cleanup and handles', flush=True)
    print('DURABILITY LIMIT: directory rec_sync remains errno95; file flush and write-through '
          'replacement prove process-crash persistence, not POSIX directory fsync or power-loss survival.', flush=True)


def main():
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first.')
    environment = sdk_environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-recovery-windows-') as temporary:
        work = Path(temporary)
        stage = work / 'stage'
        stage.mkdir()
        for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
            shutil.copytree(ROOT / 'src' / module, stage / module)
        for name in ('rec_io_windows.dyn', 'recovery.dyn', 'sync_desktop.dyn', 'sync_windows.dyn', 'clock.dyn'):
            shutil.copyfile(ROOT / 'src/native/dyn' / name, stage / name)
        sync = (ROOT / 'src/native/dyn/sync.dyn').read_text(encoding='utf-8').split('// Dyn\'s current executable entry point', 1)[0]
        (stage / 'sync.dyn').write_text(sync, encoding='utf-8')
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
                command = [sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler), 'build', str(stage), '--' + mode, '--output', str(binary)]
                if target == 'native':
                    command += ['--shared']
                else:
                    command += ['--target', target, '--emit-object', '--no-link']
                subprocess.run(command, check=True, env=environment, timeout=120)
                if target == 'native':
                    native_work = work / ('café 日本語-' + mode)
                    native_work.mkdir()
                    subprocess.run([sys.executable, str(Path(__file__).resolve()), '--native-library', str(binary), str(native_work)], check=True, env=environment, timeout=120)
                else:
                    print('PASS Windows recovery object: ' + target + ' ' + mode, flush=True)
    if os.name != 'nt':
        print('UNAVAILABLE Windows runtime; cross objects do not qualify recovery persistence.', flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--native-library':
        native_tests(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) == 4 and sys.argv[1] == '--crash':
        library = configure(Path(sys.argv[2]))
        root = Path(sys.argv[3])
        state = library.dna_recovery_open(str(root).encode('utf-8'))
        assert state
        payload = b'crash snapshot\x00exact'
        assert library.dna_recovery_submit(state, payload, len(payload))
        wait_snapshot(root, payload)
        assert not library.dna_recovery_error(state)
        os._exit(0)
    else:
        main()
