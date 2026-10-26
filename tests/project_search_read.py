#!/usr/bin/env python3
"""Superseding a search between short reads must stop the old file immediately."""
import ctypes as c
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[1]
if '--child' not in sys.argv:
    probe = ROOT / 'build/search-read.so'
    subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'search_read', str(probe)], check=True)
    subprocess.run([sys.executable, __file__, '--child'], check=True, timeout=15,
                   env=dict(os.environ, LD_PRELOAD=str(probe), LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib')))
    raise SystemExit
probe = c.CDLL(None)
for name in ('waiting', 'reads'):
    getattr(probe, 'dna_test_search_'+name).restype = c.c_uint
lib = c.CDLL(os.environ.get('DNA_NATIVE_LIBRARY', str(ROOT/'build/deps/install/lib/libdna_native.so')))
lib.dna_search_open.restype = c.c_void_p
lib.dna_search_submit.argtypes = [c.c_void_p, c.c_char_p, c.c_char_p]
lib.dna_search_count.argtypes = [c.c_void_p, c.POINTER(c.c_int)]
lib.dna_search_count.restype = c.c_size_t
lib.dna_search_close.argtypes = [c.c_void_p]
worker = lib.dna_search_open()
assert worker
try:
    with tempfile.TemporaryDirectory() as directory:
        tree = Path(directory)
        (tree/'old').mkdir(); (tree/'new').mkdir()
        (tree/'old/file.txt').write_bytes(b'x'*1_000_000)
        probe.dna_test_search_arm()
        lib.dna_search_submit(worker, os.fsencode(tree/'old'), b'needle')
        deadline = time.monotonic()+5
        while not probe.dna_test_search_waiting():
            assert time.monotonic() < deadline, 'worker did not reach file read'
            time.sleep(.001)
        lib.dna_search_submit(worker, os.fsencode(tree/'new'), b'needle')
        probe.dna_test_search_release()
        deadline = time.monotonic()+5
        while True:
            status = c.c_int(); count = lib.dna_search_count(worker, c.byref(status))
            if status.value != 1:
                break
            assert time.monotonic() < deadline, 'replacement search did not complete'
            time.sleep(.001)
        assert status.value == 0 and count == 0
        assert probe.dna_test_search_reads() == 1, ('cancelled worker kept reading', probe.dna_test_search_reads())
finally:
    probe.dna_test_search_release()
    lib.dna_search_close(worker)
print('PASS superseded search stops after its in-flight read')
