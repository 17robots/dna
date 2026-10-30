#!/usr/bin/env python3
"""Final syntax colors stay complete across document size, edits and cancellation."""
import ctypes as c
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import time
ROOT=Path(__file__).resolve().parents[1]
lib=c.CDLL(str(ROOT/'build/deps/install/lib/libdna_native.so'))
lib.dna_syntax_open_named.argtypes=[c.c_char_p,c.c_char_p]
lib.dna_syntax_open_named.restype=c.c_void_p
lib.dna_syntax_update.argtypes=[c.c_void_p,c.c_char_p,c.c_uint32,c.c_uint64]
lib.dna_syntax_colors.argtypes=[c.c_void_p,c.c_void_p,c.c_uint32,c.c_uint64]
lib.dna_syntax_close.argtypes=[c.c_void_p]
def opened():
    state=lib.dna_syntax_open_named(os.fsencode(ROOT/'build/test-languages'),b'dyn')
    assert state,'Dyn syntax fixture required'
    return state
def result(state,text,revision):
    output=c.create_string_buffer(max(1,len(text)))
    deadline=time.monotonic()+5
    while not lib.dna_syntax_colors(state,output,len(text),revision):
        assert time.monotonic()<deadline,('syntax did not complete',revision,len(text))
        time.sleep(.001)
    return output.raw[:len(text)]
line=b'fn example() { print("hello") }\n'
state=opened()
try:
    lib.dna_syntax_update(state,line,len(line),1)
    reference=result(state,line,1)
    assert reference[:2]==bytes([3,3]) and reference[3:10]==bytes([4])*7 and reference[21:28]==bytes([2])*7
    for revision,count in enumerate((64,) if "--slow-query" in sys.argv else (4096,4097,2048,8192),2):
        text=line*count
        lib.dna_syntax_update(state,text,len(text),revision)
        colors=result(state,text,revision)
        assert colors==reference*count,('same Dyn code loses colors with document size',count,next(i for i in range(count) if colors[i*len(line):(i+1)*len(line)]!=reference))
    # A newer revision cancels a large parse/query instead of publishing its
    # partial colors or delaying the small current revision until it completes.
    text=line*65536
    lib.dna_syntax_update(state,text,len(text),10)
    time.sleep(.003)
    lib.dna_syntax_update(state,line,len(line),11)
    assert result(state,line,11)==reference
    stale=c.create_string_buffer(1)
    assert not lib.dna_syntax_colors(state,stale,1,10)
finally:
    lib.dna_syntax_close(state)
state=opened()
try:
    text=line*65536
    lib.dna_syntax_update(state,text,len(text),1)
    time.sleep(.003)
finally:
    started=time.monotonic()
    lib.dna_syntax_close(state)
    assert time.monotonic()-started<2,'syntax close did not cancel background work promptly'
if '--slow-query' in sys.argv:
    print('PASS Dyn syntax: a query delayed beyond the former100ms deadline still publishes complete colors')
else:
    print('PASS Dyn syntax: identical colors through8192 repeated lines, shrinking edits, latest-revision cancellation and prompt close',flush=True)
    # Delay a real Tree-sitter capture call beyond the former shared deadline.
    # The previous worker acknowledged an all-plain buffer as completed here.
    with tempfile.TemporaryDirectory(prefix='dna-syntax-deadline-') as directory:
        work=Path(directory)
        source=work/'delay.c'
        source.write_text(r'''#define _GNU_SOURCE
#include <tree_sitter/api.h>
#include <dlfcn.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <time.h>
static atomic_int delayed;
bool ts_query_cursor_next_capture(TSQueryCursor *cursor, TSQueryMatch *match, uint32_t *capture) {
    bool (*next)(TSQueryCursor *, TSQueryMatch *, uint32_t *) = dlsym(dlopen("libtree-sitter.so", RTLD_NOW | RTLD_LOCAL), "ts_query_cursor_next_capture");
    if (!next) abort();
    if (!atomic_exchange(&delayed, 1)) {
        struct timespec delay = {0, 150000000};
        nanosleep(&delay, 0);
    }
    return next(cursor, match, capture);
}
''')
        interposer=work/'delay.so'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC',str(source),'-ldl','-o',str(interposer)],check=True)
        preload=str(interposer)
        if os.environ.get('LD_PRELOAD'): preload+=':'+os.environ['LD_PRELOAD']
        subprocess.run([sys.executable,__file__,'--slow-query'],env=dict(os.environ,LD_PRELOAD=preload),check=True,timeout=15)
