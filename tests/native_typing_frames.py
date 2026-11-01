#!/usr/bin/env python3
"""Compare complete native edit frames against unchanged and uncached redraws."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from native_gpu_probe import install as gpu_probe
# This correctness oracle redraws hundreds of full frames at up to 1920x1080.
# Hosted LLVMpipe runs consume CPU throughout and need a larger bounded budget
# than startup smoke; latency/performance gates are separate tests.
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-typing-frames-',dir=ROOT/'build') as temporary:
    work=Path(temporary);stage=work/'src';shutil.copytree(ROOT/'src',stage)
    shutil.copyfile(ROOT/'tests/editor/native_typing_frame_smoke.dyn',stage/'native_typing_frame_smoke.dyn')
    gui=stage/'platform/gui.dyn';source=gui.read_text()
    begin=source.index('fn sdl_present(');end=source.index('\nfn sdl_scale(',begin)
    present='fn sdl_present(renderer:rawptr)bool{return true}\n'
    if '--negative-control' in sys.argv:
        present='''typing_probe_present_count:usize=0
fn sdl_present(renderer:rawptr)bool{
 typing_probe_present_count+=1
 if typing_probe_present_count%3==1 {native_memory.zero(native_gui.surface.pixels)}
 return true
}
'''
    source=source[:begin]+present+source[end:]
    source+='''\npub fn typing_probe_pixels() []const u8 {return native_gui.surface.pixels}
pub fn typing_probe_resize(width,height:i32) {
 native_gui.window.width=width
 native_gui.window.height=height
 if !native_resize() {#panic("typing frame resize")}
}
'''
    gui.write_text(gpu_probe(source))
    (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer:rawptr,window:rawptr,input_storage:[]u8){
 native_typing_frame_smoke(app,typography,renderer,window,NativeTypingFrameProbe{pixels:sdl.typing_probe_pixels,resize:sdl.typing_probe_resize})
}
fn finish_probe(app:*App){}
''')
    env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary=work/'editor'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        if '--negative-control' in sys.argv:
            result=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=240)
            assert result.returncode!=0 and 'initial cached/fresh frame mismatch' in result.stderr, result.stdout+result.stderr
            print(f'PASS native typing negative control ({mode}): injected whole-frame blanking is detected',flush=True)
            continue
        subprocess.run([str(binary)],env=env,check=True,timeout=240)
        print(f'PASS native typing framebuffer ({mode}): ASCII/Unicode, backspace/newline, long line and vertical scroll; cached frame equals unchanged and forced-fresh draw at640/960/1920',flush=True)
