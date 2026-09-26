#!/usr/bin/env python3
"""Small documents must not reserve maximum-sized syntax buffers per worker."""
import ctypes as c
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ['DNA_RENDER_TRACE'] = 'syntax-memory-test'
lib = c.CDLL(str(ROOT / 'build/deps/install/lib/libdna_native.so'))
lib.dna_syntax_open_named.argtypes = [c.c_char_p, c.c_char_p]
lib.dna_syntax_open_named.restype = c.c_void_p
lib.dna_syntax_update.argtypes = [c.c_void_p, c.c_char_p, c.c_uint32, c.c_uint64]
lib.dna_syntax_colors.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32, c.c_uint64]
lib.dna_syntax_close.argtypes = [c.c_void_p]
lib.dna_memory_snapshot.argtypes = [c.c_uint, c.c_void_p]
text = b'[\n' + b'{"name":"needle","value":123,"active":true},\n' * 1000 + b'{}]'
output = c.create_string_buffer(len(text))
for cycle in range(12):
    handle = lib.dna_syntax_open_named(os.fsencode(ROOT / 'build/test-languages'), b'json')
    assert handle, 'JSON syntax fixture is required'
    try:
        lib.dna_syntax_update(handle, text, len(text), 1)
        deadline = time.monotonic() + 3
        while not lib.dna_syntax_colors(handle, output, len(text), 1):
            assert time.monotonic() < deadline, 'syntax result timed out'
            time.sleep(.001)
        assert any(output.raw), 'real syntax highlighting did not run'
    finally:
        lib.dna_syntax_close(handle)
totals = (c.c_uint64 * 7)()
lib.dna_memory_snapshot(0, totals)
assert totals[2] == 0 and totals[6] == 0, list(totals)
assert totals[3] < 4 * 1024 * 1024, f'small-file syntax peak: {totals[3]} bytes'
print(f'PASS repeated real syntax: peak {totals[3]} bytes; all buffers released')

# Force completed worker-buffer growth, shrinking and regrowth. Compare the
# incremental result with a fresh parser so byte offsets and UTF-8 stay correct.
handle = lib.dna_syntax_open_named(os.fsencode(ROOT / 'build/test-languages'), b'json')
assert handle
def parse(worker, text, revision):
    lib.dna_syntax_update(worker, text, len(text), revision)
    output = c.create_string_buffer(max(1, len(text)))
    deadline = time.monotonic() + 3
    while not lib.dna_syntax_colors(worker, output, len(text), revision):
        assert time.monotonic() < deadline, ('syntax timed out', len(text), revision)
        time.sleep(.001)
    return output.raw[:len(text)]

try:
    payload = '{"s":"é😀","n":42}'.encode()
    for revision, size in enumerate((4095, 4096, 8191, 8192, 65536, 0, 64, 131072, 32), 1):
        text = b'' if size == 0 else b' ' * (size - len(payload)) + payload
        actual = parse(handle, text, revision)
        fresh = lib.dna_syntax_open_named(os.fsencode(ROOT / 'build/test-languages'), b'json')
        assert fresh
        try:
            assert actual == parse(fresh, text, 1), ('incremental colors differ', size)
        finally:
            lib.dna_syntax_close(fresh)
finally:
    lib.dna_syntax_close(handle)
for category in (0, 4):
    lib.dna_memory_snapshot(category, totals)
    assert totals[0] == totals[1] and totals[2] == 0 and totals[6] == 0, list(totals)
print('PASS syntax capacity growth, empty/UTF-8 shrink and regrowth match fresh parses')
