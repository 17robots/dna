#!/usr/bin/env python3
"""Each syntax buffer growth failure must permit retry of the same revision."""
import ctypes as c
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if '--child' not in sys.argv:
    interposer = ROOT / 'build/syntax-faults.so'
    subprocess.run([sys.executable, str(ROOT / 'scripts/native_test.py'),
                    'syntax_faults', str(interposer)], check=True)
    env = dict(os.environ, LD_PRELOAD=str(interposer), DNA_RENDER_TRACE='syntax-faults')
    subprocess.run([sys.executable, __file__, '--child'], env=env, check=True, timeout=20)
    sys.exit()

lib = c.CDLL(str(ROOT / 'build/deps/install/lib/libdna_native.so'), mode=c.RTLD_GLOBAL)
probe = c.CDLL(None)
probe.dna_test_syntax_arm.argtypes = [c.c_uint32]
probe.dna_test_syntax_failed.restype = c.c_uint32
lib.dna_syntax_open_named.argtypes = [c.c_char_p, c.c_char_p]
lib.dna_syntax_open_named.restype = c.c_void_p
lib.dna_syntax_update.argtypes = [c.c_void_p, c.c_char_p, c.c_uint32, c.c_uint64]
lib.dna_syntax_colors.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32, c.c_uint64]
lib.dna_syntax_close.argtypes = [c.c_void_p]
lib.dna_memory_snapshot.argtypes = [c.c_uint, c.c_void_p]

def complete(handle, text, revision, retry=False):
    output = c.create_string_buffer(len(text))
    deadline = time.monotonic() + 2
    while not lib.dna_syntax_colors(handle, output, len(text), revision):
        assert time.monotonic() < deadline, ('same revision did not recover', nth, revision)
        if retry:
            lib.dna_syntax_update(handle, text, len(text), revision)
        time.sleep(.001)
    assert output.raw[text.index(b'42')] == 6, 'number highlight missing'

for nth in range(1, 6):
    handle = lib.dna_syntax_open_named(os.fsencode(ROOT / 'build/test-languages'), b'json')
    assert handle, 'JSON syntax fixture is required'
    try:
        initial = b'{"n":42}'
        lib.dna_syntax_update(handle, initial, len(initial), 1)
        complete(handle, initial, 1)
        # All five buffers must grow beyond their initial 4096-byte capacity.
        larger = b'{"n":42,"s":"' + b'x' * 8192 + b'"}'
        probe.dna_test_syntax_arm(nth)
        lib.dna_syntax_update(handle, larger, len(larger), 2)
        deadline = time.monotonic() + 2
        while not probe.dna_test_syntax_failed():
            assert time.monotonic() < deadline, ('fault not reached', nth)
            time.sleep(.001)
        complete(handle, larger, 2, retry=True)
    finally:
        probe.dna_test_syntax_arm(0)
        lib.dna_syntax_close(handle)
    for category in (0, 4):
        totals = (c.c_uint64 * 7)()
        lib.dna_memory_snapshot(category, totals)
        assert totals[0] > 0 and totals[0] == totals[1] and totals[2] == 0 and totals[6] == 0, (nth, category, list(totals))
print('PASS all five syntax buffer growth failures: same-revision retry and allocation balance')
