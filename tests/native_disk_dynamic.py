#!/usr/bin/env python3
"""Production disk worker ownership and notifications beyond the old slot bound."""
import ctypes as c
import os
import resource
from pathlib import Path
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
if os.environ.get('DNA_DISK_DYNAMIC_CHILD')!='1':
    subprocess.run([sys.executable,__file__],check=True,timeout=30,
                   env=dict(os.environ,DNA_DISK_DYNAMIC_CHILD='1',DNA_RENDER_TRACE='native-disk-dynamic'))
    raise SystemExit
library=Path(os.environ.get('DNA_DISK_LIBRARY',ROOT/'build/deps/install/lib/libdna_native.so'))
lib=c.CDLL(str(library))
lib.dna_disk_open.restype=c.c_void_p
lib.dna_disk_close.argtypes=[c.c_void_p]
class Ready(c.Structure):
    _fields_=[('index',c.c_size_t),('identity',c.c_uint64)]
lib.dna_disk_next_ready.argtypes=[c.c_void_p,c.POINTER(Ready)]
lib.dna_disk_next_ready.restype=c.c_int
ready_seen=set()
lib.dna_disk_watch_checked.argtypes=[c.c_void_p,c.c_size_t,c.c_uint64,c.c_char_p,c.c_void_p,c.c_size_t]
lib.dna_disk_watch_checked.restype=c.c_int
lib.dna_disk_pending_at.argtypes=[c.c_void_p,c.c_size_t,c.c_uint64]
lib.dna_disk_pending_at.restype=c.c_ssize_t
lib.dna_disk_take_at.argtypes=[c.c_void_p,c.c_size_t,c.c_uint64,c.c_void_p,c.c_size_t]
lib.dna_disk_take_at.restype=c.c_int
lib.dna_memory_snapshot.argtypes=[c.c_uint32,c.POINTER(c.c_uint64)]

def await_bytes(worker,index,identity,expected):
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        ready=Ready()
        while lib.dna_disk_next_ready(worker,c.byref(ready)):
            ready_seen.add((ready.index,ready.identity))
        if (index,identity) not in ready_seen:
            time.sleep(.002)
            continue
        ready_seen.discard((index,identity))
        pending=lib.dna_disk_pending_at(worker,index,identity)
        if pending:
            out=c.create_string_buffer(max(len(expected)+1,4096))
            status=lib.dna_disk_take_at(worker,index,identity,out,len(out))
            if status==1 and out.value==expected:return
            assert status in (1,5),(index,pending,status)
        time.sleep(.002)
    raise AssertionError(('disk notification timeout',index,identity,expected))

before=(c.c_uint64*7)();lib.dna_memory_snapshot(3,before)
fds_before=len(list(Path('/proc/self/fd').iterdir()))
with tempfile.TemporaryDirectory(prefix='dna-disk-many-') as directory:
    paths=[]
    worker=lib.dna_disk_open();assert worker
    try:
        assert lib.dna_disk_watch_checked(worker,c.c_size_t(-1).value,0,None,None,0)==1
        for index in range(96):
            parent=Path(directory)/str(index);parent.mkdir()
            path=parent/'watched.txt';path.write_bytes(b'old\n');paths.append(path)
            assert lib.dna_disk_watch_checked(worker,index,index+1,os.fsencode(path),b'old\n',4)==1
        # A failed growth request and invalid input leave prior registrations live.
        assert lib.dna_disk_watch_checked(worker,c.c_size_t(-1).value,999,os.fsencode(paths[0]),b'',0)==0
        # Force a real allocator refusal without asking the kernel to commit a
        # giant array. Keep enough address-space headroom for the live worker.
        limits=resource.getrlimit(resource.RLIMIT_AS)
        vm_line=next(line for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('VmSize:'))
        ceiling=int(vm_line.split()[1])*1024+32*1024*1024
        if limits[1]!=resource.RLIM_INFINITY:ceiling=min(ceiling,limits[1])
        resource.setrlimit(resource.RLIMIT_AS,(ceiling,limits[1]))
        try:
            assert lib.dna_disk_watch_checked(worker,1048575,999,os.fsencode(paths[0]),b'',0)==0
        finally:resource.setrlimit(resource.RLIMIT_AS,limits)
        assert lib.dna_disk_watch_checked(worker,95,96,None,b'',0)==0
        assert lib.dna_disk_watch_checked(worker,95,96,os.fsencode(paths[95]),None,1)==0
        for index,path in enumerate(paths):path.write_bytes(f'updated-{index}\n'.encode())
        for index in range(96):await_bytes(worker,index,index+1,f'updated-{index}\n'.encode())
        # Parent-directory watches must keep following atomic file replacement.
        for index,path in enumerate(paths):
            temporary=path.with_suffix('.tmp');temporary.write_bytes(f'renamed-{index}\n'.encode());temporary.replace(path)
        for index in range(96):await_bytes(worker,index,index+1,f'renamed-{index}\n'.encode())
        for index in range(1,96,2):
            assert lib.dna_disk_watch_checked(worker,index,0,None,None,0)==1
            paths[index].write_bytes(b'unregistered\n')
            assert lib.dna_disk_pending_at(worker,index,index+1)==0
        # Reusing a high slot discards the old identity and its pending result.
        replacement=Path(directory)/'replacement.txt';replacement.write_bytes(b'replacement\n')
        # Re-register while a ready link may still be queued: stale indices must
        # retain queue linkage and never expose the old identity as current.
        for identity in range(2000,2050):
            assert lib.dna_disk_watch_checked(worker,95,identity,os.fsencode(replacement),b'',0)==1
        assert lib.dna_disk_watch_checked(worker,95,1000,os.fsencode(replacement),b'',0)==1
        assert lib.dna_disk_pending_at(worker,95,96)==0
        await_bytes(worker,95,1000,b'replacement\n')
    finally:lib.dna_disk_close(worker)
after=(c.c_uint64*7)();lib.dna_memory_snapshot(3,after)
assert after[2]==before[2] and after[6]==before[6],(list(before),list(after))
assert after[0]-before[0]==after[1]-before[1],(list(before),list(after))
assert len(list(Path('/proc/self/fd').iterdir()))==fds_before
print('PASS native disk: 96 independent directory watches, growth rollback, queued readiness, updates, atomic replacement, unregister, identity reuse, balanced ownership and descriptors')
