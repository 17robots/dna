#!/usr/bin/env python3
"""Exercise production pacing with a missing display mode and vsync transitions."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get('DYN', str(ROOT.parent/'dyn/compiler/build/dyn-release'))
def function(source, name):
    start = source.index('fn '+name+'(')
    body = source.index('{', start)
    depth, end = 1, body+1
    while depth:
        if source[end] == '{': depth += 1
        elif source[end] == '}': depth -= 1
        end += 1
    return source[start:end]+'\n'
view = (ROOT/'src/view.dyn').read_text()
scheduler = (ROOT/'src/scheduler.dyn').read_text()
base = '''use "./sdl" sdl
struct Animation {active:bool}
struct View {vsync,vsync_supported:bool,refresh_ms:f32,animation:Animation}
struct Config {frame_interval_ms:f32=4.0}
struct Trace {pending:u64}
struct App {view:View,config:Config,render_trace:Trace}
const RenderKey:u64=1
const RenderText:u64=2
const RenderMouse:u64=4
const RenderIme:u64=8
const RenderWindow:u64=16
'''
cases = '''fn main(){
 app:=App{config:Config{}}
 display_refresh(&app,nil)
 if app.view.refresh_ms<16.0 || animation_interval(&app)<16 {#panic("unknown native refresh spins animation at 250 Hz")}
 app.view.refresh_ms=1000.0/144.0
 if animation_interval(&app)!=7 {#panic("timer wakes before the fractional refresh deadline")}
 app.config.frame_interval_ms=20.0
 if animation_interval(&app)!=20 {#panic("configured animation floor ignored")}
 app.view.vsync_supported=true
 app.view.animation.active=true
 present_pacing(&app,nil)
 if !app.view.vsync || sdl.last!=1 {#panic("animation not synchronized")}
 if animation_interval(&app)!=20 {#panic("vsync floor ignored")}
 app.render_trace.pending=RenderText
 present_pacing(&app,nil)
 if app.view.vsync || sdl.last!=0 {#panic("input delayed by animation vsync")}
 app.render_trace.pending=0
 app.view.animation.active=false
 present_pacing(&app,nil)
 if app.view.vsync {#panic("settled frame retains animation pacing")}
 app.view.vsync_supported=false
 app.view.animation.active=true
 present_pacing(&app,nil)
 if app.view.vsync {#panic("unsupported vsync enabled")}
}
'''
with tempfile.TemporaryDirectory(prefix='dna-presentation-') as temporary:
    stage=Path(temporary)
    (stage/'sdl').mkdir()
    (stage/'sdl/sdl.dyn').write_text('''pub struct DisplayMode {refresh:f32}
pub last:i32=-1
pub fn render_vsync(renderer:rawptr,interval:i32)bool {last=interval
 return true}
pub fn window_display(window:rawptr)u32{return 0}
pub fn display_mode(display:u32)*const DisplayMode{return nil}
''')
    (stage/'main.dyn').write_text(base+function(view,'present_pacing')+function(scheduler,'animation_interval')+function(scheduler,'display_refresh')+cases)
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary=stage/'test'
        subprocess.run(['python3',str(ROOT/'scripts/compile.py'),DYN,'build',str(stage),'--'+mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([str(binary)],check=True)
        print('PASS presentation pacing ('+mode+'): missing/144Hz refresh, configured floor, input bypass, animation and idle')
# Pacing must use animation state computed by this draw, immediately before swap.
draw=view[view.index('fn draw('):view.index('fn draw_document(')]
assert draw.index('animation_begin(')<draw.index('present_pacing(')<draw.index('sdl.present('), 'presentation uses previous frame animation state'
