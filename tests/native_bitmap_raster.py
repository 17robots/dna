#!/usr/bin/env python3
"""Pixel equivalence and bounded clipping work for native glyph rasterization."""
import ctypes as c
import os
from pathlib import Path
import random
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'src/platform/gui.dyn'
REFERENCE=ROOT/'tests/fixtures/native_bitmap_reference.dyn'
def function(path,name):
    text=path.read_text();start=text.index(('pub ' if 'pub fn '+name+'(' in text else '')+'fn '+name+'(')
    end=text.index('{',start)+1;depth=1
    while depth:
        if text[end]=='{':depth+=1
        if text[end]=='}':depth-=1
        end+=1
    return text[start:end]
HEADER='''use "std/ui"
use "std/ui/software"
struct PixelRect {x,y,width,height:i32}
struct NativeTexture {pixels:[]u8,width,height:i32}
struct Gui {surface:software.Surface,target:*NativeTexture,viewport,clip:PixelRect,clipped:bool,draw_alpha:u8=255,sx,sy:f32}
native_gui:Gui
clips:u64
pub fn probe_setup(pixels:*u8,width,height:i32,vx,vy,vw,vh,cx,cy,cw,ch:i32,sx,sy:f32) {
 native_gui=Gui{surface:software.Surface{pixels:pixels[..#cast(usize,width)*#cast(usize,height)*4],width:width,height:height,stride:#cast(usize,width)*4},viewport:PixelRect{x:vx,y:vy,width:vw,height:vh},clip:PixelRect{x:cx,y:cy,width:cw,height:ch},clipped:true,sx:sx,sy:sy}
 clips=0
}
pub fn probe_bitmap(reference:i32,pixels:*const u8,width,height:i32,x,y:f32,r,g,b,a:u8,checks:*u64) bool {
 result:=false
 if reference!=0 {result=reference_bitmap(nil,pixels,width,height,x,y,r,g,b,a)}
 else {result=native_text_bitmap(nil,pixels,width,height,x,y,r,g,b,a)}
 checks.*=clips
 return result
}
'''
rng=random.Random(8183)
cases=[(48,32,-47.,-31.,(0,0,64,48),(0,0,1,1),(1.,1.),(33,117,230,170),True)]
for _ in range(320):
 cases.append((rng.randint(1,60),rng.randint(1,50),rng.uniform(-60,60),rng.uniform(-50,50),(rng.randint(-10,10),rng.randint(-10,10),rng.randint(1,70),rng.randint(1,60)),(rng.randint(-10,40),rng.randint(-10,30),rng.randint(0,60),rng.randint(0,50)),(rng.choice((.5,1.,1.25,2.)),rng.choice((.5,1.,1.5,2.))),tuple(rng.randrange(256) for _ in range(4)),bool(rng.randrange(2))))
with tempfile.TemporaryDirectory(prefix='dna-native-bitmap-') as temporary:
 stage=Path(temporary)
 names=['native_surface','native_clip','native_blend','native_draw_alpha']
 if 'fn native_blend_at(' in SOURCE.read_text():names.append('native_blend_at')
 shared='\n'.join(function(SOURCE,n) for n in names)
 shared=shared.replace('fn native_clip(surface: software.Surface) ui.Rect {','fn native_clip(surface: software.Surface) ui.Rect {\n clips+=1')
 (stage/'main.dyn').write_text(HEADER+'\n'+shared+'\n'+REFERENCE.read_text()+'\n'+function(SOURCE,'native_text_bitmap'))
 for mode in ('debug','release'):
  output=stage/(mode+'.so')
  subprocess.run(['python3',str(ROOT/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(stage),'--shared','--'+mode,'--output',str(output)],check=True)
  lib=c.CDLL(str(output));lib.probe_setup.argtypes=[c.POINTER(c.c_ubyte)]+[c.c_int32]*10+[c.c_float]*2
  lib.probe_bitmap.argtypes=[c.c_int32,c.POINTER(c.c_ubyte),c.c_int32,c.c_int32,c.c_float,c.c_float]+[c.c_uint8]*4+[c.POINTER(c.c_uint64)];lib.probe_bitmap.restype=c.c_bool
  def draw(reference,case):
   w,h,x,y,viewport,clip,scale,color,opaque=case
   data=(c.c_ubyte*(64*48*4))(*[(i*37+19)%256 for i in range(64*48*4)])
   if opaque:
    for i in range(3,len(data),4):data[i]=255
   glyph=(c.c_ubyte*(w*h))(*[(i*43)%256 for i in range(w*h)])
   lib.probe_setup(data,64,48,*viewport,*clip,*scale);checks=c.c_uint64()
   ok=lib.probe_bitmap(reference,glyph,w,h,x,y,*color,c.byref(checks))
   return ok,bytes(data),checks.value
  for number,case in enumerate(cases):
   before=draw(1,case);after=draw(0,case)
   assert before[:2]==after[:2],(mode,number,'pixels differ')
  before=draw(1,cases[0]);after=draw(0,cases[0])
  assert before[2]>100 and after[2]<=1,(mode,'glyph clipping repeated per pixel',before[2],after[2])
  print(f'PASS native bitmap {mode}: {len(cases)} exact pixel cases; clipping checks {before[2]} -> {after[2]}',flush=True)
