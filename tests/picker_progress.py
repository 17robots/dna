#!/usr/bin/env python3
"""Prove cold picker rows publish before a stalled remainder of the actual scan."""
import ctypes as c
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
if '--child' not in sys.argv:
    interposer=ROOT/'build/picker-progress.so'
    subprocess.run([sys.executable,str(ROOT/'scripts/native_test.py'),'picker_progress',str(interposer)],check=True)
    subprocess.run([sys.executable,str(Path(__file__).resolve()),'--child'],check=True,
                   env=dict(os.environ,LD_PRELOAD=str(interposer)))
    raise SystemExit(0)
lib=c.CDLL(os.environ.get('DNA_PICKER_LIBRARY',str(ROOT/'build/deps/install/lib/libdna_native.so')))
lib.dna_picker_open.restype=c.c_void_p
lib.dna_picker_submit.argtypes=[c.c_void_p,c.c_char_p];lib.dna_picker_submit.restype=c.c_uint64
lib.dna_picker_poll.argtypes=[c.c_void_p,c.c_uint64,c.POINTER(c.c_size_t),c.POINTER(c.c_size_t),c.POINTER(c.c_uint32)]
lib.dna_picker_row.argtypes=[c.c_void_p,c.c_uint64,c.c_size_t,c.c_void_p,c.c_size_t];lib.dna_picker_row.restype=c.c_size_t
lib.dna_picker_close.argtypes=[c.c_void_p]
probe=c.CDLL(None)
with tempfile.TemporaryDirectory(prefix='dna-picker-progress-') as temporary:
    root=Path(temporary)
    for index in range(512): (root/f'file-{index:04d}').write_text('')
    worker=lib.dna_picker_open();assert worker
    try:
        probe.dna_picker_probe_begin()
        generation=lib.dna_picker_submit(worker,os.fsencode(root))
        deadline=time.monotonic()+5
        while not probe.dna_picker_probe_blocked():
            assert time.monotonic()<deadline,'metadata stall probe was not reached'
            time.sleep(.001)
        count,visited,flags=c.c_size_t(),c.c_size_t(),c.c_uint32()
        status=lib.dna_picker_poll(worker,generation,c.byref(count),c.byref(visited),c.byref(flags))
        assert status==2 and count.value>=64,'cold picker waited for the whole blocked scan before publishing rows'
        first=[]
        for index in range(count.value):
            row=c.create_string_buffer(512)
            assert lib.dna_picker_row(worker,generation,index,row,len(row))
            first.append(row.value)
        assert len(set(first))==len(first),'partial rows must remain coherent'
        probe.dna_picker_probe_release()
        while True:
            status=lib.dna_picker_poll(worker,generation,c.byref(count),c.byref(visited),c.byref(flags))
            if status==1: break
            assert time.monotonic()<deadline,'final picker snapshot stalled'
            time.sleep(.001)
        assert count.value==512
        for index,name in enumerate(first):
            row=c.create_string_buffer(512)
            assert lib.dna_picker_row(worker,generation,index,row,len(row))
            assert row.value==name,'published prefix changed while scan continued'
    finally:
        probe.dna_picker_probe_release()
        lib.dna_picker_close(worker)
print('PASS cold picker: coherent >=64-row prefix visible while scan blocked at file129, then complete512-row snapshot')
