#!/usr/bin/env python3
"""Darwin errno accessor resolves once before fallible I/O, including racing calls."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get('DYN', 'dyn')
SHIM = r'''
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
static _Thread_local int stored,expected;
static int resolutions;
static int *get_error(void) {return &stored;}
void *probe_resolve(void) {__atomic_add_fetch(&resolutions,1,__ATOMIC_SEQ_CST);stored=77;return (void*)get_error;}
void probe_fail(void) {stored=expected;}
int probe_expected(void) {return expected;}
static int (*callback)(void);
static void *run(void *p) {expected=(int)(intptr_t)p+2;for(int i=0;i<100;i++)assert(callback()==1);return 0;}
int probe_race(int (*call)(void)) {callback=call;pthread_t threads[16];for(int i=0;i<16;i++)assert(!pthread_create(&threads[i],0,run,(void*)(intptr_t)i));for(int i=0;i<16;i++)assert(!pthread_join(threads[i],0));assert(resolutions==1);return 1;}
'''
with tempfile.TemporaryDirectory(prefix='dna-darwin-errno-') as directory:
    stage = Path(directory)
    shutil.copytree(ROOT/'src/cstring', stage/'cstring')
    (stage/'dynlib').mkdir()
    (stage/'dynlib/dynlib.dyn').write_text('''pub struct SymbolResult {value:rawptr,ok:bool}
extern fn resolve "probe_resolve"() rawptr
pub fn symbol(handle:rawptr,name:[]const u8) SymbolResult {
 if #cast(isize,handle)!=-2 || #len(name)!=7 {#panic("wrong Darwin symbol lookup")}
 expected:[]const u8="__error"
 for i in 0..7 {if name[i]!=expected[i] {#panic("wrong errno symbol")}}
 return SymbolResult{value:resolve(),ok:true}
}
''')
    source = (ROOT/'src/filesystem/macos.dyn').read_text()
    helpers = source[source.index('// The pinned SDK thread module'):source.index('fn darwin_result(')]
    (stage/'main.dyn').write_text('''#link("c")
#link("pthread")
use "std/sync" sync
use "./dynlib" dynlib
use "./cstring" cstring
extern fn probe_fail "probe_fail"()
extern fn probe_race "probe_race"(callback:fn()i32) i32
extern fn probe_expected "probe_expected"() i32
'''+helpers+'''
fn check_error() i32 {
 storage:[32]u8=[]
 if darwin_path("missing",storage[..])==nil {#panic("missing path")}
 probe_fail()
 if darwin_error()!=0-#cast(isize,probe_expected()) {#panic("loader clobbered I/O errno")}
 return 1
}
fn main() {_=probe_race(check_error)}
''')
    subprocess.run(['cc','-pthread','-x','c','-c','-o',str(stage/'shim.o'),'-'],input=SHIM,text=True,check=True)
    for mode in ('debug','release'):
        binary = stage/mode
        subprocess.run([DYN,'build',str(stage),'--'+mode,'--link',str(stage/'shim.o'),'--output',str(binary)],check=True)
        subprocess.run([str(binary)],check=True,timeout=10)
print('PASS Darwin errno: one resolver across racing threads; preserves post-I/O errno (debug/release; loader simulated)')
