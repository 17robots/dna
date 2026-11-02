#!/usr/bin/env python3
"""Count work in production background functions with deterministic worker seams."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--expect', choices=['baseline', 'bounded'], default='bounded')
parser.add_argument('--output', type=Path)
parser.add_argument('--source-root', type=Path, default=ROOT/'src')
parser.add_argument('--counts-only', action='store_true')
args = parser.parse_args()

def functions(path, names):
    source = path.read_text()
    result = []
    for name in names:
        match = re.search(r'^fn ' + name + r'\(', source, re.M)
        if not match:
            continue
        start = match.start()
        begin = source.index('{', start)
        depth = 1
        end = begin + 1
        while depth:
            if source[end] == '{': depth += 1
            elif source[end] == '}': depth -= 1
            end += 1
        body = source[start:end]
        if name == 'syntax_tick':
            body = body.replace('for index < #len(app.documents.slots) {', 'for index < #len(app.documents.slots) {\n    probe_visits += 1')
        if name == 'configured_filetypes':
            body = body.replace('slot := app.documents.slots[slot_index]', 'probe_filetypes += 1\n    slot := app.documents.slots[slot_index]')
        if name == 'configured_filetype_slot':
            body = body[:body.index('{')+1] + '\n  probe_filetypes += 1' + body[body.index('{')+1:]
        if name == 'recovery_needed':
            body = body.replace('for index in 0..#len(app.documents.slots) {', 'for index in 0..#len(app.documents.slots) {\n    probe_recovery += 1')
        if name == 'syntax_slot_tick':
            body = body[:body.index('{')+1] + '\n  probe_visits += 1' + body[body.index('{')+1:]
        if name == 'syntax_waiting':
            body = body.replace('slot := app.documents.slots[index]', 'probe_visits += 1\n    slot := app.documents.slots[index]').replace('slot := app.documents.slots[visible.indices[item]]', 'probe_visits += 1\n    slot := app.documents.slots[visible.indices[item]]')
        result.append(body)
    return '\n'.join(result)

BUFFER = '''pub struct TextSnapshot { length:usize }
pub fn snapshot_take(doc:*const Document) TextSnapshot { return TextSnapshot{length:doc.length} }
pub fn snapshot_release(text:*TextSnapshot) {}
pub struct Document { bytes:[32]u8, length:usize, revision:u64, saved_epoch:u64, saved_length:usize }
pub const LargeFile:usize=100000
pub const Capacity:usize=31
pub struct Change { found:bool, old_length, low, old_high, high:usize }
pub fn changes_since(doc:*Document, revision:u64) Change { return Change{} }
pub fn row_at(doc:*Document, offset:usize) usize { return 0 }
pub fn row_start(doc:*Document, row:usize) usize { return 0 }
pub fn line_end(doc:*const Document, offset:usize) usize { return doc.length }
pub fn saved_text(doc:*Document) []u8 { return doc.bytes[..] }
pub fn range(doc:*const Document, low:usize, high:usize) []const u8 { return doc.bytes[low..high] }
pub fn all(doc:*const Document) []const u8 { return doc.bytes[..doc.length] }
pub fn byte_at(doc:*const Document, offset:usize) u8 { return doc.bytes[offset] }
pub fn pointer(doc:*const Document, low:usize, high:usize) *const u8 { return &doc.bytes[low] }
pub fn release_views(doc:*Document) {}
pub fn copy_range(doc:*const Document, low:usize, high:usize, output:[]u8) {}
pub fn saved_hash(doc:*const Document) u64 { return 0 }
pub const LoadComplete:u8=0
pub fn load_state(doc:*const Document) u8 { return 0 }
pub fn chunk_at(doc:*const Document, offset:usize) []const u8 { return doc.bytes[offset..doc.length] }
pub fn dirty_cached(doc:*Document) bool { return false }
pub fn valid(bytes:[]const u8) bool { return true }
pub fn equal(a:[]const u8,b:[]const u8) bool { if #len(a)!=#len(b) {return false} for i in 0..#len(a) { if a[i]!=b[i] {return false} } return true }
'''
FILES = '''pub struct State { path:[4096]u8, length:usize }
pub fn name(file:*const State) []const u8 { return file.path[..file.length] }
pub struct Stamp { inode, size, modify_seconds, modify_nanos, change_seconds, change_nanos: u64, ok: bool }
pub fn saved_stamp(file:*const State) Stamp { _ = file
  return Stamp{} }
pub fn forget_stamp(file:*State) { _ = file }
'''
BASE = '''use "std/mem"
use "./buffer"
use "./files"
use "./owned_arena" arena_owner
#link("c")
extern fn puts "puts"(message:*const u8) i32
probe_filetypes:usize=0
probe_recovery:usize=0
probe_colors_ready:bool=true
probe_watch:usize=0
probe_fail:bool=false
probe_fire:bool=false
probe_ready_index:usize=0
probe_ready_identity:u64=0
probe_pending:usize=0
probe_updates:usize=0
probe_visits:usize=0
probe_visible:usize=0
struct SyntaxStream { context:rawptr,read:fn(rawptr,u32,*u32)*const u8,done:fn(rawptr),length,low,high:u32,revision,document_revision:u64 }
struct SyntaxSnapshot { next:*SyntaxSnapshot,arena:*mem.Arena,text:buffer.TextSnapshot }
syntax_snapshots:*SyntaxSnapshot=nil
fn syntax_snapshot_read(context:rawptr,byte:u32,length:*u32) *const u8 { return nil }
fn syntax_snapshot_done(context:rawptr) {}
fn syntax_snapshot_collect() {}
fn syntax_stream(handle:rawptr,request:*const SyntaxStream) i32 { probe_updates+=1 return 0 }
fn syntax_stream_needed(handle:rawptr,revision:u64) i32 { return 0 }
struct SyntaxChange { revision:u64, low, old_high, high, old_length, row, column:u32 }
struct DiskWatch { identity,epoch:u64, path:[4096]u8,length:usize, dirty,ready:bool,next:*Slot }
struct DiskState { worker:rawptr,retry:bool,first,last:*Slot, initialized:bool }
struct SyntaxState { first,filetype_first,filetype_last:*Slot }
struct Slot { document:*buffer.Document,file:files.State,terminal:Terminal,watch:DiskWatch,disk_changed:bool,colors:[]u8,identity:u64,index:usize,syntax:rawptr,syntax_checked:bool,syntax_revision,syntax_used:u64,syntax_window_low,syntax_window_high,syntax_shown_low,syntax_shown_high,syntax_view_low,syntax_view_high:usize,syntax_window_tag,syntax_shown_tag,syntax_window_revision:u64,syntax_owner:*App,syntax_next,syntax_previous:*Slot,filetype_length:usize,filetype:[65]u8,filetype_dirty:bool,filetype_next:*Slot,inferred_filetype:bool,recovery_revision,recovery_identity:u64 }
struct Terminal {handle:rawptr}
struct Pane {used,branch:bool,slot:usize}
struct View {panes:[15]Pane,revision:u64}
struct Documents {slots:[]*Slot,active:usize,generation:u64}
struct Language {extensions:[64]u8,extensions_length:usize,name:[65]u8,name_length:usize}
struct Config {syntax_enabled,reload_clean_buffers:bool,language_count:usize,languages:[1]Language}
struct Workspace {language_root:[4096]u8,project:[4096]u8,project_length:usize}
struct Recovery {ready:bool,generation,view:u64,active:usize,project:[4096]u8,project_length:usize}
struct App {recovery:Recovery,documents:Documents,disk:DiskState,syntax_state:SyntaxState,view:View,config:Config,workspace:Workspace}
struct DiskReady { index:usize,identity:u64 }
struct SyntaxVisible { indices:[16]usize,count:usize }
fn disk_open() rawptr {return #cast(rawptr,1)}
fn disk_watch(worker:rawptr,index:usize,identity:u64,path:*const u8,saved:*const u8,length:usize) i32 {
 probe_watch+=1
 if probe_fail {return 0}
 return 1
}
fn disk_watch_hashed(worker:rawptr,index:usize,identity:u64,path:*const u8,baseline:u64,length:usize) i32 {
 probe_watch+=1
 if probe_fail {return 0}
 return 1
}
fn disk_watch_stamped(worker:rawptr,index:usize,identity:u64,path:*const u8,stamp:*const u64,length:usize) i32 {
 probe_watch+=1
 if probe_fail {return 0}
 return 1
}
fn disk_pending(worker:rawptr,index:usize,identity:u64) isize {probe_pending+=1 return 0}
fn disk_next(worker:rawptr,ready:*DiskReady) i32 {
 if !probe_fire {return 0}
 probe_fire=false
 ready.index=probe_ready_index
 ready.identity=probe_ready_identity
 return 1
}
fn disk_take(worker:rawptr,index:usize,identity:u64,bytes:*u8,capacity:usize) i32 {return 0}
fn disk_replace(doc:*buffer.Document,bytes:[]const u8) {}
fn copy_text(out:[]u8,source:[]const u8) usize { for i in 0..#len(source) {out[i]=source[i]} return #len(source) }
fn explorer_suffix(name:[]const u8,extension:[]const u8) bool {return false}
fn lsp_document_dirty(app:*App,index:usize) {}
fn slot_visible(app:*App,index:usize) bool {probe_visible+=1 return index==app.documents.active}
fn syntax_open(root:*const u8,path:*const u8) rawptr {return #cast(rawptr,1)}
fn syntax_open_named(root:*const u8,path:*const u8) rawptr {return #cast(rawptr,1)}
fn syntax_update(handle:rawptr,text:*const u8,length:u32,revision:u64) {probe_updates+=1}
fn syntax_update_begin(handle:rawptr,length:u32,revision:u64) *u8 {probe_updates+=1 return nil}
fn syntax_update_commit(handle:rawptr,length:u32,revision:u64,hint:*const SyntaxChange) {}
fn syntax_update_changed(handle:rawptr,text:*const u8,length:u32,revision:u64,hint:*const SyntaxChange) {probe_updates+=1}
fn syntax_colors(handle:rawptr,colors:*u8,length:u32,revision:u64) i32 {
 if probe_colors_ready {return 1}
 return 0
}
fn syntax_retire(handle:rawptr) i32 {return 1}
fn syntax_close(handle:rawptr) {}
fn syntax_collect(wait:i32) {}
fn syntax_reset(slot:*Slot) {slot_syntax_release(slot)}
fn preview_syntax_tick(app:*App) bool {return false}
fn preview_syntax_waiting(app:*App) bool {return false}
'''
SYNTHETIC_SDL='''pub fn ticks() u64 {return 1}'''

def report(label, value):
    return f'  if !({value}) {{ #panic("{label}") }}\n'

with tempfile.TemporaryDirectory(prefix='dna-worksets-') as temporary:
    directory = Path(temporary)
    (directory/'buffer').mkdir(); (directory/'buffer/buffer.dyn').write_text(BUFFER.replace('} for', '}\n for').replace('} return', '}\n return'))
    (directory/'files').mkdir(); (directory/'files/files.dyn').write_text(FILES)
    (directory/'sdl').mkdir(); (directory/'sdl/sdl.dyn').write_text(SYNTHETIC_SDL)
    shutil.copytree(args.source_root/'owned_arena',directory/'owned_arena')
    (directory/'settings').mkdir(); (directory/'settings/settings.dyn').write_text('pub fn trim(value:[]const u8) []const u8 {return value}')
    source = BASE + '\nuse "./sdl"\nuse "./settings"\n'
    source += functions(args.source_root/'disk.dyn', ['disk_dirty_slot', 'disk_register', 'disk_process', 'disk_tick'])
    source += '\n' + functions(args.source_root/'syntax.dyn', ['syntax_track', 'syntax_untrack', 'slot_syntax_release', 'syntax_trim', 'syntax_slot_tick', 'syntax_copy', 'syntax_window_needed', 'syntax_window_tick', 'syntax_visible', 'syntax_tick', 'syntax_waiting', 'filetype_dirty_slot', 'configured_filetype_slot', 'configured_filetypes'])
    source += '\nconst SyntaxMargin: usize = 524288\nconst SyntaxWindowBit: u64 = 9223372036854775808\nconst SyntaxWindowLimit: usize = 8388608\n'
    source += '\n' + functions(args.source_root/'persistence.dyn', ['recovery_needed'])
    source += '''
fn probe_number(value:usize) {
  bytes:[32]u8=[]
  at:usize=30
  current:=value
  bytes[31]=10
  for true {
    bytes[at]=#cast(u8,current%10)+48
    current/=10
    if current==0 {break}
    at-=1
  }
  _=#syscall(1,1,&bytes[at],32-at)
}
fn main() {
  owner:=arena_owner.create(8388608)
  defer arena_owner.release(owner)
  app:=mem.push(App,owner)
  slots:=mem.push_array(Slot,owner,80)
  docs:=mem.push_array(buffer.Document,owner,80)
  pointers:=mem.push_array(*Slot,owner,80)
  colors: [32]u8=[]
  app.recovery.ready=true
  app.config.syntax_enabled=true
  app.disk.worker=#cast(rawptr,1)
  app.disk.initialized=true
  for i in 0..80 {
    pointers[i]=&slots[i]
    slots[i].index=i
    slots[i].document=&docs[i]
    docs[i].revision=1
    docs[i].saved_epoch=1
    slots[i].identity=#cast(u64,i)+1
    slots[i].file.path[0]=97
    slots[i].file.length=1
    slots[i].watch.identity=slots[i].identity
    slots[i].watch.epoch=1
    slots[i].watch.path[0]=97
    slots[i].watch.length=1
    slots[i].colors=colors[..]
  }
  for size in 0..2 {
    count:usize=1
    if size==1 {count=80}
    app.documents.slots=pointers[..count]
    slots[0].syntax=#cast(rawptr,1)
    slots[0].syntax_checked=true
    slots[0].syntax_revision=docs[0].revision
    for edited in 0..2 {
      app.recovery.generation=app.documents.generation
      if edited==1 {
        docs[0].revision+=1
        app.documents.generation+=1
      }
      probe_filetypes=0
      probe_recovery=0
      probe_pending=0
      probe_updates=0
      probe_visits=0
      probe_visible=0
      _=disk_tick(app)
      _=syntax_tick(app)
      _=syntax_waiting(app)
      configured_filetypes(app)
      recovery_dirty:=recovery_needed(app)
'''
    source += '  probe_number(probe_pending)\n  probe_number(probe_visits)\n  probe_number(probe_visible)\n  probe_number(probe_updates)\n  probe_number(probe_filetypes)\n  probe_number(probe_recovery)\n'
    if args.expect=='baseline':
        source += report('baseline_filetypes', 'probe_filetypes==count')
        source += report('baseline_recovery', 'probe_recovery==count')
        source += report('baseline_pending', 'probe_pending==count')
        source += report('baseline_visits', 'probe_visits==count*2')
        source += report('baseline_trim', 'probe_visible==1')
        source += report('baseline_redundant_update', 'probe_updates==1')
    else:
        source += report('bounded_filetypes', 'probe_filetypes==0')
        source += report('bounded_recovery', 'probe_recovery==0 && recovery_dirty==(edited==1)')
        source += report('bounded_pending', 'probe_pending==0')
        source += report('bounded_visits', 'probe_visits<=2')
        source += report('bounded_trim', 'probe_visible<=16')
        source += report('bounded_idle_update', '(edited==0 && probe_updates==0)||(edited==1 && probe_updates==1)')
    source += '\n    }\n'
    if args.expect == 'bounded' and not args.counts_only:
        source += '''
    target:=count-1
    probe_filetypes=0
    filetype_dirty_slot(app,target)
    filetype_dirty_slot(app,target)
    configured_filetypes(app)
    if probe_filetypes!=1 {#panic("targeted filetype resolution deduplication")}
    probe_filetypes=0
    configured_filetypes(app)
    if probe_filetypes!=0 {#panic("idle filetype resolution")}
    docs[target].saved_epoch+=1
    probe_watch=0
    probe_pending=0
    disk_dirty_slot(app,target)
    _=disk_tick(app)
    if probe_watch!=1 || probe_pending!=0 {#panic("targeted registration")}
    probe_watch=0
    _=disk_tick(app)
    if probe_watch!=0 {#panic("idle registration")}
    docs[target].saved_epoch+=1
    probe_fail=true
    disk_dirty_slot(app,target)
    _=disk_tick(app)
    if !app.disk.retry || !slots[target].watch.dirty {#panic("registration retry retained")}
    probe_fail=false
    _=disk_tick(app)
    if app.disk.retry || slots[target].watch.dirty {#panic("registration retry recovered")}
    probe_pending=0
    probe_ready_index=target
    probe_ready_identity=slots[target].identity
    probe_fire=true
    _=disk_tick(app)
    if probe_pending!=1 {#panic("single ready slot dispatch")}
    probe_pending=0
    probe_ready_identity+=1000
    probe_fire=true
    _=disk_tick(app)
    if probe_pending!=0 {#panic("stale ready identity")}
    probe_watch=0
    held_document:=slots[target].document
    slots[target].document=nil
    disk_dirty_slot(app,target)
    _=disk_tick(app)
    if probe_watch!=1 || slots[target].watch.identity!=0 {#panic("inactive close unregister")}
    slots[target].document=held_document
    disk_dirty_slot(app,target)
    _=disk_tick(app)
    if count==80 {
      app.view.panes[0]=Pane{used:true,slot:79}
      app.view.panes[1]=Pane{used:true,slot:79}
      probe_updates=0
      probe_colors_ready=false
      _=syntax_tick(app)
      if probe_updates!=1 || !syntax_waiting(app) {#panic("visible parser readiness and pane deduplication")}
      app.view.panes[0].used=false
      app.view.panes[1].used=false
      if syntax_waiting(app) {#panic("hidden parser must not force polling")}
      app.view.panes[0].used=true
      probe_colors_ready=true
      _=syntax_tick(app)
      if syntax_waiting(app) {#panic("parser completion clears readiness")}
      // A shrink may leave last frame's color origin beyond the new end.
      // Reject the stale range without subtracting unsigned offsets backwards.
      docs[79].length=20000000
      docs[79].revision+=1
      slots[79].syntax_window_tag=1
      slots[79].syntax_window_low=24000000
      slots[79].syntax_window_high=27000000
      slots[79].syntax_view_low=25000000
      slots[79].syntax_view_high=26000000
      _=syntax_window_tick(&slots[79])
      slot_syntax_release(&slots[79])
      if slots[79].syntax_owner!=nil {#panic("parser owner untracked")}
    }
'''
    source += '\n  }\n}\n' 
    source = source.replace('} for', '}\n for').replace('} return', '}\n return').replace('+=1 return', '+=1\n return')
    (directory/'main.dyn').write_text(source)
    binary=directory/'probe'
    subprocess.run([os.environ.get('DYN','dyn'),'build',str(directory),'--release','--output',str(binary)],check=True)
    result=subprocess.run([str(binary)],capture_output=True,text=True)
    if result.returncode:
        raise SystemExit(result.stdout+result.stderr or f'probe exited {result.returncode}')
    numbers=[int(line) for line in result.stdout.splitlines()]
    cases=[]
    for position,(count,phase) in enumerate((count,phase) for count in (1,80) for phase in ('idle','single edit')):
        values=numbers[position*6:position*6+6]
        cases.append(dict(buffers=count,phase=phase,**dict(zip(('disk_pending_calls','syntax_slot_visits','syntax_visibility_calls','syntax_updates','filetype_resolutions','recovery_slot_visits'),values))))
    report_data={'expect':args.expect,'kind':'production function count probe; worker/native seams deterministic', 'source_sha256':{name:hashlib.sha256((args.source_root/name).read_bytes()).hexdigest() for name in ('disk.dyn','syntax.dyn','persistence.dyn')}, 'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':cases}
    print(json.dumps(report_data,indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report_data,indent=2)+'\n')
