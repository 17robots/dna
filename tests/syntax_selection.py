#!/usr/bin/env python3
"""Revision-safe syntax navigation uses the real background parser."""
import ctypes as c
import os
from pathlib import Path
import time
import subprocess
root = Path(__file__).resolve().parents[1]
for language in ('json','dyn'):
    if not (root/'build/test-languages'/language/'parser.so').exists():
        subprocess.run(['python3',str(root/'scripts/compile.py'),str(root/'build/deps/install/bin/dna-language'),'install',language],
                       env=dict(os.environ,DNA_LANGUAGE_DIR=str(root/'build/test-languages')),check=True,timeout=180)
lib = c.CDLL(str(root/'build/deps/install/lib/libdna_native.so'))
lib.dna_syntax_open_named.argtypes = [c.c_char_p, c.c_char_p]
lib.dna_syntax_open_named.restype = c.c_void_p
lib.dna_syntax_update.argtypes = [c.c_void_p,c.c_char_p,c.c_uint32,c.c_uint64]
lib.dna_syntax_select.argtypes = [c.c_void_p,c.c_uint64,c.c_uint32,c.c_uint32,c.c_uint,c.POINTER(c.c_uint32),c.POINTER(c.c_uint32)]
lib.dna_syntax_close.argtypes = [c.c_void_p]
state = lib.dna_syntax_open_named(os.fsencode(root/'build/test-languages'),b'json')
assert state, 'Install the JSON test grammar first'
text = b'{"a": [1,2]}'
try:
    lib.dna_syntax_update(state,text,len(text),1)
    def select(low,high,mode,revision=1):
        start,end = c.c_uint32(),c.c_uint32()
        ok = lib.dna_syntax_select(state,revision,low,high,mode,c.byref(start),c.byref(end))
        return (start.value,end.value) if ok else None
    deadline=time.monotonic()+3
    while select(7,8,0) is None and time.monotonic()<deadline: time.sleep(.005)
    assert select(7,8,0)==(6,11), select(7,8,0)
    assert select(6,11,1)==(7,8)
    assert select(7,8,3)==(9,10)
    assert select(9,10,2)==(7,8)
    assert select(7,8,0,2) is None
    assert select(0,len(text)+1,0) is None
    assert select(8,7,0) is None
    lib.dna_syntax_update(state,b'[]',2,2)
    assert select(7,8,0,1) is None
finally: lib.dna_syntax_close(state)
print('PASS syntax parent/child/siblings, invalid ranges, stale revisions')

# Queries are optional per language; exercise shipped Dyn captures in isolation.
import tempfile, shutil
lib.dna_syntax_object.argtypes = [c.c_void_p,c.c_uint64,c.c_uint32,c.c_uint32,c.c_uint,c.c_uint,c.POINTER(c.c_uint32),c.POINTER(c.c_uint32)]
with tempfile.TemporaryDirectory() as directory:
    package=Path(directory)/'dyn'
    shutil.copytree(root/'build/test-languages/dyn',package)
    shutil.copyfile(root/'languages/queries/dyn.textobjects.scm',package/'textobjects.scm')
    state=lib.dna_syntax_open_named(os.fsencode(directory),b'dyn');assert state
    text=b'fn main() { value := 12 }'
    try:
        lib.dna_syntax_update(state,text,len(text),5)
        def object_range(kind,revision=5):
            start,end=c.c_uint32(),c.c_uint32()
            ok=lib.dna_syntax_object(state,revision,20,20,kind,1,c.byref(start),c.byref(end))
            return (start.value,end.value) if ok else None
        deadline=time.monotonic()+3
        while object_range(1) is None and time.monotonic()<deadline:time.sleep(.005)
        assert object_range(1)==(0,len(text)),object_range(1)
        assert object_range(0)==(10,len(text)),object_range(0)
        assert object_range(1,6) is None
    finally:lib.dna_syntax_close(state)
print('PASS query-backed Dyn function text objects, inside/around, stale revision')
