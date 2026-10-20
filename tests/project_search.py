#!/usr/bin/env python3
"""Async search: UTF-8 offsets, stale generations, invalid regex, filesystem bounds."""
import ctypes as c
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
root = Path(__file__).resolve().parents[1]
lib = c.CDLL(os.environ.get('DNA_NATIVE_LIBRARY',str(root/'build/deps/install/lib/libdna_native.so')))
class Row(c.Structure):
    _fields_ = [('path', c.c_char*4096), ('text', c.c_char*256), ('start', c.c_size_t), ('end', c.c_size_t), ('line', c.c_size_t), ('column', c.c_size_t)]
lib.dna_search_open.restype = c.c_void_p
lib.dna_search_submit.argtypes = [c.c_void_p, c.c_char_p, c.c_char_p]
lib.dna_search_count.argtypes = [c.c_void_p, c.POINTER(c.c_int)]
lib.dna_search_count.restype = c.c_size_t
lib.dna_search_row.argtypes = [c.c_void_p, c.c_size_t, c.POINTER(Row)]
lib.dna_search_close.argtypes = [c.c_void_p]
search = lib.dna_search_open()
assert search
try:
    with tempfile.TemporaryDirectory() as directory:
        tree = Path(directory)
        (tree/'one.txt').write_text('hello\nα needle needle\n')
        (tree/'binary').write_bytes(b'needle\0')
        (tree/'build').mkdir(); (tree/'build/skip').write_text('needle')
        (tree/'link').symlink_to(tree/'one.txt')
        os.mkfifo(tree/'fifo')
        def submit(query, directory=tree): lib.dna_search_submit(search, os.fsencode(directory), query)
        def finish():
            deadline = time.monotonic()+7
            while time.monotonic()<deadline:
                status = c.c_int(); count = lib.dna_search_count(search, c.byref(status))
                if status.value != 1:
                    rows=[]
                    for i in range(count):
                        row=Row(); assert lib.dna_search_row(search, i, c.byref(row)); rows.append(row)
                    return status.value, rows
                time.sleep(.005)
            raise AssertionError('search did not finish')
        submit(b'needle'); status, rows = finish()
        assert status == 0 and len(rows) == 2
        assert [(r.path, r.start, r.end, r.line, r.column) for r in rows] == [(b'one.txt',9,15,2,4),(b'one.txt',16,22,2,11)]
        submit(b'['); assert finish()[0] == 2
        submit(b'\\C'); assert finish()[0] == 2
        submit(b'^'); assert len(finish()[1]) == 2
        for i in range(100): submit(b'needle' if i%2 else b'hello')
        submit(b'no match'); assert finish() == (0, [])
        # Repeated matches must preserve character boundaries and full-file regex semantics.
        with tempfile.TemporaryDirectory() as isolated:
            fixture = Path(isolated) / 'utf8.txt'
            fixture.write_text('é中\né中\n')
            submit(b'(?=.)', isolated); status, rows = finish()
            assert status == 0 and [(r.start, r.end) for r in rows] == [(0, 0), (2, 2), (6, 6), (8, 8)]
            submit('中\né'.encode(), isolated); status, rows = finish()
            assert status == 0 and [(r.start, r.end, r.line, r.column) for r in rows] == [(2, 8, 1, 3)]
            # Even a match before malformed UTF must not bypass the initial subject check.
            fixture.write_bytes(b'needle\nneedle\xff')
            submit(b'needle', isolated); status, rows = finish()
            assert status == 3 and not rows
            # Previously, revalidating the entire subject for each match exhausted
            # the built-in five-second deadline and returned incomplete results.
            fixture.write_bytes(b'needle\n' * 1000 + b'x' * (32_000_000 - 7000))
            submit(b'needle', isolated); status, rows = finish()
            assert status == 0 and len(rows) == 1000, ('dense search incomplete', status, len(rows))
            assert [(r.start, r.end, r.line, r.column) for r in rows] == [(7*i, 7*i+6, i+1, 1) for i in range(1000)]
        # Compare the literal path with equivalent forced-regex matching.
        with tempfile.TemporaryDirectory() as isolated:
            fixture = Path(isolated) / 'literal.txt'
            for text, literal in [(b'aaaaaaa', b'aa'), ('α needle needle\nneedle'.encode(), b'needle'),
                                  (b'prefix -# value -# suffix', b'-#'),
                                  (b'needle' + b'x'*65531 + b'needle' + b'x'*65533 + b'needle', b'needle')]:
                fixture.write_bytes(text)
                submit(literal, isolated); fast_status, fast = finish()
                submit(b'(?:'+literal+b')', isolated); regex_status, regex = finish()
                assert fast_status == regex_status == 0
                assert [(r.start, r.end, r.line, r.column) for r in fast] == [(r.start, r.end, r.line, r.column) for r in regex]
        # Past buffer.Capacity; sparse, so it costs no disk.
        with open(tree/'large', 'wb') as large: large.truncate(268435456)
        submit(b'hello'); assert finish()[0] == 3
        # Catastrophic backtracking remains bounded and superseded work never leaks.
        (tree/'hard').write_text('a'*60000+'!')
        submit(b'(a+)+$'); submit(b'hello'); status, rows = finish()
        assert len(rows) == 1 and rows[0].path == b'one.txt'
finally:
    lib.dna_search_close(search)
print('PASS cancellable project search, UTF-8, invalid regex, generations, limits, symlinks/FIFO')
subprocess.run([sys.executable, str(root/'tests/project_search_read.py')], check=True)
