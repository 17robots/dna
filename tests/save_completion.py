#!/usr/bin/env python3
"""Production async save completion: sparse slots and safe close decisions."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get("DYN") or subprocess.check_output(
    ["python3", str(ROOT / "scripts/dyn_path.py")], text=True).strip()


def function(source, name):
    start = source.index("fn " + name + "(")
    body = source.index("{", start)
    depth, end = 1, body + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


source = (ROOT / "src/file_actions.dyn").read_text()
fixture = '''use "./buffer" buffer
use "./files" files
use "./owner" arena_owner
use "./thread" thread
struct SaveTask {arena:rawptr,worker:rawptr,identity:u64,job:files.SaveJob}
struct Slot {identity:u64,document:*buffer.Document,file:files.State,syntax_checked:bool,syntax_revision:u64}
struct SaveSequence {active:bool,waiting:bool}
struct Documents {slots:[]*Slot,count:usize,active:usize,save_task:*SaveTask,saving:SaveSequence,quit_after_save:bool,closing_one:bool}
enum Panel {None}
struct Prompt {panel:Panel}
struct App {documents:Documents,scratch:rawptr,prompt_state:Prompt,closed:usize,canceled:usize}
fn document_lifecycle_changed(app:*App,index:usize) {}
fn slot_syntax_release(slot:*Slot) {}
fn plugin_event(app:*App,event:[]const u8) {}
fn file_config_invalidate(app:*App) {}
fn notice(app:*App,text:[]const u8) {}
fn request_quit(app:*App) {}
fn close_clean(app:*App) {app.closed+=1}
fn save_cancel(app:*App) {app.canceled+=1
 app.documents.quit_after_save=false
 app.documents.saving.active=false
 app.documents.saving.waiting=false}
fn check(value:bool) {if !value {#panic("unsafe async save completion")}}
fn run_case(changed:bool,moved:bool,missing:bool,close:bool) {
 slots:[8]Slot=[]
 pointers:[8]*Slot=[]
 for index in 0..8 {pointers[index]=&slots[index]}
 document:=buffer.Document{dirty:changed}
 slots[7].document=&document
 slots[7].identity=55
 task:=SaveTask{identity:55}
 if missing {slots[7].identity=56}
 app:=App{}
 app.documents.slots=pointers[..]
 app.documents.count=1
 app.documents.active=7
 if moved {app.documents.active=0}
 app.documents.save_task=&task
 app.documents.quit_after_save=close
 app.documents.closing_one=close
 files.finished=0
 files.aborted=0
 arena_owner.released=0
 save_join(&app)
 check(app.documents.save_task==nil && arena_owner.released==1)
 if missing {
   check(files.finished==0 && files.aborted==1 && app.canceled==1 && app.closed==0)
 } else {
   check(files.finished==1 && files.aborted==0 && app.canceled==0)
   expected:usize=0
   if close && !changed && !moved {expected=1}
   check(app.closed==expected && !app.documents.quit_after_save)
 }
}
fn main() {
 run_case(false,false,false,false)
 run_case(false,false,false,true)
 run_case(true,false,false,true)
 run_case(false,true,false,true)
 run_case(true,true,false,true)
 run_case(false,false,true,true)
}
'''
fixture += "\n".join(function(source, name) for name in ("save_join", "save_completed"))
modules = {
    "buffer": '''pub struct Document {dirty:bool}
pub fn dirty_cached(document:*Document) bool {return document.dirty}
pub fn checkpoint(document:*Document) {}
pub fn equal(a:[]const u8,b:[]const u8) bool {
 if #len(a)!=#len(b) {return false}
 for index in 0..#len(a) {if a[index]!=b[index] {return false}}
 return true}
''',
    "files": '''use "../buffer" buffer
pub struct State {}
pub struct SaveJob {}
pub finished:usize=0
pub aborted:usize=0
pub fn name(state:*State) []const u8 {return "example.txt"}
pub fn save_finish(job:*SaveJob,state:*State,document:*buffer.Document,scratch:rawptr) []const u8 {finished+=1
 return ""}
pub fn save_abort(job:*SaveJob) {aborted+=1}
''',
    "owner": '''pub released:usize=0
pub fn release(arena:rawptr) {released+=1}
''',
    "thread": '''pub struct Result {ok:bool}
pub fn join(worker:rawptr) Result {return Result{ok:true}}
''',
}
with tempfile.TemporaryDirectory(prefix="dna-save-completion-") as temporary:
    stage = Path(temporary)
    (stage / "main.dyn").write_text(fixture)
    for name, contents in modules.items():
        (stage / name).mkdir()
        (stage / name / (name + ".dyn")).write_text(contents)
    for mode in ("debug", "release"):
        binary = stage / mode
        subprocess.run([DYN, "build", str(stage), "--" + mode,
                        "--output", str(binary)], check=True, timeout=120)
        subprocess.run([str(binary)], check=True, timeout=10)
print("PASS async save completion: sparse slots, closed owners, clean close, edits and focus changes (debug/release)")
