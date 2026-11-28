#!/usr/bin/env python3
"""Exercise production clipboard waiting with deterministic protocol/clock delays."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import private_display  # hides the desktop display; see tests/private_display.py

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn

source = (ROOT / 'src/platform/gui.dyn').read_text()
start = source.index('fn gui_clipboard_get(')
end = source.index('\nfn gui_free(', start)
clipboard = source[start:end]
if '--negative-control' in sys.argv:
    low = clipboard.index('  started :=')
    high = clipboard.index('    if !window_api.poll', low)
    clipboard = clipboard[:low] + '  for attempt in 0..100 {\n' + clipboard[high:]
with tempfile.TemporaryDirectory(prefix='dna-clipboard-deadline-') as directory:
    stage = Path(directory)
    for module in ('clock', 'window'):
        (stage / module).mkdir()
    (stage / 'clock/clock.dyn').write_text('''use real_time "std/time"
pub const Second:i64=real_time.Second
pub struct Instant {value:i64}
pub tick:i64=0
pub failed:bool=false
pub fn monotonic_now() Instant {
 if failed {tick-=10000000} else {tick+=10000000}
 return Instant{value:tick}
}
pub fn elapsed(start,end:Instant) i64 {
 return end.value-start.value
}
''')
    (stage / 'window/window.dyn').write_text('''use io "std/io"
use "vendor/window/events"
pub struct Window {}
pub polls:usize=0
pub goal:usize=200
pub success:bool=true
pub fn request_paste_snapshot(window:*Window) {polls=0}
pub fn poll(window:*Window) !io.IoErr {polls+=1}
pub fn next_event(window:*Window,event:*events.Event) bool {return false}
pub fn paste_pending(window:*Window) bool {return polls<goal}
pub fn paste_status(window:*Window) !io.IoErr {
 if !success {fail io.IoErr.System(-5)}
}
pub fn clipboard(window:*Window) []const u8 {return "slow clipboard"}
pub fn wait(window:*Window,milliseconds:i32) {}
''')
    (stage / 'main.dyn').write_text('''use io "std/io"
use "std/mem"
use time "./clock"
use window_api "./window"
use "vendor/window/events"
struct NativeClipboard {owner:*mem.Arena,bytes:[]u8,next:*NativeClipboard}
struct NativeGui {window:window_api.Window,deferred:[128]events.Event,
 deferred_count:usize,deferred_overflow:bool,clipboards:*NativeClipboard}
native_gui:NativeGui=NativeGui{}
''' + clipboard + '''
fn main() {
 // Two hundred 10 ms protocol polls exceed the old 100-poll cap.
 pointer:=gui_clipboard_get()
 if pointer==nil || window_api.polls!=200 {#panic("slow valid clipboard abandoned")}
 if native_gui.clipboards.bytes[0]!=115 || native_gui.clipboards.bytes[14]!=0 {#panic("clipboard snapshot ownership")}
 mem.arena_release(native_gui.clipboards.owner)
 native_gui.clipboards=nil
 window_api.success=false
 if gui_clipboard_get()!=nil {#panic("failed transfer published")}
 window_api.success=true
 window_api.goal=10000
 time.tick=0
 if gui_clipboard_get()!=nil || window_api.polls<2990 || window_api.polls>3000 {#panic("clipboard total deadline")}
 time.failed=true
 if gui_clipboard_get()!=nil {#panic("failed clock must bound clipboard wait")}
}
''')
    for mode in ('debug', 'release'):
        binary = stage / mode
        subprocess.run(['python3', str(ROOT / 'scripts/compile.py'), str(real_dyn()),
                        'build', str(stage), '--' + mode, '--output', str(binary)], check=True)
        subprocess.run([str(binary)], check=True, timeout=10)
        print('PASS clipboard deadline (' + mode + '): slow success, failed transfer, total deadline, failed clock')
