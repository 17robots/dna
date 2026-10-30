#!/usr/bin/env python3
"""Verify syntax glyphs equal a single correctly colored text raster."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from native_gpu_probe import install as gpu_probe
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-syntax-frames-',dir=ROOT/'build') as temporary:
    work=Path(temporary);stage=work/'src';shutil.copytree(ROOT/'src',stage)
    for name in ('native_typing_frame_smoke.dyn','native_syntax_single_pass_smoke.dyn'):
        shutil.copyfile(ROOT/'tests/editor'/name,stage/name)
    gui=stage/'platform/gui.dyn';source=gui.read_text()
    begin=source.index('fn sdl_present(');end=source.index('\nfn sdl_scale(',begin)
    source=source[:begin]+'fn sdl_present(renderer:rawptr)bool{return true}\n'+source[end:]
    source+='''\npub fn typing_probe_pixels() []const u8 {return native_gui.surface.pixels}
pub fn typing_probe_resize(width,height:i32) {
 native_gui.window.width=width
 native_gui.window.height=height
 if !native_resize() {#panic("syntax frame resize")}
}
'''
    gui.write_text(gpu_probe(source))
    (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer:rawptr,window:rawptr,input_storage:[]u8){
 native_syntax_single_pass_smoke(app,typography,renderer,window,NativeTypingFrameProbe{pixels:sdl.typing_probe_pixels,resize:sdl.typing_probe_resize})
}
fn finish_probe(app:*App){}
''')
    env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary=work/'editor'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([str(binary)],env=env,check=True,timeout=90)
        print(f'PASS native syntax single paint ({mode}): glyph antialias and full-line shaping match independent one-pass text raster; uniform/mixed styles, Latin ligatures, combining marks, RTL and tabs',flush=True)
