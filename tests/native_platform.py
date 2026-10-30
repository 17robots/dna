#!/usr/bin/env python3
"""Native GUI production pixel, event, texture and renderer lifetime oracle."""
import os
from pathlib import Path
import shutil
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
BACKEND=os.environ.get('DNA_NATIVE_BACKEND','x11')
if BACKEND not in ('x11','wayland'):
    raise SystemExit('DNA_NATIVE_BACKEND must be x11 or wayland')
DYN=str(Path(os.environ.get('DYN',ROOT.parent/'dyn/compiler/build/dyn-release')).resolve())
SOURCE=r'''extern fn probe_keycode "XKeysymToKeycode"(display:rawptr,symbol:usize) u8
extern fn probe_character "XkbKeycodeToKeysym"(display:rawptr,code:u8,group,level:i32) usize

fn native_check(ok:bool,reason:[]const u8) { if !ok { #panic(reason) } }
fn native_pixel(x,y:i32,r,g,b,a:u8) bool {
 surface:=native_surface()
 at:=#cast(usize,y)*surface.stride+#cast(usize,x)*4
 return surface.pixels[at]==r && surface.pixels[at+1]==g && surface.pixels[at+2]==b && surface.pixels[at+3]==a
}
fn main() {
 title: [12]u8=[68,78,65,32,111,114,97,99,108,101,0,0]
 window:=sdl_create_window(&title[0],128,96,0)
 native_check(window!=nil,"native window")
 defer sdl_destroy_window(window)
 renderer:=sdl_create_renderer(window,nil)
 native_check(renderer!=nil,"native renderer")
 native_check(sdl_color(renderer,0,0,0,255) && sdl_clear(renderer),"clear")
 viewport:=PixelRect{x:4,y:5,width:20,height:20}
 native_check(sdl_viewport(renderer,&viewport),"viewport")
 clip:=PixelRect{x:2,y:3,width:4,height:5}
 native_check(sdl_clip(renderer,&clip),"clip")
 rectangle:=Rect{x:0.0,y:0.0,width:20.0,height:20.0}
 native_check(sdl_color(renderer,255,0,0,128) && sdl_fill(renderer,&rectangle),"fill")
 native_check(native_pixel(6,8,128,0,0,255) && native_pixel(5,8,0,0,0,255) && native_pixel(10,8,0,0,0,255),"viewport-relative clip and alpha")
 native_check(sdl_viewport(renderer,nil),"reset viewport")
 texture:=sdl_create_texture(renderer,0x16462004,2,4,4)
 native_check(texture!=nil && sdl_target(renderer,texture),"texture target")
 native_check(sdl_color(renderer,0,255,0,128) && sdl_clear(renderer),"transparent texture clear")
 native_check(sdl_target(renderer,nil),"window target")
 destination:=Rect{x:20.0,y:10.0,width:8.0,height:8.0}
 native_check(sdl_render_texture(renderer,texture,nil,&destination),"texture scale")
 native_check(native_pixel(20,10,0,128,0,255) && native_pixel(27,17,0,128,0,255) && native_pixel(28,17,0,0,0,255),"texture bounds and straight alpha")
 native_check(sdl_texture_alpha(texture,128),"texture alpha modulation")
 destination.x=40.0
 native_check(sdl_render_texture(renderer,texture,nil,&destination) && native_pixel(40,10,0,64,0,255),"modulated texture alpha")
 sdl_destroy_texture(texture)
 native_check(native_present.draw(&native_gui.presenter,native_gui.surface).ok,"GPU upload")
 pixel: [4]u8=[]
 api:=&native_gui.presenter.api
 api.pixel_store_i(3333,1)
 api.read_pixels(20,native_gui.surface.height-1-10,1,1,6408,5121,#cast(rawptr,&pixel[0]))
 native_check(pixel[0]==0 && pixel[1]==128 && pixel[2]==0,"GPU orientation and pixel readback")
 // Reuse existing texture storage but replace its content on the next frame.
 changed:=Rect{x:20.0,y:10.0,width:1.0,height:1.0}
 native_check(sdl_color(renderer,17,83,201,255) && sdl_fill(renderer,&changed),"changed second frame")
 native_check(native_present.draw(&native_gui.presenter,native_gui.surface).ok,"same-size GPU update")
 api.read_pixels(20,native_gui.surface.height-1-10,1,1,6408,5121,#cast(rawptr,&pixel[0]))
 native_check(pixel[0]==17 && pixel[1]==83 && pixel[2]==201,"same-size upload replaces GPU pixel")
 // Exercise resized texture storage without relying on compositor window sizing.
 resized_pixels:[3072]u8=[]
 for i in 0..768 {
   resized_pixels[i*4]=51
   resized_pixels[i*4+1]=129
   resized_pixels[i*4+2]=207
   resized_pixels[i*4+3]=255
 }
 resized_pixels[3068]=201
 resized_pixels[3069]=31
 resized_pixels[3070]=19
 resized:=software.Surface{pixels:resized_pixels[..],width:32,height:24,stride:128}
 native_check(native_present.draw(&native_gui.presenter,resized).ok,"resized GPU upload")
 api.read_pixels(0,23,1,1,6408,5121,#cast(rawptr,&pixel[0]))
 native_check(pixel[0]==51 && pixel[1]==129 && pixel[2]==207,"resized top-left GPU pixel")
 api.read_pixels(31,0,1,1,6408,5121,#cast(rawptr,&pixel[0]))
 native_check(pixel[0]==201 && pixel[1]==31 && pixel[2]==19,"resized bottom-right GPU pixel")
 native_check(native_present.draw(&native_gui.presenter,native_gui.surface).ok,"restore full-size GPU upload")
 api.read_pixels(20,native_gui.surface.height-1-10,1,1,6408,5121,#cast(rawptr,&pixel[0]))
 native_check(pixel[0]==17 && pixel[1]==83 && pixel[2]==201,"restored full-size GPU pixel")
 // One A8 source texel must cover the scaled 2 by 3 destination rectangle.
 native_check(sdl_scale(renderer,2.0,3.0),"text scale")
 mask:[1]u8=[255]
 native_check(native_text_bitmap(renderer,&mask[0],1,1,30.0,10.0,0,0,255,255),"text bitmap")
 native_check(native_pixel(60,30,0,0,255,255) && native_pixel(61,32,0,0,255,255) && native_pixel(62,32,0,0,0,255),"text bitmap scale extents")
 native_check(sdl_scale(renderer,1.0,1.0),"unit scale")
 vertices: [4]Vertex=[Vertex{x:70.0,y:20.0,red:1.0,alpha:0.5},Vertex{x:74.0,y:20.0,red:1.0,alpha:0.5},Vertex{x:74.0,y:24.0,red:1.0,alpha:0.5},Vertex{x:70.0,y:24.0,red:1.0,alpha:0.5}]
 indices:[6]i32=[0,1,2,0,2,3]
 native_check(sdl_geometry(renderer,nil,&vertices[0],4,&indices[0],6),"geometry")
 native_check(native_pixel(70,20,127,0,0,255) && native_pixel(71,20,127,0,0,255),"shared triangle edge blends once")
 native_check(native_key(events.F1)==1073741882 && native_key(events.F1+11)==1073741893,"F1 through F12")
 native_check(native_key(events.F1+12)==1073741928 && native_key(events.F24)==1073741939,"F13 through F24")
 event:=Event{}
 source:=events.Event{kind:events.Kind.KeyDown,key:events.Left,scancode:77,modifiers:events.Control|events.Shift,repeated:1}
 native_check(native_event(&source,&event),"key mapping")
 key:=#cast(*KeyEvent,&event)
 native_check(key.key==1073741904 && key.scancode==77 && key.modifiers==195 && key.down && key.repeated,"key fields and modifiers")
 digit_code:=probe_keycode(native_gui.window.display,52)
 native_check(digit_code!=0,"configured digit keycode")
 source=events.Event{kind:events.Kind.KeyDown,key:52,scancode:#cast(u32,digit_code),modifiers:events.Shift}
 native_check(native_event(&source,&event),"shifted key mapping")
 expected_symbol:=probe_character(native_gui.window.display,digit_code,0,1)
 native_check(expected_symbol!=0 && sdl_key_from_scancode(#cast(u32,digit_code),3,false)==#cast(u32,expected_symbol),"shifted character follows configured X keymap")
 source=events.Event{kind:events.Kind.FocusLost}
 native_check(native_event(&source,&event) && sdl_modifiers()==0,"focus loss clears modifier state")
 source=events.Event{kind:events.Kind.KeyDown,key:97,modifiers:events.CapsLock|events.NumLock|events.Super}
 native_check(native_event(&source,&event) && sdl_modifiers()==15360,"lock and super modifiers")
 source=events.Event{kind:events.Kind.PointerDown,button:1,x:10,y:10,modifiers:events.Shift}
 native_check(native_event(&source,&event) && sdl_modifiers()==3,"pointer event updates modifiers for shift selection")
 native_gui.click_valid=false
 native_gui.mouse_buttons=0
 source=events.Event{kind:events.Kind.PointerDown,button:1,x:10,y:10}
 native_check(native_event(&source,&event) && #cast(*MouseButton,&event).clicks==1,"first click")
 source.kind=events.Kind.PointerMove
 native_check(native_event(&source,&event) && #cast(*MouseMotion,&event).state==1,"drag motion retains left button")
 source.kind=events.Kind.PointerUp
 native_check(native_event(&source,&event) && native_gui.mouse_buttons==0,"release clears left button")
 source.kind=events.Kind.PointerDown
 native_gui.click_at=time.monotonic_now().value
 native_check(native_event(&source,&event) && #cast(*MouseButton,&event).clicks==2,"double click")
 source.kind=events.Kind.PointerUp
 native_check(native_event(&source,&event),"second release")
 source.kind=events.Kind.PointerDown
 native_gui.click_at=time.monotonic_now().value
 native_check(native_event(&source,&event) && #cast(*MouseButton,&event).clicks==3,"triple click")
 source.kind=events.Kind.PointerUp
 native_check(native_event(&source,&event),"third release")
 source.kind=events.Kind.PointerDown
 native_gui.click_at=time.monotonic_now().value
 native_check(native_event(&source,&event) && #cast(*MouseButton,&event).clicks==1,"click sequence restarts after triple")
 source.x=30
 native_gui.click_at=time.monotonic_now().value
 native_check(native_event(&source,&event) && #cast(*MouseButton,&event).clicks==1,"distant click starts new sequence")
 native_gui.click_at=time.monotonic_now().value
 native_gui.click_at.seconds-=1
 native_check(native_event(&source,&event) && #cast(*MouseButton,&event).clicks==1,"click timeout starts new sequence")
 source.button=3
 native_check(native_event(&source,&event) && native_gui.mouse_buttons==5,"multiple held button mask")
 source.kind=events.Kind.PointerMove
 native_check(native_event(&source,&event) && #cast(*MouseMotion,&event).state==5,"motion retains both buttons")
 source.kind=events.Kind.PointerUp
 source.button=1
 native_check(native_event(&source,&event) && native_gui.mouse_buttons==4,"release preserves other held button")
 source.kind=events.Kind.FocusLost
 native_check(native_event(&source,&event) && native_gui.mouse_buttons==0 && !native_gui.click_valid,"focus loss clears drag and click sequence")



 source=events.Event{kind:events.Kind.Text,text_length:2}
 source.text[0]=0xc3
 source.text[1]=0xa9
 native_check(native_event(&source,&event),"text mapping")
 received:=#cast(*TextEvent,&event)
 source.text[0]=120
 native_check(received.kind==771 && received.text[..3][0]==0xc3 && received.text[..3][1]==0xa9 && received.text[..3][2]==0,"owned event text")
 native_check(native_cursor(8)==window_api.Cursor.ResizeX && native_cursor(9)==window_api.Cursor.ResizeY,"split resize cursor shapes")
 step:=48.0*window_api.scale(&native_gui.window)
 source=events.Event{kind:events.Kind.Wheel,scroll_x:step,scroll_y:0.0-step}
 native_check(native_event(&source,&event),"wheel translation")
 wheel:=#cast(*MouseWheel,&event)
 native_check(wheel.x==1.0 && wheel.y==1.0,"pixel scroll normalizes to logical wheel units and direction")
 first_bytes: [6]u8=[102,105,114,115,116,0]
 native_check(sdl_clipboard_set(&first_bytes[0]),"first clipboard offer")
 first_clip:=sdl_clipboard_get()
 native_check(first_clip!=nil,"first clipboard allocation")
 second_bytes: [7]u8=[115,101,99,111,110,100,0]
 native_check(sdl_clipboard_set(&second_bytes[0]),"second clipboard offer")
 second_clip:=sdl_clipboard_get()
 native_check(second_clip!=nil && first_clip!=second_clip && first_clip[..5][0]==102 && first_clip[..5][4]==116 && second_clip[..6][0]==115,"clipboard results remain independently owned")
 sdl_free(#cast(rawptr,first_clip))
 sdl_free(#cast(rawptr,second_clip))
 native_check(native_gui.clipboards==nil,"clipboard free balances owners")
 large_owner:=mem.arena_create(0)
 large:=mem.push_bytes_uninit(large_owner,1200002)
 for i in 0..1200001 {large[i]=97}
 large[1200001]=0
 native_check(sdl_clipboard_set(&large[0]),"large clipboard offer without truncation")
 large_copy:=sdl_clipboard_get()
 native_check(large_copy!=nil && c.string_length(large_copy,1200002)==1200001 && large_copy[..1200001][1200000]==97,"large complete clipboard allocation")
 sdl_free(#cast(rawptr,large_copy))
 mem.arena_release(large_owner)
 source=events.Event{kind:events.Kind.Overflow,dropped:2}
 native_check(native_event(&source,&event) && event.words[0]==32770 && sdl_modifiers()==0 && native_gui.mouse_buttons==0,"overflow reports dropped input without stale state")
 sdl_destroy_renderer(renderer)
 native_check(native_gui.surface.width==0 && #len(native_gui.surface.pixels)==0,"destroy invalidates framebuffer")
 renderer=sdl_create_renderer(window,nil)
 native_check(renderer!=nil && sdl_color(renderer,1,2,3,255) && sdl_clear(renderer),"same-size renderer recreation")
 native_check(native_pixel(0,0,1,2,3,255),"recreated framebuffer writable")
 sdl_destroy_renderer(renderer)
}
'''
if BACKEND=='wayland':
    SOURCE=SOURCE[SOURCE.index('fn native_check'):]
    start=SOURCE.index(' digit_code:=')
    end=SOURCE.index(' source=events.Event{kind:events.Kind.FocusLost}',start)
    SOURCE=SOURCE[:start]+r''' // Capture a shifted digit before a later queued modifier release. The
 // producer's current state has changed by the time this event is consumed.
 queued:[2]events.Event=[events.Event{kind:events.Kind.KeyDown,key:52,scancode:5,modifiers:events.Shift,height:36},events.Event{kind:events.Kind.KeyUp,key:0,scancode:42}]
 native_gui.modifiers=0
 source=queued[0]
 native_check(native_event(&source,&event),"queued shifted key mapping")
 native_check(sdl_key_from_scancode(5,0,false)==36,"queued shifted character survives later producer modifier release")
 source=queued[1]
 native_check(native_event(&source,&event) && sdl_modifiers()==0,"queued modifier release")
 source=events.Event{kind:events.Kind.KeyDown,key:69,scancode:18,height:8364}
 native_check(native_event(&source,&event) && sdl_key_from_scancode(18,0,false)==8364,"queued Unicode layout character")
'''+SOURCE[end:]
    start=SOURCE.index(' first_bytes:')
    end=SOURCE.index(' source=events.Event{kind:events.Kind.Overflow',start)
    SOURCE=SOURCE[:start]+SOURCE[end:]
    print('Wayland clipboard offer/get runs in the private tests/wayland_runner.py compositor with real input',flush=True)
with tempfile.TemporaryDirectory(prefix='dna-native-platform-') as directory:
    work=Path(directory)
    stage=work/'platform'
    stage.mkdir()
    types=(ROOT/'src/platform/platform.dyn').read_text()
    declarations=[]
    for match in re.finditer(r'pub struct [A-Za-z_]+\s*\{',types):
        depth=1;end=match.end()
        while depth:
            if types[end]=='{':depth+=1
            if types[end]=='}':depth-=1
            end+=1
        declarations.append(types[match.start():end])
    (stage/'types.dyn').write_text('use "std/mem"\n#link("dna_native")\npub const WorkerWakeEvent:u32=32768\npub const InputOverflowEvent:u32=32770\n'+'\n'.join(declarations))
    shutil.copyfile(ROOT/'src/platform/gui.dyn',stage/'sdl.dyn')
    shutil.copytree(ROOT/'src/platform/native_present',stage/'native_present')
    (stage/'backend').mkdir()
    shutil.copyfile(ROOT/f'modules/native/platform_{BACKEND}.dyn',stage/'backend/backend.dyn')
    for source in [stage/'sdl.dyn',*(stage/'native_present').rglob('*.dyn')]:
        text=source.read_text().replace('"vendor/window/wayland"','"vendor/window"')
        if BACKEND=='wayland': text=text.replace('"vendor/window"','"vendor/window/wayland"')
        source.write_text(text)
    (stage/'main.dyn').write_text(SOURCE)
    library=ROOT/('build/native-wayland' if BACKEND=='wayland' else 'build/native-gui')
    if not (library/'libdna_native.so').exists():
        raise SystemExit(f'Run scripts/build_native.py --backend {BACKEND} before native platform tests')
    environment=dict(os.environ,DNA_RENDERER='software',DYN_LIBRARY_PATH=str(library),LD_LIBRARY_PATH=str(library))
    if BACKEND=='x11': environment.pop('WAYLAND_DISPLAY',None)
    for flags in (['--debug'],['--release']):
        output=work/'test'
        subprocess.run([DYN,'build',str(stage),*flags,'--quiet','--link','-rpath='+str(library),'--output',str(output)],env=environment,check=True,timeout=180)
        subprocess.run([str(output)],env=environment,check=True,timeout=60)
print(f'PASS native platform: clipped alpha pixels, texture scaling/modulation, same-size/resized GPU readback, scaled glyph masks, triangle edges, event translation, drag/multiclick and renderer recreation (debug/release, {BACKEND})')
