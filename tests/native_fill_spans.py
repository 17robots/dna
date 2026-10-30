#!/usr/bin/env python3
"""Compare production native clear/fill spans with the frozen pixel reference."""
import ctypes as c
import os
from pathlib import Path
import random
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'src/platform/gui.dyn';REFERENCE=ROOT/'tests/fixtures/native_fill_reference.dyn'
from native_software_source import function

HEADER='''use "std/ui"
use "std/ui/software"
struct PixelRect {x,y,width,height:i32}
struct Rect {x,y,width,height:f32}
struct NativeTexture {pixels:[]u8,width,height:i32}
struct Gui {surface:software.Surface,target:*NativeTexture,viewport,clip:PixelRect,clipped:bool,draw_alpha:u8=255,sx,sy:f32,color:ui.Color}
native_gui:Gui
pub fn probe_setup(pixels:*u8,vx,vy,vw,vh,cx,cy,cw,ch:i32,sx,sy:f32,r,g,b,a:u8) {
 native_gui=Gui{surface:software.Surface{pixels:pixels[..64*48*4],width:64,height:48,stride:64*4},viewport:PixelRect{x:vx,y:vy,width:vw,height:vh},clip:PixelRect{x:cx,y:cy,width:cw,height:ch},clipped:true,sx:sx,sy:sy,color:ui.Color{r:r,g:g,b:b,a:a}}
}
pub fn probe_draw(reference,clear:i32,rect:*const Rect) bool {
 if reference!=0 {if clear!=0 {return reference_clear(nil)};return reference_fill(nil,rect)}
 if clear!=0 {return sdl_clear(nil)}
 return sdl_fill(nil,rect)
}
'''.replace(';','\n')
rng=random.Random(7213)
class Rect(c.Structure):_fields_=[(x,c.c_float) for x in ('x','y','width','height')]
with tempfile.TemporaryDirectory(prefix='dna-fill-spans-') as directory:
 stage=Path(directory);names=['native_surface','native_clip','sdl_clear','sdl_fill','native_draw_alpha']
 if 'fn native_fill_span(' in SOURCE.read_text():names.append('native_fill_span')
 code='\n'.join(function(SOURCE,n) for n in names)
 if 'extern fn native_span_copy' in SOURCE.read_text():
  code+='\n'+'\n'.join(x for x in SOURCE.read_text().splitlines() if x.startswith('extern fn native_span_'))
 (stage/'main.dyn').write_text(HEADER+code+'\n'+REFERENCE.read_text())
 for mode in ('debug','release'):
  output=stage/(mode+'.so');subprocess.run(['python3',str(ROOT/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(stage),'--shared','--'+mode,'--output',str(output)],check=True)
  lib=c.CDLL(str(output));lib.probe_setup.argtypes=[c.POINTER(c.c_ubyte)]+[c.c_int32]*8+[c.c_float]*2+[c.c_uint8]*4;lib.probe_draw.argtypes=[c.c_int32,c.c_int32,c.POINTER(Rect)];lib.probe_draw.restype=c.c_bool
  for case in range(240):
   data=bytes((i*37+19)%256 for i in range(64*48*4))
   viewport=tuple(rng.randint(-10,10) for _ in range(2))+(rng.randint(1,75),rng.randint(1,60))
   clip=tuple(rng.randint(-15,45) for _ in range(2))+(rng.randint(0,65),rng.randint(0,55))
   scale=(rng.choice((.5,1.,1.25,2.)),rng.choice((.5,1.,1.5,2.)))
   color=(0,0,0,0) if case%5==0 else tuple(rng.randrange(256) for _ in range(3))+(255 if case%2 else rng.randrange(256),)
   rect=Rect(rng.uniform(-50,70),rng.uniform(-50,60),rng.uniform(-5,70),rng.uniform(-5,60))
   def draw(ref):
    pixels=(c.c_ubyte*len(data)).from_buffer_copy(data)
    lib.probe_setup(pixels,*viewport,*clip,*scale,*color)
    ok=lib.probe_draw(ref,int(case%7==0),c.byref(rect));return ok,bytes(pixels)
   assert draw(1)==draw(0),(mode,case,'fill pixels changed')
  print(f'PASS native clear/fill {mode}:240 exact pixel cases',flush=True)
