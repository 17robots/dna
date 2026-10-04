#!/usr/bin/env python3
"""Small documents must not reserve maximum-sized syntax buffers per worker."""
import ctypes as c
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ['DNA_RENDER_TRACE'] = 'syntax-memory-test'
lib = c.CDLL(str(ROOT / 'build/deps/install/lib/libdna_native.so'), mode=c.RTLD_GLOBAL)
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

# A transient small revision must not discard warm capacity. Sustained small
# revisions must eventually release it without closing the syntax worker.
handle = lib.dna_syntax_open_named(os.fsencode(ROOT / 'build/test-languages'), b'json')
assert handle
try:
    small = b' ' * 16 + b'{"s":"ok","n":7}'
    large = b' ' * (4 * 1024 * 1024 - len(small)) + small
    expected = parse(handle, small, 1)
    parse(handle, large, 2)
    lib.dna_memory_snapshot(0, totals)
    grown = totals[2]
    assert grown >= 40 * 1024 * 1024, list(totals)
    for revision in range(3, 13):
        actual = parse(handle, small if revision % 2 else large, revision)
        if revision % 2:
            assert actual == expected, 'alternating-size colors changed'
        lib.dna_memory_snapshot(0, totals)
        assert totals[2] == grown, 'alternating sizes caused capacity churn'
    for revision in range(13, 21):
        assert parse(handle, small, revision) == expected, 'trim changed colors'
        lib.dna_memory_snapshot(0, totals)
        if revision < 20:
            assert totals[2] == grown, 'capacity released before sustained low usage'
    trimmed = totals[2]
    assert trimmed < 1024 * 1024, ('oversized buffers retained', grown, trimmed)
    # Regrowth after reallocating all five buffers must still highlight correctly.
    assert parse(handle, large, 21)[-len(small):] == expected
finally:
    lib.dna_syntax_close(handle)
for category in (0, 4):
    lib.dna_memory_snapshot(category, totals)
    assert totals[0] == totals[1] and totals[2] == 0 and totals[6] == 0, list(totals)
print(f'PASS sustained syntax shrink: {grown} -> {trimmed} bytes; alternating sizes retain capacity')

# Reuse tests/native/syntax_faults when explicitly launched with its interposer.
if '--trim-faults' in sys.argv:
    probe = c.CDLL(None)
    probe.dna_test_syntax_arm.argtypes = [c.c_uint32]
    probe.dna_test_syntax_failed.restype = c.c_uint32
    for nth in range(1, 6):
        handle = lib.dna_syntax_open_named(os.fsencode(ROOT / 'build/test-languages'), b'json')
        assert handle
        try:
            parse(handle, large, 1)
            probe.dna_test_syntax_arm(nth)
            for revision in range(2, 10):
                assert parse(handle, small, revision) == expected
            assert probe.dna_test_syntax_failed(), ('trim fault not reached', nth)
            lib.dna_memory_snapshot(0, totals)
            assert 8 * 1024 * 1024 <= totals[2] < 9 * 1024 * 1024, (nth, list(totals))
            # Partial trimming must retry the one failed allocation, even when
            # the input buffer itself already shrank successfully.
            for revision in range(10, 18):
                assert parse(handle, small, revision) == expected
            lib.dna_memory_snapshot(0, totals)
            assert totals[2] < 1024 * 1024, ('failed trim never retried', nth, list(totals))
            assert parse(handle, large, 18)[-len(small):] == expected
        finally:
            probe.dna_test_syntax_arm(0)
            lib.dna_syntax_close(handle)
        for category in (0, 4):
            lib.dna_memory_snapshot(category, totals)
            assert totals[0] == totals[1] and totals[2] == 0 and totals[6] == 0, (nth, category, list(totals))
    print('PASS all five syntax trim failures: colors preserved, trimming retried, owners released')
