#!/usr/bin/env python3
"""Compile the real Windows process adapter; exercise it on native Windows.

Cross objects check ABI compilation only. Native tests cover byte pipes, process
ownership, Unicode cwd, exit status, descendant cancellation, and handle leaks.
"""
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

FIXTURE = r'''
#link("kernel32")
#link("ucrt")
extern fn rec_alloc "calloc"(count:usize,size:usize) rawptr
extern fn rec_free "free"(memory:rawptr)
extern fn string_length "strlen"(text:*const u8) usize
extern fn copy "memcpy"(output:*u8, input:*const u8, size:usize) rawptr
fn dna_watch(fd:i32, writing:i32) { _=fd
  _=writing }
fn dna_unwatch(fd:i32) { _=fd }
pub fn test_open(command:*const u8, directory:*const u8, shell:i32) rawptr {
  first:=proc_open(command, directory, shell!=0)
  if first.pid==0 { return nil }
  owned:=#cast(*OwnedProcess, rec_alloc(1, #sizeof(OwnedProcess)))
  if owned==nil { proc_close(&first)
    return nil }
  owned.*=proc_take(&first)
  proc_close(&first)
  proc_close(&first)
  if first.pid!=0 || first.input != -1 { #panic("take must invalidate owner") }
  return #cast(rawptr, owned)
}
pub fn test_read(pointer:rawptr, stream:i32, bytes:*u8, size:usize) isize {
  owned:=#cast(*OwnedProcess, pointer)
  fd:=owned.output
  if stream==2 { fd=owned.error }
  return proc_read(fd, bytes, size)
}
pub fn test_write(pointer:rawptr, bytes:*const u8, size:usize) isize {
  return proc_write((#cast(*OwnedProcess,pointer)).input, bytes, size)
}
pub fn test_finish_input(pointer:rawptr) {
  owned:=#cast(*OwnedProcess,pointer)
  _=rec_close(owned.input)
  owned.input = -1
}
pub fn test_peek(pointer:rawptr) i32 { return proc_peek(#cast(*OwnedProcess,pointer)) }
pub fn test_close(pointer:rawptr) {
  owned:=#cast(*OwnedProcess,pointer)
  proc_close(owned)
  proc_close(owned)
  rec_free(pointer)
}
pub fn test_layout() i32 {
  if #sizeof(WinProcStartup)!=112 || #sizeof(WinProcLimits)!=144 { return 0 }
  return 1
}
fn main() {}
'''


def native_tests(binary, work):
    lib = c.CDLL(str(binary))
    lib.test_open.argtypes = [c.c_char_p, c.c_char_p, c.c_int]
    lib.test_open.restype = c.c_void_p
    for name in ('test_peek', 'test_close', 'test_finish_input'):
        getattr(lib, name).argtypes = [c.c_void_p]
    lib.test_read.argtypes = [c.c_void_p, c.c_int, c.c_void_p, c.c_size_t]
    lib.test_read.restype = c.c_ssize_t
    lib.test_write.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t]
    lib.test_write.restype = c.c_ssize_t
    assert lib.test_layout() == 1, 'Windows native structure layout'
    cwd = work / 'Unicode 空間'
    cwd.mkdir(exist_ok=True)
    helper = cwd / 'child.py'
    helper.write_text('''import os, subprocess, sys, time, msvcrt
for descriptor in (0,1,2): msvcrt.setmode(descriptor, os.O_BINARY)
if len(sys.argv)>1 and sys.argv[1]=='tree':
    descendant=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(os.getpid(), descendant.pid, flush=True)
    time.sleep(60)
else:
    while True:
        block=os.read(0,8192)
        if not block: break
        os.write(1,block)
        os.write(2,block)
''', encoding='utf-8')
    # cmd's command is itself enclosed by proc_open's /S /C outer quotes.
    command = f'"{sys.executable}" "{helper}"'
    def open_child(command, shell=True):
        child = lib.test_open(command.encode('utf-8'), str(cwd).encode('utf-8'), int(shell))
        assert child, ('CreateProcessW failed', command)
        return child
    def wait_exit(child):
        deadline = time.monotonic() + 10
        while lib.test_peek(child) == 0:
            assert time.monotonic() < deadline, 'child exit deadline'
            time.sleep(.001)
        return lib.test_peek(child)
    def drain(child, expected=None):
        output, errors = bytearray(), bytearray()
        storage = c.create_string_buffer(65536)
        deadline = time.monotonic() + 15
        closed = set()
        while len(closed) != 2:
            assert time.monotonic() < deadline, 'pipe drain deadline'
            for stream, target in ((1, output), (2, errors)):
                if stream in closed:
                    continue
                got = lib.test_read(child, stream, storage, len(storage))
                if got > 0:
                    target.extend(storage.raw[:got])
                elif got == 0:
                    closed.add(stream)
                else:
                    assert got in (-11, -4), ('pipe read', got)
            time.sleep(.001)
        return bytes(output), bytes(errors)
    child = open_child(command)
    payload = bytes(range(256)) * 8192
    sent = 0
    output, errors = bytearray(), bytearray()
    storage = c.create_string_buffer(65536)
    deadline = time.monotonic() + 20
    try:
        while sent < len(payload) or len(output) < len(payload) or len(errors) < len(payload):
            assert time.monotonic() < deadline, 'simultaneous pipe IO blocked'
            if sent < len(payload):
                block = payload[sent:sent+65536]
                wrote = lib.test_write(child, block, len(block))
                assert wrote >= 0 or wrote in (-11, -4), ('pipe write', wrote)
                if wrote > 0:
                    sent += wrote
                if sent == len(payload):
                    lib.test_finish_input(child)
            for stream, target in ((1, output), (2, errors)):
                got = lib.test_read(child, stream, storage, len(storage))
                assert got >= 0 or got in (-11, -4), ('pipe read', got)
                if got > 0:
                    target.extend(storage.raw[:got])
            time.sleep(.001)
        assert bytes(output) == payload and bytes(errors) == payload, 'binary pipe bytes changed'
        assert wait_exit(child) == 1
    finally:
        lib.test_close(child)
    for status, expected in ((0, 1), (7, 2), (259, 2)):
        child = open_child(f'exit /b {status}')
        try:
            lib.test_finish_input(child)
            assert wait_exit(child) == expected
        finally:
            lib.test_close(child)
    child = open_child(sys.executable, shell=False)
    try:
        source = b"import os; os.write(1,os.getcwd().encode('utf-8'))\n"
        assert lib.test_write(child, source, len(source)) == len(source)
        lib.test_finish_input(child)
        output, errors = drain(child)
        assert wait_exit(child) == 1 and output.strip() and not errors
    finally:
        lib.test_close(child)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [c.c_uint32, c.c_int, c.c_uint32]
    kernel.OpenProcess.restype = c.c_void_p
    kernel.WaitForSingleObject.argtypes = [c.c_void_p, c.c_uint32]
    kernel.CloseHandle.argtypes = [c.c_void_p]
    kernel.GetCurrentProcess.restype = c.c_void_p
    kernel.GetProcessHandleCount.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
    child = open_child(command + ' tree')
    line = bytearray()
    deadline = time.monotonic() + 10
    try:
        while b'\n' not in line:
            assert time.monotonic() < deadline, 'descendant spawn deadline'
            got = lib.test_read(child, 1, storage, len(storage))
            if got > 0:
                line.extend(storage.raw[:got])
            else:
                assert got in (-11, -4)
                time.sleep(.001)
        pids = [int(value) for value in line.split()]
        handles = [kernel.OpenProcess(0x100000, 0, pid) for pid in pids]
        assert len(handles) == 2 and all(handles)
    finally:
        lib.test_close(child)
    try:
        for handle in handles:
            assert kernel.WaitForSingleObject(handle, 5000) == 0, 'Job descendant survived close'
    finally:
        for handle in handles:
            kernel.CloseHandle(handle)
    count = c.c_uint32()
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    before = count.value
    for _ in range(40):
        child = open_child('exit /b 0')
        lib.test_close(child)
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    assert count.value <= before + 2, ('process handle leak', before, count.value)
    missing = lib.test_open(b'Z:\\dna-missing\\none.exe', str(cwd).encode(), 0)
    assert not missing, 'missing executable must fail synchronously'
    print('PASS Windows process: Unicode, binary simultaneous pipes, transfer, exits, Job descendants, handle cleanup', flush=True)


def main():
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first.')
    environment = sdk_environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-process-windows-') as temporary:
        work = Path(temporary)
        stage = work / 'stage'
        stage.mkdir()
        for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
            shutil.copytree(ROOT / 'src' / module, stage / module)
        for source in ('process_windows.dyn', 'rec_io_windows.dyn'):
            shutil.copyfile(ROOT / 'src/native/dyn' / source, stage / source)
        (stage / 'main.dyn').write_text(FIXTURE)
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
                    native_tests(binary, work)
                else:
                    print(f'PASS Windows process production object: {target} {mode}', flush=True)
    if os.name != 'nt':
        print('QUALIFICATION GAP: cross objects do not prove native Windows process execution.', flush=True)


if __name__ == '__main__':
    main()
