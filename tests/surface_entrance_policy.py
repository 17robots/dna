#!/usr/bin/env python3
"""RAD-style panel edges settle without gaps, restart or delayed input."""
import os
from pathlib import Path
import shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
DYN=os.environ.get('DYN',str(ROOT.parent/'dyn/compiler/build/dyn-release'))
def function(source,name):
    start=source.index('fn '+name+'(');end=source.index('{',start)+1;depth=1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return source[start:end]+'\n'
s=(ROOT/'src/animation.dyn').read_text()
base='''use "./motion" motion
use "./sdl" sdl
struct Config {popup_animation_ms:f32=40.0,popup_transitions:bool=true}
struct Animation {now,geometry_elapsed:f32,active,surfaces_ready,resized,geometry_active,geometry_retargeted:bool}
struct View {animation:Animation,reduced_motion:bool}
struct Pointer {dragging:bool}
struct Trace {pending:u32}
struct App {config:Config,view:View,pointer:Pointer,render_trace:Trace}
const RenderKey:u32=2
const RenderText:u32=4
const RenderMouse:u32=8
const RenderIme:u32=32
const RenderWindow:u32=16
fn frame(app:*App,now,elapsed:f32,cause:u32,changed:bool){
 app.view.animation.now=now
 app.view.animation.geometry_elapsed=elapsed
 app.view.animation.geometry_retargeted=changed
 app.view.animation.active=false
 app.view.animation.geometry_active=false
 app.render_trace.pending=cause
}
'''
cases='''fn main() {
 app:=App{config:Config{}}
 left:=motion.Rectangle{}
 right:=motion.Rectangle{}
 full:=sdl.PixelRect{width:1000,height:600}
 first:=sdl.PixelRect{width:500,height:600}
 second:=sdl.PixelRect{x:500,width:500,height:600}
 frame(&app,0.0,8.0,0,false)
 if animated_rectangle(&app,&left,full).width!=1000 || left.active {#panic("startup must land immediately")}
 app.view.animation.surfaces_ready=true
 motion.rectangle_seed(&right,[1000.0,0.0,1000.0,600.0],0.0)
 frame(&app,0.0,8.0,RenderKey,true)
 a:=animated_rectangle(&app,&left,first)
 b:=animated_rectangle(&app,&right,second)
 if a.width<=500 || a.width>=1000 || b.width<=0 || b.width>=500 || !app.view.animation.active {#panic("new split must grow spatially from its shared edge")}
 if a.x+a.width!=b.x || b.x+b.width!=1000 {#panic("opening split has a gap or overlap")}
 previous:=b.width
 for i in 1..25 {
  frame(&app,#cast(f32,i)*16.0,16.0,0,false)
  a=animated_rectangle(&app,&left,first)
  b=animated_rectangle(&app,&right,second)
  if a.x+a.width!=b.x || b.x+b.width!=1000 || b.width<previous {#panic("panel growth is not adjacent and monotonic")}
  previous=b.width
 }
 if left.active || right.active || a.width!=500 || b.width!=500 {#panic("panel edges must settle exactly")}
 // Closing copies the survivor's current geometry, then expands it.
 frame(&app,500.0,8.0,RenderKey,true)
 a=animated_rectangle(&app,&left,full)
 if a.width<=500 || a.width>=1000 {#panic("closing sibling must expand surviving view")}
 // Another layout command retargets from current edges without jumping.
 old:=left.current[2]
 motion.rectangle_seed(&right,[old,0.0,old,600.0],500.0)
 frame(&app,516.0,16.0,RenderKey,true)
 a=animated_rectangle(&app,&left,first)
 b=animated_rectangle(&app,&right,second)
 if a.x+a.width!=b.x || a.width> #cast(i32,old+0.5) {#panic("rapid retarget broke shared boundary or continuity")}
 frame(&app,517.0,1.0,RenderText,false)
 if animated_rectangle(&app,&left,first).width!=500 || left.active {#panic("genuine input must finish existing geometry motion")}
 for reason in 0..6 {
  app.view.reduced_motion=reason==0
  app.config.popup_transitions=reason!=1
  app.config.popup_animation_ms=40.0
  if reason==2 {app.config.popup_animation_ms=0.0}
  app.pointer.dragging=reason==3
  sdl.terminal=reason==4
  app.view.animation.resized=reason==5
  frame(&app,1000.0,8.0,RenderKey,true)
  if animated_rectangle(&app,&left,full).width!=1000 || app.view.animation.active {#panic("motion opt-out or interactive resize must snap")}
 }
}
'''
with tempfile.TemporaryDirectory(prefix='dna-pane-policy-') as temporary:
    work=Path(temporary);shutil.copytree(ROOT/'src/motion',work/'motion');(work/'sdl').mkdir()
    (work/'sdl/sdl.dyn').write_text('pub struct PixelRect{x,y,width,height:i32}\npub terminal:bool\npub fn tui_active()bool{return terminal}\n')
    helpers=''.join(function(s,name) for name in ('surface_motion_enabled','rectangle_edges','animated_rectangle'))
    (work/'main.dyn').write_text(base+helpers+cases)
    for mode in ('debug','release'):
        binary=work/'test'
        subprocess.run(['python3',str(ROOT/'scripts/compile.py'),DYN,'build',str(work),'--'+mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([str(binary)],check=True)
        print(f'PASS panel geometry policy ({mode}): shared edges, monotonic growth, close expansion, retarget, exact settle, input and motion opt-outs',flush=True)
