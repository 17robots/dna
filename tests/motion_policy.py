#!/usr/bin/env python3
"""Deterministic production motion/presentation policy, without timers or a GPU."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
DYN=os.environ.get('DYN',str(ROOT.parent/'dyn/compiler/build/dyn-release'))
def function(source,name):
    start=source.index('fn '+name+'(')
    body=source.index('{',start)
    depth,end=1,body+1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return source[start:end]+'\n'
BASE='''use "./motion" motion
use "./sdl" sdl
struct Animation { now:f32, line:f32, active:bool, reset:bool, panel:Panel }
enum Panel { None }
struct View { reduced_motion:bool, insert:bool, animation:Animation, scroll_x,scroll_y:f32 }
struct Config { popup_animation_ms:f32=40.0, smooth_cursor:bool=true, smooth_scroll:bool=true, scroll_animation_ms:f32=100.0, cursor_animation_ms:f32=100.0, cursor_thickness:f32=2.0 }
struct Explorer {insert:bool,scroll_x,scroll_y:f32}
struct App { view:View, config:Config, explorer:Explorer }
struct UiBox { hot:motion.Tween, selected:motion.Tween }
struct UiState { boxes:[1]UiBox, menu_open:motion.Tween }
struct Typography { cell:f32=8.0, line:f32=20.0, points:f32=16.0, scale:f32=1.0 }
struct CursorTrail { unused:u32 }
struct Visual { cursor_x:motion.Tween, cursor_y:motion.Tween, trail:CursorTrail }
struct AnimatedView {x,y,cursor_x,cursor_y:motion.Tween,trail:CursorTrail}
struct Rgb { red,green,blue:u8 }
struct Theme { cursor:Rgb }
trail_active:bool=false
trail_snapped:bool=false
hovered:bool=false
fn theme() Theme { return Theme{} }
fn paint(renderer:rawptr,color:Rgb) bool { return true }
fn draw_cursor_trail(renderer:rawptr,app:*App,trail:*CursorTrail,target:sdl.Rect,snap:bool,color:Rgb) bool {trail_snapped=snap
 return trail_active}
fn ui_hovered(ui:*UiState,index:usize) bool { return hovered }
fn key_menu_is(panel:Panel) bool { return false }
fn vim_menu_active(app:*const App) bool { return false }
'''
SDL='''pub struct Rect { x,y,width,height:f32 }
pub last:Rect
pub fills:usize
pub fn fill(renderer:rawptr,rect:*const Rect) bool {last=rect.*
 fills+=1
 return true}
'''
animation=(ROOT/'src/animation.dyn').read_text()
ui=(ROOT/'src/ui.dyn').read_text()
picker=(ROOT/'src/picker_view.dyn').read_text()
view=(ROOT/'src/view.dyn').read_text()
helpers=''.join(function(animation,name) for name in ('animated_value','animated_follow','distance','cursor_step_snaps','animated_scroll'))
if 'fn editing_scroll_visible(' in animation:helpers+=function(animation,'editing_scroll_visible')
# Popup paint/hit geometry is covered by popup_surface_motion.py.
primary_start=view.index('  cursor_target_x :=')
primary_end=view.index('  if focused {\n    draw_extra_cursors',primary_start)
primary=view[primary_start:primary_end]
CASES={
'reversal':'''fn main() {
 value:=motion.Tween{}
 _=motion.follow(&value,0.0,0.0,100.0,false)
 _=motion.follow(&value,100.0,0.0,100.0,false)
 _=motion.follow(&value,100.0,10.0,100.0,false)
 before:=value.value
 _=motion.follow(&value,-100.0,11.0,100.0,false)
 if value.value>before {#panic("reversed scroll initially moves away from its new target")}
 for i in 1..100 {
  next:=motion.follow(&value,-100.0,11.0+#cast(f32,i)*2.0,100.0,false)
  if next>before || next< -100.001 {#panic("reversed scroll is not bounded monotonic")}
  before=next
 }
}
''',
'near_target':'''fn main() {
 value:=motion.Tween{}
 _=motion.follow(&value,0.0,0.0,100.0,false)
 _=motion.follow(&value,100.0,0.0,100.0,false)
 _=motion.follow(&value,100.0,10.0,100.0,false)
 target:=value.value+1.0
 before:=value.value
 for i in 1..100 {
  next:=motion.follow(&value,target,10.0+#cast(f32,i)*2.0,100.0,false)
  if next<before || next>target+0.001 {#panic("short scroll retarget overshoots")}
  before=next
 }
}
''',
'selection':function(ui,'ui_animate')+'''fn main() {
 app:=App{}
 ui:=UiState{}
 ui_animate(&app,&ui,0,false)
 app.view.animation.now=20.0
 hovered=true
 ui_animate(&app,&ui,0,true)
 if ui.boxes[0].selected.value!=1.0 {#panic("logical selection highlight waits for animation")}
 if ui.boxes[0].hot.value!=0.0 || !ui.boxes[0].hot.active {#panic("hover decoration lost its configured transition")}
 app.view.animation.now=40.0
 ui_animate(&app,&ui,0,true)
 if ui.boxes[0].hot.value<=0.0 || ui.boxes[0].hot.value>=1.0 {#panic("hover decoration timing")}
 ui_animate(&app,&ui,0,false)
 if ui.boxes[0].selected.value!=0.0 {#panic("old logical selection lingers")}
}
''',
'primary_caret':'''fn draw_primary(app:*App,visual:*Visual,typography:*Typography) {
 renderer:rawptr=nil
 origin:f32=0.0
 caret_x:f32=80.0
 margin:f32=0.0
 caret_y:f32=120.0
 scroll_x:f32=0.0
 scroll_y:f32=0.0
 cursor_width:f32=8.0
 focused:=true
'''+primary+'''}
fn main() {
 app:=App{}
 visual:=Visual{}
 typography:=Typography{}
 motion.snap(&visual.cursor_x,0.0)
 motion.snap(&visual.cursor_y,0.0)
 draw_primary(&app,&visual,&typography)
 if sdl.fills!=1 || sdl.last.x!=80.0 || sdl.last.y!=120.0 {#panic("primary caret lags its logical target")}
 trail_active=true
 draw_primary(&app,&visual,&typography)
 if sdl.fills!=2 {#panic("decorative trail hides the actual caret")}
 if trail_snapped {#panic("drawing the same caret twice cancels its jump decoration")}
}
''',
}
explorer=(ROOT/'src/explorer.dyn').read_text()
start=explorer.index('  cursor_x := animated_follow(')
end=explorer.index('  line_layout_draw(',start)
CASES['explorer_caret']='''fn main() {
 app_value:=App{config:Config{}}
 app:=&app_value
 visual:=Visual{}
 typography:=Typography{}
 motion.snap(&visual.cursor_x,0.0)
 motion.snap(&visual.cursor_y,0.0)
 renderer:rawptr=nil
 origin:f32=0.0
 x:f32=80.0
 top:f32=0.0
 y:f32=120.0
 scroll_x:f32=0.0
 scroll_y:f32=0.0
 cursor_width:f32=8.0
 cursor_snap:=false
'''+explorer[start:end]+'''
 if sdl.fills!=1 || sdl.last.x!=80.0 || sdl.last.y!=120.0 {#panic("explorer primary caret lags")}
}
'''
terminal=(ROOT/'src/terminal.dyn').read_text()
start=terminal.index('  cursor_x := animated_follow(')
end=terminal.index('  focus: i32',start)
CASES['terminal_caret']='''struct Terminal {cursor_x:motion.Tween,cursor_y:motion.Tween,input:bool}
struct Slot {terminal:Terminal}
captured_x:f32
captured_y:f32
fn terminal_cursor_rect(target:rawptr,x,y,width,height:f32) {captured_x=x
 captured_y=y}
fn main() {
 app_value:=App{config:Config{}}
 app:=&app_value
 slot:=Slot{}
 typography:=Typography{}
 motion.snap(&slot.terminal.cursor_x,0.0)
 motion.snap(&slot.terminal.cursor_y,0.0)
 column:i32=10
 row:i32=6
 terminal_snap:=false
 target:rawptr=nil
'''+terminal[start:end]+'''
 if captured_x!=80.0 || captured_y!=120.0 {#panic("terminal primary caret lags")}
}
'''
start=view.index('  animated_scroll(app, visual, app.view.scroll_x')
end=view.index('  scroll_x := visual.x.value',start)
CASES['editing_viewport']='''fn draw_edit_scroll(app:*App,visual:*AnimatedView,focused:bool,caret_x,caret_y:f32) {
 visible_width:f32=100.0
 visible_height:f32=500.0
 typography:=Typography{}
'''+view[start:end]+'''}
fn main() {
 app:=App{}
 app.view.animation.line=20.0
 app.view.insert=true
 app.view.scroll_x=100.0
 app.view.scroll_y=200.0
 visual:=AnimatedView{}
 reference:=AnimatedView{}
 motion.snap(&visual.x,0.0)
 motion.snap(&visual.y,0.0)
 motion.snap(&reference.x,0.0)
 motion.snap(&reference.y,0.0)
 animated_scroll(&app,&reference,100.0,200.0,500.0,false)
 draw_edit_scroll(&app,&visual,true,150.0,400.0)
 if visual.x.value!=100.0 {#panic("edited text is clipped by lagging horizontal scroll")}
 if visual.y.value!=reference.y.value || !visual.y.active {#panic("visible nonoffending axis lost animation")}
 motion.snap(&visual.x,0.0)
 motion.snap(&visual.y,0.0)
 draw_edit_scroll(&app,&visual,false,150.0,400.0)
 if visual.x.value!=reference.x.value {#panic("inactive pane scroll was forced")}
 motion.snap(&visual.x,0.0)
 motion.snap(&visual.y,0.0)
 app.view.insert=false
 draw_edit_scroll(&app,&visual,true,150.0,400.0)
 if visual.x.value!=reference.x.value {#panic("normal navigation lost scroll animation")}
 app.view.insert=true
 app.view.scroll_x=0.0
 motion.snap(&visual.x,0.0)
 motion.snap(&visual.y,0.0)
 draw_edit_scroll(&app,&visual,true,50.0,650.0)
 if visual.y.value!=200.0 || visual.x.value!=0.0 {#panic("vertical edit visibility guard")}
}
'''
start=explorer.index('  animated_scroll(app, visual, app.explorer.scroll_x')
end=explorer.index('  scroll_x := visual.x.value',start)
CASES['editing_explorer_viewport']='''fn main() {
 app_value:=App{config:Config{}}
 app:=&app_value
 app.view.animation.line=20.0
 app.explorer.insert=true
 app.explorer.scroll_x=100.0
 app.explorer.scroll_y=200.0
 storage:=AnimatedView{}
 visual:=&storage
 motion.snap(&visual.x,0.0)
 motion.snap(&visual.y,0.0)
 typography:=Typography{}
 x:f32=150.0
 y:f32=400.0
 body_height:f32=500.0
 available:f32=100.0
 reset:=false
'''+explorer[start:end]+'''
 if visual.x.value!=100.0 || !visual.y.active {#panic("explorer edit clipped by animated viewport")}
}
'''
CASES['scroll_continuation']='''fn main() {
 app:=App{}
 app.view.animation.line=20.0
 visual:=AnimatedView{}
 motion.snap(&visual.x,0.0)
 motion.snap(&visual.y,0.0)
 animated_scroll(&app,&visual,160.0,200.0,500.0,false)
 first_x:=visual.x.value
 first_y:=visual.y.value
 if !visual.x.active || !visual.y.active {#panic("page scroll must start a transition")}
 app.view.animation.now=8.0
 animated_scroll(&app,&visual,160.0,200.0,500.0,false)
 if visual.x.value<=first_x || visual.x.value>=160.0 || !visual.x.active {#panic("unchanged horizontal target truncates scroll on second frame")}
 if visual.y.value<=first_y || visual.y.value>=200.0 || !visual.y.active {#panic("unchanged vertical target truncates scroll on second frame")}
 app.view.animation.now=16.0
 animated_scroll(&app,&visual,170.0,220.0,500.0,false)
 if visual.x.value!=170.0 || visual.y.value!=220.0 || visual.x.active || visual.y.active {#panic("small navigation steps must still snap immediately")}
 // A distant jump starts near its destination, then preserves that short glide.
 app.view.animation.now=24.0
 animated_scroll(&app,&visual,170.0,2000.0,500.0,false)
 first_y=visual.y.value
 if first_y<1925.0 || first_y>=2000.0 {#panic("long jump must land close to destination")}
 app.view.animation.now=32.0
 animated_scroll(&app,&visual,170.0,2000.0,500.0,false)
 if visual.y.value<=first_y || visual.y.value>=2000.0 || !visual.y.active {#panic("long jump continuation must not snap on second frame")}
 app.config.smooth_scroll=false
 animated_scroll(&app,&visual,170.0,2200.0,500.0,false)
 if visual.y.value!=2200.0 || visual.y.active {#panic("disabled smooth scroll must snap immediately")}
}
'''
CASES['cursor_continuation']='''fn main() {
 x:=motion.Tween{}
 y:=motion.Tween{}
 motion.snap(&x,0.0)
 motion.snap(&y,0.0)
 if cursor_step_snaps(&x,&y,200.0,100.0,8.0,20.0) {#panic("large cursor jumps must allow a trail")}
 // draw_primary records the logical destination after evaluating jump policy.
 motion.snap(&x,200.0)
 motion.snap(&y,100.0)
 if cursor_step_snaps(&x,&y,200.0,100.0,8.0,20.0) {#panic("unchanged cursor target cancels its trail on second frame")}
 if !cursor_step_snaps(&x,&y,208.0,100.0,8.0,20.0) {#panic("typing steps must remain immediate")}
 if !cursor_step_snaps(&x,&y,0.0,120.0,8.0,20.0) {#panic("newline steps must remain immediate")}
}
'''
CASES['existing_contracts']=(ROOT/'tests/motion/main.dyn').read_text().replace('use "../../src/motion" motion','')
CASES['settings']='''fn main() {
 fast:=motion.Tween{}
 slow:=motion.Tween{}
 _=motion.follow(&fast,0.0,0.0,50.0,false)
 _=motion.follow(&slow,0.0,0.0,500.0,false)
 _=motion.follow(&fast,100.0,0.0,50.0,false)
 _=motion.follow(&slow,100.0,0.0,500.0,false)
 if fast.value<=slow.value || slow.value<=0.0 {#panic("custom motion durations were ignored")}
 app:=App{}
 app.view.reduced_motion=true
 if animated_follow(&app,&slow,-80.0,500.0,false)!= -80.0 || slow.active || app.view.animation.active {
  #panic("reduced motion must interrupt immediately and idle")
 }
}
'''
failures=[]
with tempfile.TemporaryDirectory(prefix='dna-motion-policy-') as directory:
    work=Path(directory)
    for name,body in CASES.items():
        stage=work/name;stage.mkdir()
        shutil.copytree(ROOT/'src/motion',stage/'motion')
        (stage/'sdl').mkdir();(stage/'sdl/sdl.dyn').write_text(SDL)
        (stage/'main.dyn').write_text(BASE+helpers+body.replace('app:=App{}','app:=App{config:Config{}}'))
        for mode in ('debug','release'):
            output=work/(name+'-'+mode)
            subprocess.run(['python3',str(ROOT/'scripts/compile.py'),DYN,'build',str(stage),'--'+mode,'--output',str(output)],check=True,timeout=60,stdout=subprocess.DEVNULL)
            result=subprocess.run([str(output)],capture_output=True,text=True,timeout=5)
            if result.returncode:
                failures.append(name+' '+mode+': '+result.stderr.splitlines()[0])
        if not any(item.startswith(name+' ') for item in failures):print('PASS deterministic motion policy: '+name,flush=True)
if failures:raise AssertionError('\n'.join(failures))
