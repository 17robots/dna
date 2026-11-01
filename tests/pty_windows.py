#!/usr/bin/env python3
"""Qualify production ConPTY hooks with real Windows processes and pipes."""
import ctypes as c
import os
from pathlib import Path
import re
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
use "std/sync" sync
use "std/time" time
extern fn rec_alloc "calloc"(count:usize,size:usize) rawptr
extern fn rec_malloc "malloc"(size:usize) rawptr
extern fn rec_free "free"(memory:rawptr)
extern fn string_length "strlen"(text:*const u8) usize
extern fn copy "memcpy"(output:*u8, input:*const u8, size:usize) rawptr
struct TtySize { rows, columns, width, height:u16 }
struct Terminal { pid,fd,input_fd,exit_fd,status,exited,read_closed:i32, platform:rawptr }
fn dna_watch(fd:i32,writing:i32) { _=fd
  _=writing }
fn dna_unwatch(fd:i32) { _=fd }
pub fn test_open(cwd,shell,command:*const u8) rawptr {
  terminal:=#cast(*Terminal,rec_alloc(1,#sizeof(Terminal)))
  if terminal==nil { return nil }
  terminal.fd = -1
  terminal.input_fd = -1
  terminal.exit_fd = -1
  if !terminal_start(terminal,cwd,shell,command) { rec_free(#cast(rawptr,terminal))
    return nil }
  return #cast(rawptr,terminal)
}
pub fn test_read(pointer:rawptr,bytes:*u8,size:usize) isize {
  terminal:=#cast(*Terminal,pointer)
  received:=proc_read(terminal.fd,bytes,size)
  if received==0 { terminal.read_closed=1 }
  return received
}
pub fn test_write(pointer:rawptr,bytes:*const u8,size:usize) isize {
  return proc_write((#cast(*Terminal,pointer)).input_fd,bytes,size)
}
pub fn test_resize(pointer:rawptr,columns,rows:u16) {
  size:=TtySize{columns:columns,rows:rows}
  terminal_resize_host(#cast(*Terminal,pointer),&size)
}
pub fn test_poll(pointer:rawptr) i32 {
  terminal:=#cast(*Terminal,pointer)
  if terminal_exit_native(terminal) { terminal.exited=1 }
  return terminal.exited
}
pub fn test_status(pointer:rawptr) i32 { return (#cast(*Terminal,pointer)).status }
pub fn test_needs_poll(pointer:rawptr) i32 {
  if terminal_needs_exit_poll(#cast(*Terminal,pointer)) { return 1 }
  return 0
}
pub fn test_close(pointer:rawptr) {
  terminal:=#cast(*Terminal,pointer)
  terminal_stop(terminal)
  terminal_stop(terminal)
  if terminal.platform!=nil || terminal.fd != -1 || terminal.input_fd != -1 { #panic("terminal_stop must invalidate") }
  rec_free(pointer)
}
fn main() {}
'''


def process_handles():
    class Handle(c.Structure):
        _fields_ = [("object", c.c_void_p), ("pid", c.c_size_t), ("handle", c.c_size_t),
                    ("access", c.c_uint32), ("creator", c.c_uint16), ("type", c.c_uint16),
                    ("attributes", c.c_uint32), ("reserved", c.c_uint32)]
    native = c.WinDLL('ntdll')
    native.NtQuerySystemInformation.argtypes = [c.c_uint32, c.c_void_p, c.c_uint32, c.POINTER(c.c_uint32)]
    size = 1024 * 1024
    while size <= 128 * 1024 * 1024:
        buffer = c.create_string_buffer(size)
        needed = c.c_uint32()
        result = native.NtQuerySystemInformation(64, buffer, size, c.byref(needed))
        if result == 0:
            count = c.c_size_t.from_buffer(buffer).value
            rows = (Handle * count).from_buffer(buffer, 2 * c.sizeof(c.c_size_t))
            return {row.handle: row.type for row in rows if row.pid == os.getpid()}
        size = max(size * 2, needed.value)
    raise AssertionError('handle diagnostic query failed')

def handle_type(handle):
    native = c.WinDLL('ntdll')
    native.NtQueryObject.argtypes = [c.c_void_p, c.c_uint32, c.c_void_p, c.c_uint32, c.c_void_p]
    buffer = c.create_string_buffer(4096)
    if native.NtQueryObject(handle, 2, buffer, len(buffer), None) == 0:
        length = c.c_uint16.from_buffer(buffer).value
        pointer = c.c_void_p.from_buffer(buffer, 8).value
        return c.wstring_at(pointer, length // 2)
    return 'unknown'


def native_tests(binary, work, mode):
    lib = c.CDLL(str(binary))
    lib.test_open.argtypes = [c.c_char_p] * 3
    lib.test_open.restype = c.c_void_p
    lib.test_read.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t]
    lib.test_read.restype = c.c_ssize_t
    lib.test_write.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t]
    lib.test_write.restype = c.c_ssize_t
    lib.test_resize.argtypes = [c.c_void_p, c.c_uint16, c.c_uint16]
    for name in ('test_close', 'test_poll', 'test_needs_poll', 'test_status'):
        getattr(lib, name).argtypes = [c.c_void_p]
    cwd = work / ('PTY café 日本語-' + mode)
    cwd.mkdir()
    helper = cwd / 'console.py'
    helper.write_text('''import os, subprocess, sys, time
assert all(os.isatty(fd) for fd in (0,1,2)), 'ConPTY must supply console stdio'
print('READY',flush=True)
for line in sys.stdin:
    request=line.strip()
    if request=='size':
        size=os.get_terminal_size(1)
        print('SIZE',size.columns,size.lines,flush=True)
    elif request=='tree':
        descendant=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        print('PIDS',os.getpid(),descendant.pid,flush=True)
    elif request=='flood':
        os.write(1,b'x'*4194304)
        print('FLOODED',flush=True)
    elif request=='exit':
        print('DONE',flush=True)
        break
''', encoding='utf-8')
    def open_terminal(command=b'', shell=None):
        if isinstance(command, str):
            command = command.encode('utf-8')
        terminal = lib.test_open(str(cwd).encode('utf-8'), shell, command)
        assert terminal, ('ConPTY startup', command, shell)
        return terminal
    storage = c.create_string_buffer(65536)
    ansi = re.compile(rb'\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)')
    def wait_for(terminal, pattern, timeout=15):
        output = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            got = lib.test_read(terminal, storage, len(storage))
            if got > 0:
                output.extend(storage.raw[:got])
                matched = re.search(pattern, ansi.sub(b'', bytes(output)))
                if matched:
                    return matched
            elif got < 0:
                assert got in (-11, -4), ('ConPTY read', got, bytes(output[-1000:]))
            time.sleep(.001)
        raise AssertionError(('ConPTY output deadline', pattern, {'exited': lib.test_poll(terminal), 'status': lib.test_status(terminal)}, bytes(output[-2000:])))
    def write(terminal, data):
        sent = 0
        deadline = time.monotonic() + 5
        while sent < len(data):
            assert time.monotonic() < deadline, 'ConPTY input deadline'
            got = lib.test_write(terminal, data[sent:], len(data) - sent)
            if got > 0:
                sent += got
            else:
                assert got in (-11, -4)
                time.sleep(.001)
    command = f'"{sys.executable}" "{helper}"'
    terminal = open_terminal(command)
    try:
        wait_for(terminal, rb'READY')
        assert lib.test_needs_poll(terminal) == 1
        lib.test_resize(terminal, 101, 37)
        # Resize runs independently while this thread services output.
        deadline = time.monotonic() + 10
        while True:
            write(terminal, b'size\r')
            result = wait_for(terminal, rb'SIZE\s+(\d+)\s+(\d+)')
            if result.groups() == (b'101', b'37'):
                break
            assert time.monotonic() < deadline, 'ConPTY native resize deadline'
        write(terminal, b'exit\r')
        wait_for(terminal, rb'DONE')
        deadline = time.monotonic() + 10
        while lib.test_poll(terminal) == 0:
            assert time.monotonic() < deadline, 'ConPTY exit inspection'
            # Keep draining until the process itself reports exited.
            _ = lib.test_read(terminal, storage, len(storage))
            time.sleep(.001)
        assert lib.test_needs_poll(terminal) == 0
    finally:
        lib.test_close(terminal)
    # The portable default /bin/sh selects the native Windows default shell.
    terminal = open_terminal(b'echo default-shell', b'/bin/sh')
    try:
        wait_for(terminal, rb'default-shell')
    finally:
        lib.test_close(terminal)
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    terminal = open_terminal("Write-Output 'quoted \"value\" café'", str(powershell).encode('utf-8'))
    try:
        wait_for(terminal, 'quoted "value" café'.encode('utf-8'))
    finally:
        lib.test_close(terminal)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [c.c_uint32, c.c_int, c.c_uint32]
    kernel.OpenProcess.restype = c.c_void_p
    kernel.WaitForSingleObject.argtypes = [c.c_void_p, c.c_uint32]
    kernel.CloseHandle.argtypes = [c.c_void_p]
    kernel.GetCurrentProcess.restype = c.c_void_p
    kernel.GetProcessHandleCount.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
    terminal = open_terminal(command)
    handles = []
    try:
        wait_for(terminal, rb'READY')
        write(terminal, b'tree\r')
        result = wait_for(terminal, rb'PIDS\s+(\d+)\s+(\d+)')
        handles = [kernel.OpenProcess(0x100000, 0, int(pid)) for pid in result.groups()]
        assert all(handles)
        # Do not drain this output before close: teardown must drain concurrently
        # with ClosePseudoConsole and must terminate the Job's descendants.
        write(terminal, b'flood\r')
        time.sleep(.05)
    finally:
        started = time.monotonic()
        lib.test_close(terminal)
        assert time.monotonic() - started < 10, 'ConPTY teardown blocked on output'
    try:
        for handle in handles:
            assert kernel.WaitForSingleObject(handle, 5000) == 0, 'ConPTY descendant survived close'
    finally:
        for handle in handles:
            kernel.CloseHandle(handle)
    count = c.c_uint32()
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    before = count.value
    handles_before = process_handles()
    for _ in range(8):
        terminal = open_terminal(b'echo lifecycle')
        lib.test_close(terminal)
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    handles_after = process_handles()
    added = [(handle, handle_type(handle), kind) for handle, kind in handles_after.items() if handle not in handles_before]
    assert count.value <= before + 2, ('ConPTY lifecycle handle leak', before, count.value, added)
    assert not lib.test_open(b'Z:\\dna-missing\\directory', None, b'echo invalid')
    print('PASS ConPTY: native output, Unicode cwd, default/custom shell, resize, exit, full-output teardown, descendant cancellation and handle cleanup (' + mode + ')', flush=True)


def main():
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first.')
    environment = sdk_environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-pty-windows-') as temporary:
        work = Path(temporary)
        stage = work / 'stage'
        stage.mkdir()
        for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
            shutil.copytree(ROOT / 'src' / module, stage / module)
        for source in ('process_windows.dyn', 'rec_io_windows.dyn', 'pty_windows.dyn', 'sync_desktop.dyn', 'sync_windows.dyn'):
            shutil.copyfile(ROOT / 'src/native/dyn' / source, stage / source)
        source = (ROOT / 'src/native/dyn/sync.dyn').read_text(encoding='utf-8')
        (stage / 'sync.dyn').write_text(source.split("// Dyn's current executable entry point", 1)[0], encoding='utf-8')
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
                    # Redirect all harness stdio: without STARTF_USESTDHANDLES,
                    # Windows duplicates these parent pipes into a ConPTY child.
                    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--native-library", str(binary), str(work), mode], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", env=environment, timeout=60)
                    print(result.stdout, end="", flush=True)
                    print(result.stderr, end="", file=sys.stderr, flush=True)
                    result.check_returncode()
                else:
                    print(f'PASS ConPTY production objects: {target} {mode}', flush=True)
    if os.name != 'nt':
        print('QUALIFICATION GAP: cross objects do not prove native ConPTY execution.', flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--native-library':
        native_tests(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4])
    else:
        main()
