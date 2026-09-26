#!/usr/bin/env python3
"""Tracing must account for threaded native allocation ownership after teardown."""
import ctypes
import os
from pathlib import Path
import runpy
ROOT = Path(__file__).resolve().parents[1]
os.environ['DNA_RENDER_TRACE'] = 'native-memory-test'
runpy.run_path(str(ROOT/'tests/resource_cycles.py'), run_name='__main__')
lib = ctypes.CDLL(str(ROOT/'build/deps/install/lib/libdna_native.so'))
lib.dna_memory_snapshot.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_ulonglong)]
for category in range(5):
    totals = (ctypes.c_ulonglong * 7)()
    lib.dna_memory_snapshot(category, totals)
    assert totals[0] == totals[1] and totals[2] == 0 and totals[6] == 0, (category, list(totals))
    assert totals[0] > 0, ('allocation category was not exercised',category)
    print('PASS native memory category', category, 'allocations', totals[0], 'peak bytes', totals[3])
