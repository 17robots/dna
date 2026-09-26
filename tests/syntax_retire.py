#!/usr/bin/env python3
"""Bounded retirement with a blocked close callback in an interposable library."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if '--child' not in sys.argv:
    probe = ROOT / 'build/syntax-retire.so'
    subprocess.run([sys.executable, str(ROOT / 'scripts/native_test.py'),
                    'syntax_retire', str(probe)], check=True)
    subprocess.run([sys.executable, __file__, '--child'], check=True, timeout=10,
                   env=dict(os.environ, LD_PRELOAD=str(probe),
                            LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib')))
else:
    run = ctypes.CDLL(None).dna_test_syntax_retire
    run.argtypes = [ctypes.c_char_p]
    run.restype = None
    run(os.fsencode(ROOT / 'build/test-languages'))
