#!/usr/bin/env python3
"""Repeated native lifecycles must release descriptors, threads and owned files."""
import ctypes as c, os, tempfile, time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
lib=c.CDLL(str(root/'build/deps/install/lib/libdna_native.so'))
for name,args in [('terminal_open',[c.c_char_p]*3),('syntax_open_named',[c.c_char_p]*2),('plugin_open',[c.c_char_p]*2),('search_open',[]),('recovery_open',[c.c_char_p]),('disk_open',[]),('rpc_open',[c.c_char_p]*2)]:
    fn=getattr(lib,'dna_'+name);fn.argtypes=args;fn.restype=c.c_void_p
for name in ('terminal_poll','terminal_close','syntax_close','plugin_close','search_close','recovery_close','disk_close','rpc_close'):
    getattr(lib,'dna_'+name).argtypes=[c.c_void_p]
lib.dna_syntax_update.argtypes=[c.c_void_p,c.c_char_p,c.c_uint32,c.c_uint64]
lib.dna_syntax_colors.argtypes=[c.c_void_p,c.c_void_p,c.c_uint32,c.c_uint64]
lib.dna_syntax_retire.argtypes=[c.c_void_p]
lib.dna_syntax_collect.argtypes=[c.c_int]
lib.dna_search_submit.argtypes=[c.c_void_p,c.c_char_p,c.c_char_p]
lib.dna_recovery_submit.argtypes=[c.c_void_p,c.c_char_p,c.c_size_t]
def resources():
    pages=int(Path('/proc/self/statm').read_text().split()[1])
    return len(list(Path('/proc/self/fd').iterdir())),len(list(Path('/proc/self/task').iterdir())),pages*os.sysconf('SC_PAGE_SIZE')
def settled():
    """Resources once background workers (such as the parser disposer that a
    retire hands off to) have exited; a sample taken mid-exit counts a thread
    that is already finishing."""
    deadline=time.monotonic()+2
    best=resources()
    while time.monotonic()<deadline:
        time.sleep(.02)
        sample=resources()
        if sample[:2]<=best[:2]:
            if sample[:2]==best[:2] and sample[1]==1:
                return sample
            best=sample
    return best
def parsed(syntax, text, revision):
    colors=c.create_string_buffer(max(1,len(text)))
    deadline=time.monotonic()+3
    while not lib.dna_syntax_colors(syntax,colors,len(text),revision):
        assert time.monotonic()<deadline, ('syntax did not publish',revision)
        time.sleep(.001)
    return colors.raw[:len(text)]

busy_text=b'['+b'{"n":42,"s":"value"},'*8192+b'null]'
variants=(b'',b'{"n":42}', '{"s":"é😀"}'.encode(), b'[true,false,null]')
with tempfile.TemporaryDirectory() as d:
    directory=os.fsencode(d);(Path(d)/'sample').write_text('needle\n')
    cycles = int(os.environ.get("DNA_RESOURCE_CYCLES", "60"))
    assert 20 <= cycles <= 2000
    for cycle in range(cycles):
        disk=lib.dna_disk_open();assert disk
        rpc=lib.dna_rpc_open(b'cat',directory);assert rpc
        term=lib.dna_terminal_open(directory,b'/bin/sh',b'printf cycle');assert term
        syntax=lib.dna_syntax_open_named(os.fsencode(root/'build/test-languages'),b'json')
        assert syntax, 'Install the JSON test grammar first; syntax lifecycle coverage is required'
        first=variants[cycle%len(variants)]
        lib.dna_syntax_update(syntax,first,len(first),1)
        parsed(syntax,first,1)
        # Replace queued/parsing snapshots, crossing empty and multibyte inputs.
        for revision,text in enumerate((busy_text,*variants),2):
            lib.dna_syntax_update(syntax,text,len(text),revision)
        latest='{"s":"é😀","n":42}'.encode()
        lib.dna_syntax_update(syntax,latest,len(latest),7)
        colors=parsed(syntax,latest,7)
        assert colors[latest.index('é'.encode())]==2 and colors[latest.index(b'42')]==6, colors
        stale=c.create_string_buffer(len(latest))
        assert not lib.dna_syntax_colors(syntax,stale,len(latest),1), 'stale syntax published'
        plugin=lib.dna_plugin_open(os.fsencode(root/'examples/plugins/uppercase/uppercase'),directory);assert plugin
        search=lib.dna_search_open();assert search;lib.dna_search_submit(search,directory,b'needle')
        recovery=lib.dna_recovery_open(os.fsencode(Path(d)/'recovery'));assert recovery;assert lib.dna_recovery_submit(recovery,b'cycle',5)
        time.sleep(.005);lib.dna_terminal_poll(term)
        lib.dna_terminal_close(term);lib.dna_disk_close(disk);lib.dna_rpc_close(rpc)
        # Teardown with queued or active parse work, rather than only idle workers.
        lib.dna_syntax_update(syntax,busy_text,len(busy_text),8)
        started=time.monotonic()
        if cycle % 2:
            assert lib.dna_syntax_retire(syntax)
            lib.dna_syntax_collect(1)
        else:lib.dna_syntax_close(syntax)
        assert time.monotonic()-started<1, 'syntax cancellation/teardown stalled'
        lib.dna_plugin_close(plugin);lib.dna_search_close(search);lib.dna_recovery_close(recovery)
        assert not list((Path(d)/'recovery').glob('session-*'))
        if cycle==9:baseline=settled()
    final=settled();assert final[:2]==baseline[:2],(baseline,final)
    assert final[2]-baseline[2]<8*1024*1024,(baseline,final)
    print(f'PASS {cycles} lifecycle cycles: descriptors/threads unchanged; RSS growth',final[2]-baseline[2],'bytes')
