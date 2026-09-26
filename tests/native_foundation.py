#!/usr/bin/env python3
"""Allocation ownership and thread result/TLS checks through the exported ABI."""
import ctypes as c
import os
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
if not os.environ.get('DNA_FOUNDATION_CHILD'):
    for trace in ('', 'native-foundation'):
        subprocess.run([sys.executable, __file__], check=True, timeout=15,
                       env=dict(os.environ, DNA_FOUNDATION_CHILD='1', DNA_RENDER_TRACE=trace))
    raise SystemExit
lib = c.CDLL(str(ROOT/'build/deps/install/lib/libdna_native.so'))
lib.dna_memory_alloc.argtypes = [c.c_size_t,c.c_uint]
lib.dna_memory_alloc.restype = c.c_void_p
lib.dna_memory_calloc.argtypes = [c.c_size_t,c.c_size_t,c.c_uint]
lib.dna_memory_calloc.restype = c.c_void_p
lib.dna_memory_realloc.argtypes = [c.c_void_p,c.c_size_t,c.c_uint]
lib.dna_memory_realloc.restype = c.c_void_p
lib.dna_memory_free.argtypes = [c.c_void_p]
lib.dna_memory_snapshot.argtypes = [c.c_uint,c.POINTER(c.c_uint64)]
maximum = c.c_size_t(-1).value
for size in (1,15,16,17,4096):
    pointer = lib.dna_memory_calloc(1,size,0)
    assert pointer and pointer % 16 == 0
    assert c.string_at(pointer,size) == bytes(size)
    c.memset(pointer,0x5a,size)
    assert not lib.dna_memory_realloc(pointer,maximum,0)
    assert c.string_at(pointer,size) == b'Z'*size
    grown = lib.dna_memory_realloc(pointer,size+37,0)
    assert grown and grown%16 == 0 and c.string_at(grown,size) == b'Z'*size
    lib.dna_memory_free(grown)
assert not lib.dna_memory_calloc(maximum,2,0)
lib.dna_memory_free(None)
entry = c.CFUNCTYPE(c.c_int,c.c_void_p)
lib.dna_thread_create.argtypes = [entry,c.c_void_p]
lib.dna_thread_create.restype = c.c_void_p
lib.dna_thread_join.argtypes = [c.c_void_p,c.POINTER(c.c_int)]
lib.dna_ticks.restype = c.c_uint64
libc = c.CDLL(None)
libc.__errno_location.restype = c.POINTER(c.c_int)
main_errno = c.addressof(libc.__errno_location().contents)
seen = []
@entry
def worker(context):
    seen.append(c.addressof(libc.__errno_location().contents))
    previous = lib.dna_ticks()
    for _ in range(100):
        current = lib.dna_ticks()
        assert current >= previous
        previous = current
    return context
workers = [lib.dna_thread_create(worker,i+7) for i in range(16)]
assert all(workers)
for i,thread in enumerate(workers):
    status = c.c_int()
    lib.dna_thread_join(thread,c.byref(status))
    assert status.value == i+7
assert len(seen)==16 and all(address != main_errno for address in seen)
if os.environ['DNA_RENDER_TRACE']:
    totals=(c.c_uint64*7)()
    lib.dna_memory_snapshot(0,totals)
    assert totals[0]==totals[1] and totals[2]==0 and totals[6]==0, list(totals)
print('PASS native allocation alignment/overflow/realloc ownership, thread TLS/results, monotonic ticks; trace=',bool(os.environ['DNA_RENDER_TRACE']))
