#!/usr/bin/env python3
"""Background replacement is atomic, private, coalesced, and cleaned on exit."""
import ctypes as c
import os
from pathlib import Path
import tempfile
import time
lib=c.CDLL(os.environ.get('DNA_NATIVE_LIBRARY',str(Path(__file__).resolve().parents[1]/'build/deps/install/lib/libdna_native.so')))
lib.dna_recovery_open.argtypes=[c.c_char_p];lib.dna_recovery_open.restype=c.c_void_p
lib.dna_recovery_submit.argtypes=[c.c_void_p,c.c_char_p,c.c_size_t]
lib.dna_recovery_error.argtypes=[c.c_void_p]
lib.dna_recovery_close.argtypes=[c.c_void_p]
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)/'nested/recovery'
    state=lib.dna_recovery_open(os.fsencode(root));assert state
    try:
        assert not root.exists(), "opening recovery must not perform directory IO on UI thread"
        for index in range(50):
            text=(str(index)+'\n').encode()*350000
            assert lib.dna_recovery_submit(state,text,len(text))
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            paths=[p for p in root.glob('session-*') if p.suffix != '.tmp']
            if paths and paths[0].read_bytes()==text: break
            time.sleep(.005)
        path=next(p for p in root.glob('session-*') if p.suffix != '.tmp')
        assert path.stat().st_mode&0o777 == 0o600
        assert path.read_bytes()==text and not lib.dna_recovery_error(state)
    finally:lib.dna_recovery_close(state)
    assert list(root.iterdir())==[]
print('PASS coalesced atomic session recovery, private permissions, clean shutdown')

# A hard process exit leaves the last complete file for :recoveries.
import subprocess
with tempfile.TemporaryDirectory() as directory:
    script=r'''
import ctypes as c, os, pathlib, time
lib=c.CDLL(os.environ['DNA_NATIVE_LIBRARY'])
lib.dna_recovery_open.argtypes=[c.c_char_p];lib.dna_recovery_open.restype=c.c_void_p
lib.dna_recovery_submit.argtypes=[c.c_void_p,c.c_char_p,c.c_size_t]
root=pathlib.Path(os.environ['DNA_RECOVERY_TEST'])
state=lib.dna_recovery_open(os.fsencode(root));assert state
assert lib.dna_recovery_submit(state,b'crash snapshot',14)
deadline=time.monotonic()+3
while time.monotonic()<deadline:
    if any(p.read_bytes()==b'crash snapshot' for p in root.glob('session-*') if p.suffix != '.tmp'):os._exit(0)
    time.sleep(.005)
os._exit(1)
'''
    library=os.environ.get('DNA_NATIVE_LIBRARY',str(Path(__file__).resolve().parents[1]/'build/deps/install/lib/libdna_native.so'))
    subprocess.run(['python3','-c',script],env=dict(os.environ,DNA_NATIVE_LIBRARY=library,DNA_RECOVERY_TEST=directory),check=True,timeout=5)
    assert [p.read_bytes() for p in Path(directory).iterdir()]==[b'crash snapshot']
print('PASS recovery survives abrupt process exit')
