#!/usr/bin/env python3
"""Native pane opacity modulates final window draws once, never cached pixels."""
import ctypes as c
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'src/platform/gui.dyn'
from native_software_source import function as software_function
def function(name):
    return software_function(SOURCE,name)

HEADER='''use "std/ui"
use "std/ui/software"
struct PixelRect {x,y,width,height:i32}
struct Rect {x,y,width,height:f32}
struct Vertex {x,y,red,green,blue,alpha,u,v:f32}
struct NativeTexture {pixels:[]u8,width,height:i32,alpha:u8=255}
struct Gui {surface:software.Surface,target:*NativeTexture,viewport,clip:PixelRect,clipped:bool,draw_alpha:u8=255,sx,sy:f32,color:ui.Color}
native_gui:Gui
cached:NativeTexture
pub fn probe_setup(pixels:*u8,target:i32,opacity:u8) {
 native_gui=Gui{surface:software.Surface{pixels:pixels[..256],width:8,height:8,stride:32},viewport:PixelRect{width:8,height:8},sx:1.0,sy:1.0}
 cached=NativeTexture{pixels:pixels[..256],width:8,height:8}
 if target!=0 {native_gui.target=&cached}
 _=sdl_draw_opacity(nil,opacity)
}
pub fn probe_draw(kind:i32,alpha:u8,texture:*u8) bool {
 color:=ui.Color{r:220,g:125,b:63,a:alpha}
 _=sdl_color(nil,color.r,color.g,color.b,color.a)
 rect:=Rect{width:8.0,height:8.0}
 if kind==0 {return sdl_fill(nil,&rect)}
 if kind==1 {
  mask:[64]u8=[]
  for i in 0..64 {mask[i]=#cast(u8,(i*41)%256)}
  return native_text_bitmap(nil,&mask[0],8,8,0.0,0.0,color.r,color.g,color.b,alpha)
 }
 if kind==2 {
  t:=NativeTexture{pixels:texture[..256],width:8,height:8,alpha:alpha}
  return sdl_render_texture(nil,&t,nil,nil)
 }
 if kind==3 {
  vertices:[3]Vertex=[Vertex{x:0.0,y:0.0,red:220.0/255.0,green:125.0/255.0,blue:63.0/255.0,alpha:#cast(f32,alpha)/255.0},Vertex{x:8.0,y:0.0,red:220.0/255.0,green:125.0/255.0,blue:63.0/255.0,alpha:#cast(f32,alpha)/255.0},Vertex{x:0.0,y:8.0,red:220.0/255.0,green:125.0/255.0,blue:63.0/255.0,alpha:#cast(f32,alpha)/255.0}]
  indices:[3]i32=[0,1,2]
  return sdl_geometry(nil,nil,&vertices[0],3,&indices[0],3)
 }
 if kind==4 {return sdl_clear(nil)}
 return false
}
pub fn probe_reset() {_=sdl_draw_opacity(nil,255)}
pub fn probe_preserve_color() bool {
 _=sdl_color(nil,220,125,63,137)
 _=sdl_draw_opacity(nil,96)
 _=sdl_draw_opacity(nil,255)
 rect:=Rect{width:8.0,height:8.0}
 return sdl_fill(nil,&rect)
}
'''
NAMES=['native_surface','native_clip','sdl_color','sdl_draw_opacity','native_draw_alpha','native_fill_span','sdl_fill','sdl_clear','native_blend','native_blend_at','sdl_render_texture','native_text_bitmap','native_edge','native_top_left','sdl_geometry']
code=HEADER+'\n'.join(function(name) for name in NAMES)+'\n'+'\n'.join(line for line in (ROOT/'src/platform/memory_linux.dyn').read_text().splitlines() if line.startswith('extern fn native_span_'))
with tempfile.TemporaryDirectory(prefix='dna-draw-opacity-') as temporary:
    work=Path(temporary);(work/'main.dyn').write_text(code)
    texture=bytes((220,125,63,a) [i%4] for i in range(256) for a in [255 if (i//4)%2 else 96])
    tex=(c.c_ubyte*256).from_buffer_copy(texture)
    cases=0
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        output=work/(mode+'.so')
        subprocess.run(['python3',str(ROOT/'scripts/compile.py'),os.environ.get('DYN',str(ROOT.parent/'dyn/compiler/build/dyn-release')),'build',str(work),'--shared','--'+mode,'--output',str(output)],check=True,stdout=subprocess.DEVNULL)
        lib=c.CDLL(str(output));lib.probe_setup.argtypes=[c.POINTER(c.c_ubyte),c.c_int32,c.c_uint8];lib.probe_draw.argtypes=[c.c_int32,c.c_uint8,c.POINTER(c.c_ubyte)];lib.probe_draw.restype=c.c_bool
        def draw(kind,opacity,alpha,target=0,reset=False):
            data=bytes([13,29,47,255 if not target else 121])*64
            pixels=(c.c_ubyte*256).from_buffer_copy(data)
            lib.probe_setup(pixels,target,opacity)
            if reset:lib.probe_reset()
            assert lib.probe_draw(kind,alpha,tex)
            return bytes(pixels)
        for kind in range(4):
            for opacity in (0,1,96,128,220,254,255):
                # Geometry blends vertex alpha as float; use opaque vertices so
                # the contract has an exact independently supplied byte alpha.
                for alpha in ((255,) if kind==3 else (0,1,96,128,254,255)):
                    effective=(alpha*opacity+127)//255
                    assert draw(kind,opacity,alpha)==draw(kind,255,effective),(mode,kind,opacity,alpha,'window opacity')
                    assert draw(kind,opacity,alpha,1)==draw(kind,255,alpha,1),(mode,kind,opacity,alpha,'cached target changed')
                    assert draw(kind,opacity,alpha,reset=True)==draw(kind,255,alpha),(mode,kind,'reset')
                    cases+=3
        assert draw(4,0,255)==draw(4,255,255),'clear must retain replacement semantics'
        pixels=(c.c_ubyte*256).from_buffer_copy(bytes([13,29,47,255])*64)
        lib.probe_setup(pixels,0,255)
        lib.probe_preserve_color.restype=c.c_bool
        assert lib.probe_preserve_color()
        assert bytes(pixels)==draw(0,255,137),'opacity must not change stored drawing color'
        # Opaque cached fill drawn while dimmed must contain full-color pixels;
        # final composition supplies the only opacity factor.
        cached_pixels=draw(0,128,255,1)
        tex=(c.c_ubyte*256).from_buffer_copy(cached_pixels)
        assert draw(2,128,255)==draw(0,255,128),(mode,'offscreen opacity applied twice')
        print(f'PASS native draw opacity ({mode}): fill/glyph/texture/triangle exact alpha, unchanged offscreen pixels, single composition, reset and clear',flush=True)
