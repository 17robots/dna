#!/usr/bin/env python3
"""Exact native texture pixels and bounded clip work against frozen raster."""
import ctypes as c
import os
from pathlib import Path
import random
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'src/platform/gui.dyn'
REFERENCE=ROOT/'tests/fixtures/native_texture_reference.dyn'
def function(path,name):
    text=path.read_text();start=text.index(('pub ' if 'pub fn '+name+'(' in text else '')+'fn '+name+'(')
    end=text.index('{',start)+1;depth=1
    while depth:
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    return text[start:end]
HEADER='''use "std/ui"
use "std/ui/software"
struct PixelRect {x,y,width,height:i32}
struct Rect {x,y,width,height:f32}
struct NativeTexture {pixels:[]u8,width,height:i32,alpha:u8=255}
struct Gui {surface:software.Surface,target:*NativeTexture,viewport,clip:PixelRect,clipped:bool,draw_alpha:u8=255,sx,sy:f32}
native_gui:Gui
clips:u64
span_copies:u64
blends:u64
pub fn probe_setup(pixels:*u8,width,height:i32,vx,vy,vw,vh,cx,cy,cw,ch:i32,clipped:i32,sx,sy:f32) {
 native_gui=Gui{surface:software.Surface{pixels:pixels[..#cast(usize,width)*#cast(usize,height)*4],width:width,height:height,stride:#cast(usize,width)*4},viewport:PixelRect{x:vx,y:vy,width:vw,height:vh},clip:PixelRect{x:cx,y:cy,width:cw,height:ch},clipped:clipped!=0,sx:sx,sy:sy}
 clips=0
 span_copies=0
 blends=0
}
pub fn probe_texture(reference:i32,pixels:*u8,width,height:i32,alpha:u8,alias:i32,source,destination:*const Rect,checks:*u64) bool {
 texture:=NativeTexture{pixels:pixels[..#cast(usize,width)*#cast(usize,height)*4],width:width,height:height,alpha:alpha}
 if alias!=0 {texture.pixels=native_gui.surface.pixels}
 result:=false
 if reference!=0 {result=reference_texture(nil,&texture,source,destination)}
 else {result=sdl_render_texture(nil,&texture,source,destination)}
 checks[..3][0]=clips
 checks[..3][1]=span_copies
 checks[..3][2]=blends
 return result
}
'''
class Rect(c.Structure):
    _fields_=[(name,c.c_float) for name in ('x','y','width','height')]
rng=random.Random(46013)
# texture size, source, destination, viewport, clip, scale, modulation, target alpha, source alpha
cases=[(64,48,None,None,(0,0,64,48),(0,0,1,1),(1.,1.),255,True,255)]
for modulation in (0,1,127,254,255):
 for alpha in (0,1,127,254,255):
  for source in (None,(0.,0.,16.,12.),(-.5,-.5,16.,12.),(-1.,-1.,16.,12.),(.5,.5,16.,12.)):
   cases.append((16,12,source,(0.,0.,16.,12.),(0,0,64,48),None,(1.,1.),modulation,False,alpha))
for _ in range(600):
 w,h=rng.randint(1,70),rng.randint(1,60)
 source=None if rng.randrange(4)==0 else (rng.uniform(-20,40),rng.uniform(-20,35),rng.uniform(.01,80),rng.uniform(.01,70))
 destination=None if rng.randrange(4)==0 else (rng.uniform(-60,60),rng.uniform(-50,50),rng.uniform(.01,90),rng.uniform(.01,80))
 viewport=(rng.randint(-10,10),rng.randint(-10,10),rng.randint(1,70),rng.randint(1,60))
 clip=None if rng.randrange(3)==0 else (rng.randint(-20,40),rng.randint(-20,30),rng.randint(0,60),rng.randint(0,50))
 cases.append((w,h,source,destination,viewport,clip,(rng.choice((.5,1.,1.25,2.)),rng.choice((.5,1.,1.5,2.))),rng.randrange(256),bool(rng.randrange(2)),None))
# Degenerate and fractional scaled extents preserve return values as well as pixels.
for source in ((0.,0.,0.,10.),(0.,0.,10.,-1.)):
 cases.append((8,8,source,None,(0,0,64,48),None,(1.,1.),255,True,255))
for destination in ((0.,0.,0.,10.),(0.,0.,10.,-1.),(0.,0.,.1,.1)):
 cases.append((8,8,None,destination,(0,0,64,48),None,(.5,.5),255,True,255))
alias_cases=[]
for source in (None,(0.,0.,64.,48.),(-1.,-1.,64.,48.),(.5,.5,64.,48.)):
 for destination in (None,(1.,0.,64.,48.),(-1.,-1.,64.,48.),(0.,1.,64.,48.),(0.,0.,32.,24.)):
  for opaque in (False,True):
   alias_cases.append((64,48,source,destination,(0,0,64,48),None,(1.,1.),255,opaque,None))
with tempfile.TemporaryDirectory(prefix='dna-native-texture-') as temporary:
 stage=Path(temporary)
 shared='\n'.join(function(SOURCE,n) for n in ('native_surface','native_clip','native_blend','native_blend_at','native_draw_alpha'))
 shared=shared.replace('fn native_clip(surface: software.Surface) ui.Rect {','fn native_clip(surface: software.Surface) ui.Rect {\n clips+=1')
 shared=shared.replace('fn native_blend_at(surface:*software.Surface, at:usize, r,g,b,a:u8) {','fn native_blend_at(surface:*software.Surface, at:usize, r,g,b,a:u8) {\n blends+=1')
 copy='extern fn raw_span_copy "__mempcpy_chk"(destination:*u8,source:*const u8,length,capacity:usize)rawptr\nfn native_span_copy(destination:*u8,source:*const u8,length,capacity:usize)rawptr {span_copies+=1\n return raw_span_copy(destination,source,length,capacity)}\n'
 (stage/'main.dyn').write_text(HEADER+'\n'+copy+shared+'\n'+REFERENCE.read_text()+'\n'+function(SOURCE,'sdl_render_texture'))
 for mode in ('debug','release'):
  output=stage/(mode+'.so')
  subprocess.run(['python3',str(ROOT/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(stage),'--shared','--'+mode,'--output',str(output)],check=True)
  lib=c.CDLL(str(output));lib.probe_setup.argtypes=[c.POINTER(c.c_ubyte)]+[c.c_int32]*11+[c.c_float]*2
  lib.probe_texture.argtypes=[c.c_int32,c.POINTER(c.c_ubyte),c.c_int32,c.c_int32,c.c_uint8,c.c_int32,c.POINTER(Rect),c.POINTER(Rect),c.POINTER(c.c_uint64)];lib.probe_texture.restype=c.c_bool
  def draw(reference,case,alias=False):
   w,h,source,destination,viewport,clip,scale,modulation,opaque,alpha=case
   data=(c.c_ubyte*(64*48*4))(*[(i*37+19)%256 for i in range(64*48*4)])
   if opaque:
    for i in range(3,len(data),4):data[i]=255
   texture=(c.c_ubyte*(w*h*4))(*[(i*43+29)%256 for i in range(w*h*4)])
   if alpha is not None:
    for i in range(3,len(texture),4):texture[i]=alpha
   src=Rect(*source) if source else None;dst=Rect(*destination) if destination else None
   lib.probe_setup(data,64,48,*viewport,*(clip or (0,0,0,0)),int(clip is not None),*scale);checks=(c.c_uint64*3)()
   ok=lib.probe_texture(reference,texture,w,h,modulation,int(alias),c.byref(src) if src else None,c.byref(dst) if dst else None,checks)
   return ok,bytes(data),tuple(checks)
  for number,case in enumerate(cases):
   before=draw(1,case);after=draw(0,case)
   assert before[:2]==after[:2],(mode,number,'pixels differ',case)
  before=draw(1,cases[0]);after=draw(0,cases[0])
  assert before[2][0]==3072 and after[2][0]<=1,(mode,'texture clipping repeated per pixel',before[2],after[2])
  full=(64,48,None,None,(0,0,64,48),None,(1.,1.),255,True,255)
  old=draw(1,full);new=draw(0,full)
  assert old[:2]==new[:2]
  assert new[2][1]==48 and new[2][2]==0,(mode,'opaque unit rows must bulk copy',new[2])
  for case in alias_cases:
   old=draw(1,case,True);new=draw(0,case,True)
   assert old[:2]==new[:2],(mode,'alias pixels differ',case)
   assert new[2][1]==0,(mode,'aliased source must retain sequential sampling',new[2])
  print(f'PASS native texture {mode}: {len(cases)} exact pixel cases; clipping checks {before[2][0]} -> {after[2][0]}; opaque rows bulk copied; {len(alias_cases)} alias cases',flush=True)
