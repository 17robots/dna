#!/usr/bin/env python3
"""Compare journal-assisted, stale and coalesced syntax updates with fresh parses."""
import ctypes as c
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ['DNA_RENDER_TRACE'] = 'syntax-changes-test'
lib = c.CDLL(str(ROOT / 'build/deps/install/lib/libdna_native.so'), mode=c.RTLD_GLOBAL)

class Change(c.Structure):
    _fields_ = [('revision', c.c_uint64)] + [(name, c.c_uint32) for name in
        ('low', 'old_high', 'high', 'old_length', 'row', 'column')]

lib.dna_syntax_open_named.argtypes = [c.c_char_p, c.c_char_p]
lib.dna_syntax_open_named.restype = c.c_void_p
lib.dna_syntax_update.argtypes = [c.c_void_p, c.c_char_p, c.c_uint32, c.c_uint64]
lib.dna_syntax_update_changed.argtypes = [c.c_void_p, c.c_char_p, c.c_uint32, c.c_uint64, c.POINTER(Change)]
lib.dna_syntax_colors.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32, c.c_uint64]
lib.dna_syntax_close.argtypes = [c.c_void_p]
lib.dna_memory_snapshot.argtypes = [c.c_uint, c.c_void_p]

def opened():
    worker = lib.dna_syntax_open_named(os.fsencode(ROOT / 'build/test-languages'), b'json')
    assert worker, 'JSON syntax fixture is required'
    return worker

def result(worker, text, revision):
    output = c.create_string_buffer(max(1, len(text)))
    deadline = time.monotonic() + 3
    while not lib.dna_syntax_colors(worker, output, len(text), revision):
        assert time.monotonic() < deadline, ('syntax timed out', revision)
        time.sleep(.001)
    return output.raw[:len(text)]

def fresh(text):
    worker = opened()
    try:
        lib.dna_syntax_update(worker, text, len(text), 1)
        return result(worker, text, 1)
    finally:
        lib.dna_syntax_close(worker)

def hint(old, new, base):
    low = 0
    while low < min(len(old), len(new)) and old[low] == new[low]:
        low += 1
    while low and low < len(new) and new[low] & 192 == 128:
        low -= 1
    old_high, high = len(old), len(new)
    while old_high > low and high > low and old[old_high - 1] == new[high - 1]:
        old_high -= 1
        high -= 1
    while high < len(new) and new[high] & 192 == 128:
        old_high += 1
        high += 1
    prefix = new[:low]
    return Change(base, low, old_high, high, len(old), prefix.count(b'\n'), len(prefix.rsplit(b'\n', 1)[-1]))

worker = opened()
try:
    old = b'{"n":42,"s":"initial"}\n'
    lib.dna_syntax_update(worker, old, len(old), 1)
    assert result(worker, old, 1) == fresh(old)
    samples = [
        '{"n":123,"s":"é😀"}\n'.encode(),
        '{\n "n":123,\n "s":"è😃", "a":[true,null]\n}\n'.encode(),
        b'{"a":[false,12]}', b'', b'\n[]\n',
        b' ' * 65536 + b'{"n":42}', b' {"n":7}',
    ]
    revision = 1
    for text in samples:
        change = hint(old, text, revision)
        revision += 1
        lib.dna_syntax_update_changed(worker, text, len(text), revision, c.byref(change))
        assert result(worker, text, revision) == fresh(text), ('hint result differs', revision)
        old = text
    # A stale or malformed hint must fall back to a full diff, not corrupt the tree.
    for change in [Change(1, 0, 0, 0, 0, 0, 0),
                   Change(revision + 1, 99999, 1, 2, len(old), 0, 0)]:
        text = b'\n{"z":[true,false],"n":84}\n'
        revision += 1
        lib.dna_syntax_update_changed(worker, text, len(text), revision, c.byref(change))
        assert result(worker, text, revision) == fresh(text)
        old = text
    # Publish faster than the worker can finish. Every hint references the same
    # acknowledged revision; retained intermediate parses must reject stale hints.
    base = revision
    for number in range(100):
        text = b' ' * 65536 + ('{"n":%d,"s":"é😀"}' % number).encode()
        change = hint(old, text, base)
        revision += 1
        lib.dna_syntax_update_changed(worker, text, len(text), revision, c.byref(change))
    assert result(worker, text, revision) == fresh(text), 'coalesced result differs'
finally:
    lib.dna_syntax_close(worker)
for category in (0, 4):
    totals = (c.c_uint64 * 7)()
    lib.dna_memory_snapshot(category, totals)
    assert totals[0] == totals[1] and totals[2] == totals[6] == 0, (category, list(totals))
print('PASS syntax journal ranges, UTF-8, empty input, stale hints, coalescing and allocation balance')
