#!/usr/bin/env python3
"""Comment markers inside Dyn strings stay string text, after any escape."""
import ctypes as c
import os
from pathlib import Path
import time
ROOT = Path(__file__).resolve().parents[1]
lib = c.CDLL(str(ROOT/'build/deps/install/lib/libdna_native.so'))
lib.dna_syntax_open_named.argtypes = [c.c_char_p,c.c_char_p]
lib.dna_syntax_open_named.restype = c.c_void_p
lib.dna_syntax_update.argtypes = [c.c_void_p,c.c_char_p,c.c_uint32,c.c_uint64]
lib.dna_syntax_colors.argtypes = [c.c_void_p,c.c_void_p,c.c_uint32,c.c_uint64]
lib.dna_syntax_close.argtypes = [c.c_void_p]
languages = Path(os.environ.get('DNA_LANGUAGE_DIR', str(ROOT/'build/test-languages')))
Comment, String, Constant = 1, 2, 6
# Grammar revisions before tree-sitter-dyn fc21ad6 lexed `//` or `/*` after an
# escape as a comment; `\" /*` then greyed every line up to the next `*/`.
literals = [rb'"q \" /* r"', rb'"q \" // r"', rb'"q \n // r"', rb'"q \n /* r"',
            rb'"q \t /* r"', rb'"q \\ /* r"', rb'"q \x41 /* r"', rb'"x // y \"z\" /* w"',
            rb'"https://example.com//path"', rb'"/* not a comment */"', rb'"ends \\"']
lines = [b'fn main() {']
for index, literal in enumerate(literals):
    lines += [b'  s%d := %s' % (index, literal), b'  _ = %d' % (index + 1)]
lines += [b'  _ = 0 // real comment', b'}', b'']
text = b'\n'.join(lines)
worker = lib.dna_syntax_open_named(os.fsencode(languages),b'dyn')
assert worker, 'Dyn syntax fixture required'
try:
    lib.dna_syntax_update(worker,text,len(text),1)
    colors = c.create_string_buffer(len(text))
    deadline = time.monotonic()+5
    while not lib.dna_syntax_colors(worker,colors,len(text),1):
        assert time.monotonic()<deadline, 'Dyn source did not finish highlighting'
        time.sleep(.001)
    colors = colors.raw
finally:
    lib.dna_syntax_close(worker)
at = 0
for index, literal in enumerate(literals):
    start = text.index(literal, at)
    assert colors[start:start+len(literal)] == bytes([String])*len(literal), \
        (literal, list(colors[start:start+len(literal)]))
    number = text.index(b'_ = %d' % (index + 1), start) + 4
    assert colors[number] == Constant, (literal, 'next line recolored', colors[number])
    at = start + len(literal)
comment = text.index(b'// real comment')
assert colors[comment:comment+15] == bytes([Comment])*15, 'real comment lost'
print('PASS Dyn strings keep comment markers as string text')
