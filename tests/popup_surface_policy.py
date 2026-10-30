#!/usr/bin/env python3
"""Exercise the shared popup geometry controller with deterministic frame time."""
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
source='''use "./motion" motion
use "./sdl" sdl
use "./settings" settings
struct Config {popup_animation_ms:f32=40.0,popup_transitions:bool=true,placement:settings.Placement}
struct Animation {now:f32,active,surfaces_ready,resized,geometry_active:bool,geometry_elapsed:f32=8.0,surface_geometry:[8]motion.Rectangle,surface_seen:[8]u64}
struct View {animation:Animation,reduced_motion:bool}
struct Pointer {dragging:bool}
struct Ui {frame:u64}
struct App {config:Config,view:View,pointer:Pointer,render_pending:u32,ui:Ui}
const SurfaceExplorer:usize=4
const RenderKey:u32=2
const RenderText:u32=4
const RenderMouse:u32=8
const RenderIme:u32=32
const RenderWindow:u32=16
fn answering_input(app:*const App)bool{return (app.render_pending&(RenderKey|RenderText|RenderMouse|RenderIme|RenderWindow))!=0}
placed_rects:[8]sdl.Rect
placed_frames:[8]u64
fn place_of(app:*const App,surface:usize)settings.Placement{return app.config.placement}
'''+function(s,'surface_motion_enabled')+function(s,'animated_surface')+'''
fn equal(a,b:sdl.Rect) bool {return a.x==b.x && a.y==b.y && a.width==b.width && a.height==b.height}
fn dock_case(side:u8) {
 app:=App{config:Config{}}
 app.config.placement=settings.Placement{mode:settings.PlaceDock,side:side}
 app.view.animation.surfaces_ready=true
 app.ui.frame=10
 target:=sdl.Rect{width:1000.0,height:600.0}
 pane_target:[4]f32=[0.0,0.0,1000.0,600.0]
 if side==0 {target.width=200.75
  pane_target[0]=200.0}
 else if side==1 {target.x=799.25
  target.width=200.75
  pane_target[2]=799.0}
 else if side==2 {target.height=120.75
  pane_target[1]=120.0}
 else {target.y=479.25
  target.height=120.75
  pane_target[3]=479.0}
 pane:=motion.Rectangle{}
 motion.rectangle_seed(&pane,[0.0,0.0,1000.0,600.0],0.0)
 for frame in 10..40 {
  app.ui.frame=#cast(u64,frame)
  step:=8.0
  if frame>10 {step=16.0}
  app.view.animation.geometry_elapsed=step
  app.view.animation.now+=step
  shown:=animated_surface(&app,3,target,1.0)
  motion.rectangle_step(&pane,pane_target,app.view.animation.now,step,70.0,false)
  if side==0 && shown.x+shown.width!=#cast(f32,#cast(i32,pane.current[0]+0.5)) {#panic("left dock lost shared animated boundary")}
  if side==1 && shown.x!=#cast(f32,#cast(i32,pane.current[2]+0.5)) {#panic("right dock lost shared animated boundary")}
  if side==2 && shown.y+shown.height!=#cast(f32,#cast(i32,pane.current[1]+0.5)) {#panic("top dock lost shared animated boundary")}
  if side==3 && shown.y!=#cast(f32,#cast(i32,pane.current[3]+0.5)) {#panic("bottom dock lost shared animated boundary")}
  if !equal(shown,placed_rects[3]) {#panic("docked placement hits differ from paint")}
 }
}
fn main() {
 for side in 0..4 {dock_case(#cast(u8,side))}
 app:=App{config:Config{}}
 app.ui.frame=1
 target:=sdl.Rect{x:100.25,y:80.75,width:600.5,height:400.5}
 if !equal(animated_surface(&app,0,target,1.0),target) {#panic("startup surface must retain exact placement")}
 app.view.animation.surfaces_ready=true
 app.ui.frame=2
 app.render_pending=RenderKey
 first:=animated_surface(&app,1,target,1.0)
 if first.width>=target.width || first.height>=target.height || !app.view.animation.active {#panic("new surface must settle spatially despite its opening key")}
 if !equal(first,placed_rects[1]) || placed_frames[1]!=2 {#panic("placement hit bounds must match drawn popup")}
 // Sizing queries may request the same surface twice while building one frame.
 repeated:=animated_surface(&app,1,target,1.0)
 if !equal(first,repeated) {#panic("same-frame sizing query advanced surface twice")}
 app.render_pending=0
 app.ui.frame=3
 app.view.animation.now=16.0
 app.view.animation.geometry_elapsed=16.0
 next:=animated_surface(&app,1,target,1.0)
 if next.width<=first.width || next.width>=target.width {#panic("unchanged surface restarted or snapped")}
 app.ui.frame=4
 app.render_pending=RenderText
 if !equal(animated_surface(&app,1,target,1.0),target) {#panic("typing must immediately finish an open popup")}
 // Hidden for one drawn frame, then reopened: a fresh entrance starts.
 app.render_pending=0
 app.ui.frame=6
 if equal(animated_surface(&app,1,target,1.0),target) {#panic("reopened surface failed to animate")}
 for frame in 7..100 {
  app.ui.frame=#cast(u64,frame)
  app.view.animation.now+=16.0
  _=animated_surface(&app,1,target,1.0)
 }
 app.view.animation.active=false
 app.view.animation.geometry_active=false
 app.ui.frame=100
 if !equal(animated_surface(&app,1,target,1.0),target) || app.view.animation.active {#panic("settled surface must preserve exact target and idle")}
 // A background size update retargets the current rectangle without reseeding.
 larger:=target
 larger.height+=100.0
 app.ui.frame=101
 changed:=animated_surface(&app,1,larger,1.0)
 if changed.height<=target.height || changed.height>=larger.height {#panic("background surface resize must retarget continuously")}
 for reason in 0..6 {
  app.ui.frame+=2
  app.view.reduced_motion=reason==0
  app.config.popup_transitions=reason!=1
  app.config.popup_animation_ms=40.0
  if reason==2 {app.config.popup_animation_ms=0.0}
  app.pointer.dragging=reason==3
  sdl.terminal=reason==4
  app.view.animation.resized=reason==5
  app.view.animation.active=false
  if !equal(animated_surface(&app,2,target,1.0),target) || app.view.animation.active {#panic("motion opt-out must preserve exact popup placement")}
 }
}
'''
with tempfile.TemporaryDirectory(prefix='dna-popup-policy-') as temporary:
 work=Path(temporary);shutil.copytree(ROOT/'src/motion',work/'motion');(work/'sdl').mkdir()
 (work/'sdl/sdl.dyn').write_text('pub struct Rect{x,y,width,height:f32}\npub terminal:bool\npub fn tui_active()bool{return terminal}\n')
 (work/'settings').mkdir()
 (work/'settings/settings.dyn').write_text('pub const PlaceDock:u8=2\npub struct Placement{mode,side:u8}\n')
 (work/'main.dyn').write_text(source)
 for mode in ('debug','release'):
  binary=work/'test'
  subprocess.run(['python3',str(ROOT/'scripts/compile.py'),DYN,'build',str(work),'--'+mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
  subprocess.run([str(binary)],check=True)
  print(f'PASS popup geometry policy ({mode}): spatial open, duplicate queries, exact hits, input, reopen, background retarget, four dock boundaries and opt-outs',flush=True)
