#!/usr/bin/env python3
"""Production recovery capture and patch restore with real text/workspace storage."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get("DYN") or subprocess.check_output(
    ["python3", str(ROOT / "scripts/dyn_path.py")], text=True).strip()


def block(source, marker):
    start = source.index(marker)
    body = source.index("{", start)
    depth, end = 1, body + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


source = (ROOT / "src/persistence.dyn").read_text()
fixture = '''use "std/mem"
use "./owned_arena" arena_owner
use "./buffer" buffer
use "./workspace" workspace
use "./files" files
use "./fs" fs
use "./sdl" sdl
extern fn fill "__memset_chk"(target:*u8,byte:i32,length:usize,room:usize) rawptr
struct Terminal {handle:rawptr}
struct Slot {document:*buffer.Document,file:files.State,filetype:[65]u8,filetype_length:usize,inferred_filetype:bool,terminal:Terminal}
struct Documents {slots:[]*Slot,active:usize,generation:u64}
struct Pane {used:bool,branch:bool,vertical:bool,split_fraction:f32,parent:usize,first:usize,second:usize,slot:usize,scroll_x:f32,scroll_y:f32,secondary_count:usize}
struct View {focused:usize,revision:u64,panes:[15]Pane}
struct Project {project:[4096]u8,project_length:usize}
struct Configuration {path:[4096]u8,path_length:usize}
struct Config {recovery_enabled:bool}
struct Work {arena:*mem.Arena}
struct Operations {recovery_encode:Work}
''' + block(source, "struct RecoveryState {") + '''
struct App {documents:Documents,view:View,workspace:Project,configuration:Configuration,config:Config,recovery:RecoveryState,operations:Operations,logs:usize,notices:usize}
submissions:usize=0
record_storage:*u8=nil
record_capacity:usize=0
record_length:usize=0
fn check(value:bool) {if !value {#panic("recovery capture safety")}}
fn pane_init(app:*App) {}
fn pane_store(app:*App) {}
fn notice(app:*App,text:[]const u8) {app.notices+=1}
fn plugin_log(app:*App,text:[]const u8) {app.logs+=1}
fn recovery_delay(app:*const App) u64 {return 1}
fn recovery_allowed(app:*App) bool {return true}
fn recovery_needed(app:*const App) bool {return true}
fn recovery_error(worker:rawptr) i32 {return 0}
fn recovery_open(path:*const u8) rawptr {return #cast(rawptr,1)}
fn recovery_submit(worker:rawptr,bytes:*const u8,length:usize) i32 {
 if record_storage==nil {
  record_arena:=mem.arena_create(60000000)
  record_storage=&mem.push_bytes_uninit(record_arena,50000000)[0]
  record_capacity=50000000
 }
 check(length<=record_capacity)
 _=buffer.copy_bytes(record_storage,bytes,length)
 record_length=length
 submissions+=1
 return 1
}
fn copy_text(output:[]u8,input:[]const u8) usize {
 check(#len(output)>=#len(input))
 if #len(input)>0 {_=buffer.copy_bytes(&output[0],&input[0],#len(input))}
 return #len(input)
}
fn add_text(output:[]u8,used:*usize,input:[]const u8) {
 used.*+=copy_text(output[used.*..],input)
}
fn work_acquire(app:*App,work:*Work,capacity:usize,label:[]const u8) bool {
 work.arena=mem.arena_create(capacity+4096)
 return work.arena!=nil
}
fn work_finish(app:*App,work:*Work,label:[]const u8) {
 mem.arena_release(work.arena)
 work.arena=nil
}
fn operation_begin(app:*App) u64 {return 0}
fn operation_end(app:*App,name:[]const u8,started:u64) {}
fn operation_bytes(app:*App,name:[]const u8,length:usize) {}
fn capture(app:*App) {
 app.recovery.time=0
 recovery_tick(app)
}
fn load_original(document:*buffer.Document,length:usize) {
 storage:=buffer.storage_create(length)
 check(storage.block!=nil)
 _=fill(&storage.bytes[0],97,length,length+1)
 check(buffer.load_storage(document,&storage,length))
}
fn assert_retained(previous:[]const u8,count:usize,app:*App) {
 check(submissions==count && buffer.equal(record_storage[..record_length],previous))
 check(app.logs>0)
}
fn main() {
 arena:=mem.arena_create(2*#sizeof(buffer.Document)+4096)
 defer mem.arena_release(arena)
 document:=buffer.allocate(arena)
 restored:=buffer.allocate(arena)
 defer buffer.release(document)
 defer buffer.release(restored)
 original:usize=41943040
 load_original(document,original)
 slot:=Slot{document:document,file:files.State{length:12}}
 slots:[1]*Slot=[&slot]
 app:=App{}
 app.documents.slots=slots[..]
 app.workspace.project_length=copy_text(app.workspace.project[..],"/tmp")
 app.config.recovery_enabled=true
 app.recovery.worker=#cast(rawptr,1)
 app.view.panes[0]=Pane{used:true,slot:0}
 // A clean reload needs no edit patch or known stamp.
 capture(&app)
 check(submissions==1)
 clean:=workspace.State{}
 defer workspace.release(&clean)
 check(workspace.decode(record_storage[..record_length],&clean))
 check(clean.buffers[0].reload && !clean.buffers[0].patched)
 // Capture an actual small replacement in a document larger than the old
 // recovery threshold, then decode and apply the production restore branch.
 slot.file.stamp=fs.Stamp{ok:true,inode:11,size:#cast(u64,original),modify_seconds:13,modify_nanos:14}
 middle:=original/2
 document.anchor=middle
 document.cursor=middle+3
 check(buffer.replace(document,"XYZ"))
 capture(&app)
 check(submissions==2)
 previous:[8192]u8=[]
 previous_length:=record_length
 _=buffer.copy_bytes(&previous[0],record_storage,record_length)
 decoded:=workspace.State{}
 defer workspace.release(&decoded)
 check(workspace.decode(record_storage[..record_length],&decoded))
 patch:=&decoded.buffers[0]
 check(patch.reload && patch.patched && patch.patch_low==middle && patch.patch_high==middle+3)
 check(buffer.equal(patch.patch,"XYZ") && patch.stamp[0]==11 && patch.stamp[1]==#cast(u64,original) && patch.stamp[2]==13 && patch.stamp[3]==14)
 load_original(restored,original)
 check(restore_patch(&app,restored,patch,slot.file.stamp))
 check(buffer.dirty_cached(restored) && buffer.equal(buffer.range(restored,middle,middle+3),"XYZ"))
 // A mismatched baseline and an invalid insertion must not be accepted.
 wrong:=slot.file.stamp
 wrong.inode+=1
 check(!restore_patch(&app,restored,patch,wrong))
 invalid:=patch.*
 zero:[1]u8=[0]
 invalid.patch=zero[..]
 check(!restore_patch(&app,restored,&invalid,slot.file.stamp))
 // Missing baseline identity fails before submission, preserving the exact
 // previously encoded recovery record.
 slot.file.stamp.ok=false
 capture(&app)
 assert_retained(previous[..previous_length],2,&app)
 slot.file.stamp.ok=true
 // Two distant one-byte edits span 40 MiB: capture records pieces of the
 // file plus only the new bytes, and restore rebuilds the same text.
 document.anchor=0
 document.cursor=1
 check(buffer.replace(document,"B"))
 document.anchor=document.length-1
 document.cursor=document.length
 check(buffer.replace(document,"C"))
 capture(&app)
 check(submissions==3)
 pieced:=workspace.State{}
 defer workspace.release(&pieced)
 check(workspace.decode(record_storage[..record_length],&pieced))
 pieces:=&pieced.buffers[0]
 check(pieces.patched && #len(pieces.pieces)>0 && #len(pieces.patch)<=8 && record_length<4096)
 load_original(restored,original)
 check(restore_patch(&app,restored,pieces,slot.file.stamp))
 check(restored.length==document.length && buffer.byte_at(restored,0)=='B' && buffer.byte_at(restored,restored.length-1)=='C')
 check(buffer.equal(buffer.range(restored,middle,middle+3),"XYZ"))
 // New text past the former 34 MB record bound still fits one record.
 inserted_arena:=mem.arena_create(40000000)
 defer mem.arena_release(inserted_arena)
 inserted:=mem.push_bytes_uninit(inserted_arena,36000000)
 _=fill(&inserted[0],98,#len(inserted),#len(inserted))
 document.anchor=1000
 document.cursor=1000
 check(buffer.replace(document,inserted))
 capture(&app)
 check(submissions==4)
 large:=workspace.State{}
 defer workspace.release(&large)
 check(workspace.decode(record_storage[..record_length],&large))
 load_original(restored,original)
 check(restore_patch(&app,restored,&large.buffers[0],slot.file.stamp))
 check(restored.length==document.length && buffer.byte_at(restored,1000)=='b' && buffer.byte_at(restored,1000+36000000-1)=='b' && buffer.byte_at(restored,1000+36000000)=='a')
 check(buffer.byte_at(restored,0)=='B' && buffer.byte_at(restored,restored.length-1)=='C')
}
'''
fixture += "\n".join(block(source, "fn " + name + "(") for name in
                     ("recovery_pieces", "recovery_apply_pieces", "recovery_patch", "session_capture", "recovery_tick"))
fixture += "\nconst RecoveryPatchLimit: usize = buffer.Capacity\nconst RecoveryRecordLimit: usize = 1073741824\nconst RecoveryPiecesMinimum: usize = 1048576\n"
restore_source = source[source.index("fn session_restore("):]
fixture += '''
fn restore_patch(app:*App,doc:*buffer.Document,saved:*const workspace.SavedBuffer,stamp:fs.Stamp) bool {
''' + block(restore_source, "if saved.patched {") + '''
 return true
}
'''
with tempfile.TemporaryDirectory(prefix="dna-recovery-capture-") as temporary:
    stage = Path(temporary)
    for module in ("buffer", "workspace", "owned_arena"):
        shutil.copytree(ROOT / "src" / module, stage / module)
    for name, contents in {
        "fs": '''pub struct Stamp {inode:u64,size:u64,modify_seconds:u64,modify_nanos:u64,ok:bool}
''',
        "files": '''use "../fs" fs
pub struct State {length:usize,stamp:fs.Stamp}
pub fn saved_stamp(state:*const State) fs.Stamp {return state.stamp}
pub fn name(state:*const State) []const u8 {return "/tmp/big.log"}
''',
        "sdl": '''pub fn ticks() u64 {return 100}
''',
    }.items():
        (stage / name).mkdir()
        (stage / name / (name + ".dyn")).write_text(contents)
    (stage / "main.dyn").write_text(fixture)
    for mode in ("debug", "release"):
        binary = stage / mode
        subprocess.run([DYN, "build", str(stage), "--" + mode,
                        "--output", str(binary)], check=True, timeout=120)
        subprocess.run([str(binary)], check=True, timeout=30)
print("PASS recovery capture: clean reload, stamped patch restore, rejected mismatch/invalid patch, missing stamp preserves prior record, distant edits restore from pieces, 36 MB insertion past the old bound (debug/release)")
