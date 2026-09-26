#!/usr/bin/env python3
"""Review spans retained history; cursor follows selections and survives resize."""
import ctypes as c, time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
lib=c.CDLL(str(root/'build/deps/install/lib/libdna_native.so'))
lib.dna_terminal_open.argtypes=[c.c_char_p]*3;lib.dna_terminal_open.restype=c.c_void_p
for name in ('poll','alive','close','review_end'):
    getattr(lib,'dna_terminal_'+name).argtypes=[c.c_void_p]
lib.dna_terminal_review.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t];lib.dna_terminal_review.restype=c.c_size_t
lib.dna_terminal_review_select.argtypes=[c.c_void_p,c.c_size_t,c.c_size_t,c.c_size_t]
lib.dna_terminal_review_head.argtypes=[c.c_void_p];lib.dna_terminal_review_head.restype=c.c_size_t
lib.dna_terminal_cursor.argtypes=[c.c_void_p,c.POINTER(c.c_int),c.POINTER(c.c_int)]
lib.dna_terminal_resize.argtypes=[c.c_void_p]+[c.c_float]*4
p=lib.dna_terminal_open(b'/tmp',b'/bin/sh',b"i=0; while [ $i -lt 150 ]; do printf 'row-%03d \\303\\251\\344\\270\\255\\n' $i; i=$((i+1)); done")
assert p
try:
    deadline=time.monotonic()+3
    while lib.dna_terminal_alive(p) and time.monotonic()<deadline:
        lib.dna_terminal_poll(p);time.sleep(.002)
    lib.dna_terminal_poll(p);assert not lib.dna_terminal_alive(p)
    text=c.create_string_buffer(262144);size=lib.dna_terminal_review(p,text,len(text));data=text.raw[:size]
    assert b'row-000' in data and b'row-149' in data;assert 'é中'.encode() in data
    first=data.index(b'row-000');last=data.index(b'row-149')
    col=c.c_int();row=c.c_int()
    for head in (first,last,first,last):
        lib.dna_terminal_review_select(p,first,last+7,head)
        assert lib.dna_terminal_review_head(p)==head
        lib.dna_terminal_cursor(p,c.byref(col),c.byref(row));assert 0<=row.value<24 and col.value==0
    lib.dna_terminal_resize(p,320,160,8,16)
    lib.dna_terminal_review_select(p,first,last+7,first)
    assert lib.dna_terminal_review_head(p)==first
    lib.dna_terminal_cursor(p,c.byref(col),c.byref(row));assert 0<=row.value<10
    lib.dna_terminal_poll(p);assert lib.dna_terminal_review_head(p)==first
    lib.dna_terminal_review_end(p)
finally:lib.dna_terminal_close(p)
print('PASS terminal Unicode scrollback selection, viewport following, stable resize')
