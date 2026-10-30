#!/usr/bin/env python3
"""Production LSP metadata/shadow ownership under growth and allocator failure."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
DYN=str(Path(os.environ.get('DYN',ROOT.parent/'dyn/compiler/build/dyn-release')).resolve())
def function(source,name):
    start=source.index('fn '+name+'(')
    body=source.index('{',start)
    depth,end=1,body+1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return source[start:end]
HEADER='''use "std/mem"
use "./owner" arena_owner
use "./buffer" buffer
use "./host" host
use "./sdl" sdl
struct LspShadow {arena:*mem.Arena,bytes:[]u8,length:usize,owned:bool,ready:bool}
struct LspDocument {shadow:LspShadow,identity:u64,revision:u64,observed:u64,changed:u64,path:[4096]u8}
struct LanguageServer {documents:[]LspDocument,documents_arena:*mem.Arena,allocation_retry_due:u64,ready:bool,dirty_first:*Slot,attach_scan:bool}
struct State {servers:[8]LanguageServer}
struct Document {revision:u64}
struct Slot {document:*Document,identity:u64,index:usize,lsp_dirty_next:[8]*Slot}
struct Documents {slots:[]*Slot}
struct Config {lsp_change_delay_ms:i32}
struct App {lsp:State,documents:Documents,config:Config}
failed:bool=false
allocations:usize=0
fn fault_allocate(capacity:usize)*mem.Arena {
 if failed {return nil}
 allocations+=1
 return arena_owner.try_create(capacity)
}
fn check(value:bool){if !value{#panic("LSP dynamic storage")}}
fn main(){
 app:=App{}
 server:=&app.lsp.servers[0]
 check(lsp_documents_ensure(server,1))
 server.documents[0].identity=77
 check(lsp_shadow_ensure(&server.documents[0].shadow,3))
 shadow:=&server.documents[0].shadow
 shadow.bytes[0]=97
 shadow.bytes[1]=98
 shadow.bytes[2]=99
 shadow.length=3
 shadow.ready=true
 original:=shadow.arena
 records:=server.documents_arena
 failed=true
 check(!lsp_documents_ensure(server,97) && server.documents_arena==records && #len(server.documents)==1)
 // No record exists for the unattached new slot, but scheduler still wakes.
 server.ready=true
 sdl.now=100
 lsp_allocation_retry(server,sdl.now)
 check(lsp_allocation_wait(server,100)==250 && lsp_wait_ms(&app,1000)==250)
 sdl.now=250
 check(lsp_wait_ms(&app,1000)==100)
 sdl.now=350
 check(lsp_wait_ms(&app,1000)==0)
 server.allocation_retry_due=0
 check(!lsp_shadow_ensure(shadow,8192) && shadow.arena==original && shadow.ready && shadow.length==3 && shadow.bytes[2]==99)
 // A dirty existing shadow must not override backoff with an expired 0ms
 // debounce timer. Once due, retry may proceed immediately.
 document:=Document{revision:2}
 slot:=Slot{document:&document,identity:77}
 slots:[1]*Slot=[&slot]
 app.documents.slots=slots[..]
 server.dirty_first=&slot
 server.documents[0].revision=1
 sdl.now=500
 lsp_allocation_retry(server,sdl.now)
 check(lsp_wait_ms(&app,1000)==250 && lsp_wait_ms(&app,40)==40)
 sdl.now=750
 check(lsp_wait_ms(&app,1000)==0)
 server.allocation_retry_due=0
 failed=false
 check(lsp_documents_ensure(server,97))
 // The record pointer moved; reacquire it before accessing the transferred owner.
 shadow=&server.documents[0].shadow
 check(server.documents[0].identity==77 && shadow.arena==original && shadow.bytes[0]==97)
 check(lsp_shadow_ensure(shadow,8192) && #len(shadow.bytes)>=8193 && shadow.bytes[2]==99 && shadow.length==3 && shadow.ready)
 count:=allocations
 check(lsp_shadow_ensure(shadow,1) && allocations==count)
 records=server.documents_arena
 check(!lsp_documents_ensure(server,#cast(usize,-1)) && server.documents_arena==records)
 check(!lsp_shadow_ensure(shadow,#cast(usize,-1)) && shadow.bytes[2]==99)
 for i in 1..97 {check(lsp_shadow_ensure(&server.documents[i].shadow,i))
   server.documents[i].shadow.length=i}
 lsp_shadows_release(&app,0)
 for i in 0..97 {check(!server.documents[i].shadow.owned && server.documents[i].shadow.arena==nil)}
 arena_owner.release(server.documents_arena)
}
'''
source=(ROOT/'src/language_server.dyn').read_text()
helpers='\n'.join(function(source,name) for name in ('lsp_documents_ensure','lsp_shadow_ensure','lsp_shadow_release','lsp_shadows_release','lsp_allocation_retry','lsp_allocation_wait','lsp_wait_ms')).replace('arena_owner.try_create','fault_allocate')
with tempfile.TemporaryDirectory(prefix='dna-lsp-storage-') as temporary:
    work=Path(temporary)
    shutil.copytree(ROOT/'src/owned_arena',work/'owner')
    (work/'buffer').mkdir();(work/'buffer/buffer.dyn').write_text('pub fn copy_bytes(dst:*u8,src:*const u8,length:usize)usize {for i in 0..length {dst[..length][i]=src[..length][i]}\n return length}\n')
    (work/'host').mkdir();(work/'host/host.dyn').write_text('pub fn small_pages(memory:[]u8) {}\n')
    (work/'sdl').mkdir();(work/'sdl/sdl.dyn').write_text('pub now:u64=0\npub fn ticks()u64 {return now}\n')
    (work/'main.dyn').write_text(HEADER+helpers)
    for mode in ('--debug','--release'):
        output=work/('probe'+mode)
        subprocess.run([DYN,'build',str(work),mode,'--quiet','--no-cache','--output',str(output)],check=True,timeout=120)
        subprocess.run([str(output)],check=True,timeout=20)
print('PASS LSP metadata/shadow growth, shrink reuse, 97 records, allocation failure preservation and release (debug/release)')
