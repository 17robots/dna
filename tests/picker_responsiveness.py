#!/usr/bin/env python3
"""Production picker cache/partial-result transitions with a deterministic worker seam."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
source=Path(os.environ.get('DNA_PICKER_SOURCE',ROOT/'src'))
BASE='''use "std/mem"
use "./buffer"
use "./platform" sdl
struct Entry {name:[512]u8,length:usize,directory:bool}
enum Panel {None,Open,SaveAs}
struct Resource {kind:usize,fonts:bool}
struct Prompt {panel:Panel,text:[4096]u8,length:usize}
struct PickerState {worker:rawptr,generation,refresh_due:u64,pending,watching,watch_fallback:bool,index:*PickerIndex,arena:*mem.Arena,received_count:usize}
struct App {completion:CompletionState,picker_state:PickerState,resource_state:Resource,prompt_state:Prompt}
submits:usize=0
probe_status:i32=0
probe_count:usize=0
probe_flags:u32=0
fn picker_native_open()rawptr{return #cast(rawptr,1)}
fn picker_native_submit(worker:rawptr,root:*const u8)u64{submits+=1;return #cast(u64,submits)}
fn picker_native_poll(worker:rawptr,generation:u64,count:*usize,visited:*usize,flags:*u32)i32{count.*=probe_count;visited.*=probe_count;flags.*=probe_flags;return probe_status}
fn picker_native_row(worker:rawptr,generation:u64,index:usize,output:*u8,capacity:usize)usize{output.*='a'+#cast(u8,index);return 1}
fn picker_native_changed(worker:rawptr)i32{return 0}
fn picker_native_close(worker:rawptr){}
fn language_manager_refresh(app:*App){}
fn task_refresh(app:*App){}
fn font_refresh(app:*App){}
fn lower(byte:u8)u8{return byte}
fn contains(text:[]const u8,query:[]const u8)bool{if #len(query)>#len(text){return false} for at in 0..(#len(text)-#len(query)+1){if buffer.equal(text[at..at+#len(query)],query){return true}}return false}
fn copy_text(output:[]u8,text:[]const u8)usize{for at in 0..#len(text){output[at]=text[at]}if #len(text)<#len(output){output[#len(text)]=0}return #len(text)}
fn expand_home(path:[]const u8,output:[]u8)[]const u8{return path}
'''
CHECK='''fn main(){
 names:[65536]u8=[]
 offsets:[2048]usize=[]
 index:=PickerIndex{names:names[..],offsets:offsets[..]}
 app:=App{}
 app.prompt_state.panel=Panel.Open
 app.picker_state.index=&index
 completion_refresh(&app)
 if !app.picker_state.pending || app.completion.count!=0 {#panic("cold submit stays asynchronous")}
 probe_count=3;probe_status=1
 _=picker_index_tick(&app)
 if app.completion.count!=3 || app.picker_state.pending {#panic("completed rows imported")}
 app.prompt_state.panel=Panel.None
 _=picker_index_tick(&app)
 probe_status=0
 app.prompt_state.panel=Panel.Open
 completion_refresh(&app)
 if app.completion.count!=3 || !app.picker_state.pending {#panic("same-root reopen must show cached rows before worker ready")}
 // A cold partial snapshot becomes visible while indexing continues.
 index.count=0;app.picker_state.received_count=0
 probe_count=2;probe_status=2
 if !picker_index_tick(&app) || app.completion.count!=2 || !app.picker_state.pending {#panic("cold partial snapshot stays pending and visible")}
 if picker_index_tick(&app) {#panic("unchanged partial snapshot causes no refresh")}
 probe_count=4;probe_status=1
 if !picker_index_tick(&app) || app.completion.count!=4 || app.picker_state.pending {#panic("final snapshot replaces partial")}
 // A refresh keeps the complete cached list until a full new snapshot exists.
 picker_index_submit(&app)
 probe_count=2;probe_status=2
 if picker_index_tick(&app) || app.completion.count!=4 || !app.picker_state.pending {#panic("warm refresh must not shrink cached list")}
 probe_count=1;probe_status=1
 if !picker_index_tick(&app) || app.completion.count!=1 {#panic("refresh may remove deleted rows")}
 app.prompt_state.text[0]='x';app.prompt_state.text[1]='/'
 app.prompt_state.length=2;probe_status=0
 completion_refresh(&app)
 if app.completion.count!=0 || !app.picker_state.pending {#panic("different root never exposes cached paths")}
 probe_count=0;probe_status=1;probe_flags=2
 if !picker_index_tick(&app) || !app.completion.error || app.picker_state.pending {#panic("unreadable root finishes with an error")}
 picker_index_submit(&app)
 probe_status=-1
 if picker_index_tick(&app) || app.picker_state.pending || app.completion.count!=0 {#panic("stale generation cannot restore old rows")}
}'''
with tempfile.TemporaryDirectory(prefix='dna-picker-state-',dir=ROOT/'build') as d:
 stage=Path(d)
 shutil.copytree(ROOT/'src/owned_arena',stage/'owned_arena')
 (stage/'buffer').mkdir();(stage/'buffer/buffer.dyn').write_text('pub fn equal(a:[]const u8,b:[]const u8)bool{if #len(a)!=#len(b){return false}\nfor i in 0..#len(a){if a[i]!=b[i]{return false}}\nreturn true}\n')
 (stage/'platform').mkdir();(stage/'platform/platform.dyn').write_text('pub fn ticks()u64{return 100}\n')
 completion=(source/'completion.dyn').read_text()
 completion=completion[:completion.index('fn complete_path(')]
 start=completion.index('fn expand_home(');end=completion.index('// Bounded, cached',start)
 completion=completion[:start]+completion[end:]
 index=(source/'picker_index.dyn').read_text();index=index[index.index('fn picker_index_submit('):]
 (stage/'main.dyn').write_text('\n'.join((BASE.replace(';','\n'),completion,index,CHECK.replace(';','\n'))).replace('}for','}\nfor').replace('}return','}\nreturn').replace('} for','}\nfor').replace('}if','}\nif'))
 (ROOT/'build/picker-probe-source.dyn').write_text((stage/'main.dyn').read_text())
 for mode in ('debug','release'):
  binary=stage/'probe'
  subprocess.run(['python3',str(ROOT/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(stage),'--'+mode,'--output',str(binary)],check=True)
  subprocess.run([str(binary)],check=True)
print('PASS picker responsiveness: immediate same-root cache, cold partial publication, no redundant refresh, complete warm refresh, root isolation (debug/release)')
