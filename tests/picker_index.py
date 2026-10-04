#!/usr/bin/env python3
"""Async picker generations, nested invalidation, cancellation, and bounded watches."""
import ctypes as c
import os
from pathlib import Path
import tempfile
import time
ROOT = Path(__file__).resolve().parents[1]
os.environ['DNA_RENDER_TRACE'] = 'picker-memory-test'
lib = c.CDLL(str(ROOT / 'build/deps/install/lib/libdna_native.so'))
lib.dna_picker_open.restype = c.c_void_p
lib.dna_picker_submit.argtypes = [c.c_void_p, c.c_char_p]
lib.dna_picker_submit.restype = c.c_uint64
lib.dna_picker_poll.argtypes = [c.c_void_p, c.c_uint64, c.POINTER(c.c_size_t), c.POINTER(c.c_size_t), c.POINTER(c.c_uint32)]
lib.dna_picker_row.argtypes = [c.c_void_p, c.c_uint64, c.c_size_t, c.c_void_p, c.c_size_t]
lib.dna_picker_row.restype = c.c_size_t
lib.dna_picker_changed.argtypes = [c.c_void_p]
lib.dna_picker_close.argtypes = [c.c_void_p]
def result(worker, generation):
    count, visited, flags = c.c_size_t(), c.c_size_t(), c.c_uint32()
    deadline = time.monotonic() + 5
    while True:
        status = lib.dna_picker_poll(worker, generation, c.byref(count), c.byref(visited), c.byref(flags))
        assert status >= 0, 'unexpected stale generation'
        if status: break
        assert time.monotonic() < deadline, 'picker stalled'
        time.sleep(.001)
    rows = set()
    for index in range(count.value):
        path = c.create_string_buffer(512)
        assert lib.dna_picker_row(worker, generation, index, path, len(path))
        rows.add(os.fsdecode(path.value))
    return rows, flags.value

def changed(worker):
    deadline = time.monotonic() + 2
    while not lib.dna_picker_changed(worker):
        assert time.monotonic() < deadline, 'nested change missed'
        time.sleep(.001)

with tempfile.TemporaryDirectory(prefix='dna-picker-') as temporary:
    root = Path(temporary)
    (root/'nested').mkdir()
    (root/'nested/one.txt').write_text('one')
    (root/'.hidden').write_text('hidden')
    (root/'node_modules').mkdir()
    (root/'node_modules/excluded').write_text('excluded')
    worker = lib.dna_picker_open()
    assert worker
    try:
        submit = lambda: lib.dna_picker_submit(worker, os.fsencode(root))
        generation = submit()
        assert result(worker, generation)[0] == {'nested/one.txt'}
        (root/'nested/two.txt').write_text('two')
        changed(worker)
        assert result(worker, submit())[0] == {'nested/one.txt', 'nested/two.txt'}
        (root/'nested/two.txt').rename(root/'nested/renamed.txt')
        changed(worker)
        assert result(worker, submit())[0] == {'nested/one.txt', 'nested/renamed.txt'}
        (root/'nested/one.txt').unlink()
        changed(worker)
        assert result(worker, submit())[0] == {'nested/renamed.txt'}
        # Superseded results must never be read as the current root.
        stale = submit()
        current = lib.dna_picker_submit(worker, os.fsencode(root/'nested'))
        assert result(worker, current)[0] == {'renamed.txt'}
        path = c.create_string_buffer(512)
        assert not lib.dna_picker_row(worker, stale, 0, path, len(path))
        for index in range(270): (root/f'd{index}').mkdir()
        assert result(worker, submit())[1] & 4, 'watch coverage overflow needs fallback'
        canceled = lib.dna_picker_submit(worker, b'')
        assert result(worker, canceled)[0] == set()
        for _ in range(20): submit()
    finally:
        lib.dna_picker_close(worker)
    for _ in range(20):
        worker = lib.dna_picker_open()
        assert worker
        lib.dna_picker_submit(worker, os.fsencode(root))
        lib.dna_picker_close(worker)
lib.dna_memory_snapshot.argtypes = [c.c_uint, c.POINTER(c.c_uint64)]
for category in (1, 3):
    totals = (c.c_uint64 * 7)()
    lib.dna_memory_snapshot(category, totals)
    assert totals[0] > 0 and totals[0] == totals[1] and totals[2] == totals[6] == 0, list(totals)
print('PASS picker: nested create/rename/delete, stale generations, watch fallback, cancellation, shutdown, allocation balance')
