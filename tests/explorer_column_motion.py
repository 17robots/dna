#!/usr/bin/env python3
"""Editable explorer columns settle spatially without deferring navigation/input."""
import os
from pathlib import Path
import shutil, subprocess, sys, tempfile
ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get('DYN', str(ROOT.parent / 'dyn/compiler/build/dyn-release'))
s = (ROOT / 'src/explorer.dyn').read_text()
start = s.index('fn explorer_columns_progress(')
end = s.index('\nfn draw_explorer(', start)
source = '''use "./motion" motion
struct Config {popup_animation_ms:f32=40.0,popup_transitions:bool=true}
struct Animation {now:f32,active,surfaces_ready,resized,geometry_active:bool,geometry_elapsed:f32=8.0}
struct View {animation:Animation,reduced_motion:bool}
struct Pointer {dragging:bool}
struct Ui {frame:u64}
struct Explorer {columns_geometry:motion.Rectangle,columns_frame:u64}
struct App {config:Config,view:View,pointer:Pointer,render_pending:u32,ui:Ui,explorer:Explorer}
const RenderKey:u32=2
const RenderText:u32=4
const RenderMouse:u32=8
const RenderIme:u32=32
const RenderWindow:u32=16
fn answering_input(app:*const App)bool{return (app.render_pending&(RenderKey|RenderText|RenderMouse|RenderIme|RenderWindow))!=0}
terminal:bool
fn surface_motion_enabled(app:*const App)bool{return !terminal && !app.view.reduced_motion && app.config.popup_transitions && app.config.popup_animation_ms>0.0 && !app.pointer.dragging}
''' + s[start:end] + '''
fn main() {
 app:=App{config:Config{}}
 app.view.animation.surfaces_ready=true
 app.view.animation.geometry_elapsed=8.0
 app.ui.frame=10
 if explorer_columns_progress(&app,1)!=1.0 {#panic("initial explorer layout")}
 app.ui.frame+=1
 app.render_pending=RenderKey
 first:=explorer_columns_progress(&app,2)
 if first<=1.0 || first>=2.0 || !app.view.animation.active {#panic("new right pane must grow beside anchored columns")}
 if explorer_columns_progress(&app,2)!=first {#panic("same frame advanced twice")}
 old_width:=explorer_column_extent(first,0,1000.0,8.0)
 new_width:=explorer_column_extent(first,1,1000.0,8.0)
 if old_width<=new_width || new_width<=0.0 {#panic("new pane must start smaller than its anchored parent")}
 gap:=8.0*explorer_column_fraction(first,1)
 if old_width+gap+new_width<999.9 || old_width+gap+new_width>1000.1 {#panic("columns lost shared boundary")}
 app.ui.frame+=1
 app.render_pending=0
 next:=explorer_columns_progress(&app,2)
 if next<=first || next>=2.0 {#panic("column continuation restarted")}
 app.ui.frame+=1
 app.render_pending=RenderText
 if explorer_columns_progress(&app,2)!=2.0 {#panic("typing must finish movement immediately")}
 app.ui.frame+=1
 app.render_pending=RenderKey
 back:=explorer_columns_progress(&app,1)
 if back<=1.0 || back>=2.0 {#panic("rightmost pane must retract")}
 app.ui.frame+=1
 forward:=explorer_columns_progress(&app,3)
 if forward<=back || forward>=3.0 {#panic("rapid reversal failed")}
 app.render_pending=0
 for frame in 16..100 {
  app.ui.frame=#cast(u64,frame)
  app.view.animation.active=false
  _=explorer_columns_progress(&app,3)
 }
 if app.view.animation.active {#panic("settled columns must stop redrawing")}
 for reason in 0..6 {
  app.ui.frame+=1
  app.view.reduced_motion=reason==0
  app.config.popup_transitions=reason!=1
  app.config.popup_animation_ms=40.0
  if reason==2 {app.config.popup_animation_ms=0.0}
  app.pointer.dragging=reason==3
  terminal=reason==4
  app.view.animation.resized=reason==5
  app.view.animation.active=false
  if explorer_columns_progress(&app,1)!=1.0 || app.view.animation.active {#panic("column motion opt-out")}
  app.explorer.columns_geometry.ready=false
 }
}
'''
if '--negative-control' in sys.argv:
 source=source.replace('motion.rectangle_step(state, edges, animation.now, elapsed, rate, immediate)', 'motion.rectangle_seed(state, edges, animation.now)')
with tempfile.TemporaryDirectory(prefix='dna-explorer-columns-') as temporary:
 work = Path(temporary)
 shutil.copytree(ROOT/'src/motion', work/'motion')
 (work/'main.dyn').write_text(source)
 for mode in os.environ.get('DNA_SMOKE_MODES', 'debug release').split():
  binary=work/'test'
  subprocess.run(['python3',str(ROOT/'scripts/compile.py'),DYN,'build',str(work),'--'+mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
  if '--negative-control' in sys.argv:
   result=subprocess.run([str(binary)],capture_output=True,text=True)
   assert result.returncode and 'new right pane must grow beside anchored columns' in result.stderr, result.stdout+result.stderr
   print(f'PASS explorer column negative control ({mode}): disabled spatial movement detected',flush=True)
   continue
  subprocess.run([str(binary)],check=True)
  print(f'PASS explorer column motion ({mode}): navigation, reversal, immediate typing, settle and opt-outs',flush=True)
