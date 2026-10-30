#!/usr/bin/env python3
"""Dyn grammar must retain declarations and calls in DNA's actual entry point."""
import ctypes as c
import os
from pathlib import Path
import re
import time
ROOT = Path(__file__).resolve().parents[1]
lib = c.CDLL(str(ROOT/'build/deps/install/lib/libdna_native.so'))
lib.dna_syntax_open_named.argtypes = [c.c_char_p,c.c_char_p]
lib.dna_syntax_open_named.restype = c.c_void_p
lib.dna_syntax_update.argtypes = [c.c_void_p,c.c_char_p,c.c_uint32,c.c_uint64]
lib.dna_syntax_colors.argtypes = [c.c_void_p,c.c_void_p,c.c_uint32,c.c_uint64]
lib.dna_syntax_close.argtypes = [c.c_void_p]
languages = Path(os.environ.get('DNA_LANGUAGE_DIR', str(ROOT/'build/test-languages')))
def parsed(text):
    worker = lib.dna_syntax_open_named(os.fsencode(languages),b'dyn')
    assert worker, 'Dyn syntax fixture required'
    try:
        lib.dna_syntax_update(worker,text,len(text),1)
        output = c.create_string_buffer(len(text))
        deadline = time.monotonic()+5
        while not lib.dna_syntax_colors(worker,output,len(text),1):
            assert time.monotonic()<deadline, 'Dyn source did not finish highlighting'
            time.sleep(.001)
        return output.raw
    finally:
        lib.dna_syntax_close(worker)

# The old grammar loses the following function after this delimited cast.
minimal = b'fn first(x:u32) { kind := #cast(u32, (x & 4294967295)) }\nfn mainthing() {}\n'
colors = parsed(minimal)
low = minimal.index(b'mainthing')
assert colors[low:low+9]==bytes([4])*9, 'delimited cast hides following function'
source = (ROOT/'src/main.dyn').read_bytes()
sentinel = b'\nfn dna_fullfile_highlight_probe() { print("highlight probe") }\n'
text = source + sentinel
colors = parsed(text)
declarations = list(re.finditer(rb'^fn ([A-Za-z_][A-Za-z0-9_]*)\(',text,re.MULTILINE))
assert len(declarations)>=3, 'entry point fixture must contain multiple complete functions'
for match in declarations:
    low,high = match.span(1)
    assert colors[low:high]==bytes([4])*(high-low), ('Dyn function loses highlight in full file',match.group(1).decode(),low,list(colors[low:high]))
for token in (b'finish_probe', b'render_request'):
    low = source.rfind(token+b'(')
    assert low>=0, ('required full-file call missing',token)
    assert colors[low:low+len(token)]==bytes([4])*len(token), ('Dyn call loses highlight in full file',token.decode(),low)
low = text.rfind(b'"highlight probe"')
assert colors[low:low+17]==bytes([2])*17, 'trailing full-file string loses highlight'
print(f'PASS Dyn full-file highlighting: {len(declarations)} function declarations, delimited-cast recovery, representative calls and trailing string in actual src/main.dyn')
