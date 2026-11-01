#!/usr/bin/env python3
"""Qualify native Windows directory notifications and framed rescan transport."""
import ctypes as c
import os
from pathlib import Path
import shutil
import struct
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
extern fn copy "memcpy"(output:*u8,input:*const u8,size:usize) rawptr
struct DiskEvent { descriptor:i32, mask,cookie,length:u32 }
fn dna_watch(fd:i32,writing:i32) { _=fd
  _=writing }
fn dna_unwatch(fd:i32) { _=fd }
fn rec_lock(lock:rawptr) { _=sync_mutex_lock(lock) }
fn rec_unlock(lock:rawptr) { _=sync_mutex_unlock(lock) }
pub fn test_open() i32 { return disk_inotify(526336) }
pub fn test_add(queue:i32,path:*const u8) i32 { return disk_add(queue,path,16781262) }
pub fn test_remove(queue,descriptor:i32) i32 { return disk_remove(queue,descriptor) }
pub fn test_live(queue,descriptor:i32) i32 {
  if disk_target_watch(queue,nil,descriptor) { return 1 }
  return 0
}
pub fn test_read(queue:i32,output:*u8,capacity:usize) isize { return proc_read(queue,output,capacity) }
pub fn test_close(queue:i32) { disk_changes_close(queue) }
pub fn test_pressure(fd:i32,count:usize) i32 {
  rec_lock(#cast(rawptr,&disk_windows_lock))
  defer rec_unlock(#cast(rawptr,&disk_windows_lock))
  queue:=disk_windows_find(fd)
  if queue==nil { return 0 }
  for index in 0..count { disk_windows_emit(queue,100000+#cast(i32,index),256) }
  if queue.failed { return 0 }
  return 1
}
pub fn test_seek(path:*const u8) i32 {
  fd:=rec_open(path,0,0)
  if fd<0 { return 0 }
  position:=disk_lseek(fd,2,0)
  _=rec_close(fd)
  if position==2 && disk_path_separator(47) && disk_path_separator(92) && !disk_path_separator(58) { return 1 }
  return 0
}
fn main() {}
'''


def native_tests(binary, work):
    lib = c.CDLL(str(binary))
    lib.test_add.argtypes = [c.c_int, c.c_char_p]
    for name in ('test_remove', 'test_live'):
        getattr(lib, name).argtypes = [c.c_int, c.c_int]
    lib.test_close.argtypes = [c.c_int]
    lib.test_read.argtypes = [c.c_int, c.c_void_p, c.c_size_t]
    lib.test_read.restype = c.c_ssize_t
    lib.test_pressure.argtypes = [c.c_int, c.c_size_t]
    lib.test_seek.argtypes = [c.c_char_p]
    storage = c.create_string_buffer(8192)
    def read(queue):
        got = lib.test_read(queue, storage, len(storage))
        if got < 0:
            assert got in (-11, -4), ('notification transport', got)
            return []
        assert got > 0 and got % 16 == 0, ('partial notification record', got)
        records = list(struct.iter_unpack('<iIII', storage.raw[:got]))
        assert all(cookie == 0 and length == 0 for _, _, cookie, length in records), records
        return [(descriptor, mask) for descriptor, mask, _, _ in records]
    def drain(queue):
        output = []
        while True:
            records = read(queue)
            if not records:
                return output
            output.extend(records)
    def settle(queue):
        quiet = time.monotonic() + .1
        deadline = time.monotonic() + 5
        while time.monotonic() < quiet:
            assert time.monotonic() < deadline, 'notification stream never quiesced'
            if drain(queue):
                quiet = time.monotonic() + .1
            time.sleep(.005)
    def wait_for(queue, descriptor, mask=256):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            records = drain(queue)
            if any(fd == descriptor and (bits & mask) != 0 for fd, bits in records):
                return records
            time.sleep(.005)
        raise AssertionError(('directory event deadline', descriptor, mask))
    def child(code, *paths):
        subprocess.run([sys.executable, '-c', code, *(str(path) for path in paths)], check=True, timeout=10)
    root = work / 'watched café 日本語'
    root.mkdir()
    source = root / 'document.txt'
    source.write_bytes(b'initial')
    queue = lib.test_open()
    assert queue >= 0
    try:
        descriptor = lib.test_add(queue, str(root).encode('utf-8'))
        assert descriptor >= 0
        assert lib.test_add(queue, str(root).encode('utf-8')) == descriptor, 'duplicate registrations must share owner'
        assert lib.test_live(queue, descriptor) == 1
        settle(queue)
        child('import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(b"inplace-write")', source)
        wait_for(queue, descriptor)
        settle(queue)
        child('import pathlib,sys,os;p=pathlib.Path(sys.argv[1]);t=p.with_suffix(".new");t.write_bytes(b"replacement");os.replace(t,p)', source)
        wait_for(queue, descriptor)
        settle(queue)
        created = root / 'created 空間.txt'
        child('import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(b"created")', created)
        wait_for(queue, descriptor)
        settle(queue)
        child('import pathlib,sys;pathlib.Path(sys.argv[1]).unlink()', created)
        wait_for(queue, descriptor)
        assert lib.test_seek(str(source).encode('utf-8')) == 1
        settle(queue)
        renamed = work / 'renamed watched directory'
        child('import pathlib,sys;pathlib.Path(sys.argv[1]).rename(sys.argv[2])', root, renamed)
        wait_for(queue, descriptor, 3072)
        assert lib.test_live(queue, descriptor) == 0, 'renamed directory must invalidate the original pathname'
        root.mkdir()
        fresh = lib.test_add(queue, str(root).encode('utf-8'))
        assert fresh >= 0 and fresh != descriptor and lib.test_live(queue, fresh) == 1
        child('import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(b"new directory")', root / 'new.txt')
        wait_for(queue, fresh)
        assert lib.test_remove(queue, descriptor) == 0
        assert lib.test_remove(queue, descriptor) == -1
        settle(queue)
        # Fill the actual nonblocking message pipe. Full writes coalesce; a
        # successful read must never contain a fragment of a following record.
        assert lib.test_pressure(queue, 20000) == 1
        records = drain(queue)
        pressure = [fd for fd, mask in records if fd >= 100000]
        assert pressure and len(pressure) < 20000, 'pressure fixture must fill and coalesce the event queue'
        assert pressure == list(range(100000, 100000 + len(pressure))), 'message pipe lost framing/order'
        assert all(mask == 256 for fd, mask in records if fd >= 100000)
        child('import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(b"after pressure")', root / 'after.txt')
        wait_for(queue, fresh)
        assert lib.test_live(queue, fresh) == 1
        assert lib.test_remove(queue, fresh) == 0
    finally:
        lib.test_close(queue)
        lib.test_close(queue)
    # Registrations deliberately exceed WaitForMultipleObjects' 64-handle cap.
    many = work / 'many'
    many.mkdir()
    directories = [many / str(index) for index in range(96)]
    for directory in directories:
        directory.mkdir()
    queue = lib.test_open()
    assert queue >= 0
    try:
        registered = {lib.test_add(queue, str(path).encode('utf-8')) for path in directories}
        assert len(registered) == 96 and min(registered) >= 0
        for directory in directories:
            (directory / 'event.txt').write_bytes(b'native event')
        observed = set()
        deadline = time.monotonic() + 10
        while not registered <= observed:
            assert time.monotonic() < deadline, ('many registrations lost events', registered - observed)
            observed.update(fd for fd, _ in drain(queue))
            time.sleep(.005)
        for descriptor in registered:
            assert lib.test_remove(queue, descriptor) == 0
    finally:
        lib.test_close(queue)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = c.c_void_p
    kernel.GetProcessHandleCount.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
    count = c.c_uint32()
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    before = count.value
    for _ in range(32):
        queue = lib.test_open()
        assert queue >= 0
        descriptor = lib.test_add(queue, str(root).encode('utf-8'))
        assert descriptor >= 0
        (root / 'cancel.txt').write_bytes(b'cancel while work is pending')
        lib.test_close(queue)
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(count))
    assert count.value == before, ('directory watch handle leak', before, count.value)
    print('PASS Windows disk: native writes/replacements/create/delete, parent invalidation, 96 registrations, message framing/coalescing and cancellation/handle cleanup', flush=True)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--native-library':
        native_tests(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first.')
    environment = sdk_environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-disk-windows-') as temporary:
        work = Path(temporary)
        stage = work / 'stage'
        stage.mkdir()
        for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
            shutil.copytree(ROOT / 'src' / module, stage / module)
        for source in ('process_windows.dyn', 'rec_io_windows.dyn', 'install_windows.dyn', 'disk_windows.dyn', 'sync_desktop.dyn', 'sync_windows.dyn', 'clock.dyn'):
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
                    runtime = work / ('native-' + mode)
                    runtime.mkdir()
                    subprocess.run([sys.executable, str(Path(__file__).resolve()), '--native-library', str(binary), str(runtime)], check=True, timeout=90, env=environment)
                else:
                    print(f'PASS Windows disk production objects: {target} {mode}', flush=True)
    if os.name != 'nt':
        print('QUALIFICATION GAP: cross objects do not prove native Windows directory notifications.', flush=True)


if __name__ == '__main__':
    main()
