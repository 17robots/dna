#!/usr/bin/env python3
"""Differential native raster pixels and work counts against frozen geometry."""
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import statistics
import time
import tempfile
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--baseline',type=Path,default=ROOT/'tests/fixtures/native_geometry_reference.dyn')
parser.add_argument('--timings',action='store_true',help='Run only in an otherwise quiet timing slot')
parser.add_argument('--samples',type=int,default=20)
parser.add_argument('--candidate',type=Path,default=ROOT/'src/platform/gui.dyn')
parser.add_argument('--output',type=Path,default=ROOT/'build/rad-feel-20261027/triangle-bounds.json')
args=parser.parse_args()
current=args.candidate

from native_software_source import function

HEADER='''use "std/ui"
use "std/ui/software"
struct PixelRect {x,y,width,height:i32}
struct Vertex {x,y,red,green,blue,alpha,u,v:f32}
struct NativeTexture {pixels:[]u8,width,height:i32}
struct Gui {surface:software.Surface,target:*NativeTexture,viewport,clip:PixelRect,clipped:bool,draw_alpha:u8=255,sx,sy:f32}
native_gui:Gui
visits:u64=0
pub fn probe_setup(pixels:*u8,width,height:i32) {
 native_gui=Gui{surface:software.Surface{pixels:pixels[..#cast(usize,width)*#cast(usize,height)*4],width:width,height:height,stride:#cast(usize,width)*4},viewport:PixelRect{width:width,height:height},sx:1.0,sy:1.0}
}
pub fn probe_viewport(x,y,width,height:i32) {native_gui.viewport=PixelRect{x:x,y:y,width:width,height:height}}
pub fn probe_clip(x,y,width,height:i32,enabled:i32) {native_gui.clipped=enabled!=0
 native_gui.clip=PixelRect{x:x,y:y,width:width,height:height}}
pub fn probe_scale(x,y:f32) {native_gui.sx=x
 native_gui.sy=y}
'''
WRAPPER='''pub fn probe_geometry(which:i32,vertices:*const Vertex,count:i32,indices:*const i32,index_count:i32,output:*u64)i32 {
 visits=0
 ok:=false
 if which==0 {ok=baseline_geometry(nil,nil,vertices,count,indices,index_count)}
 else {ok=candidate_geometry(nil,nil,vertices,count,indices,index_count)}
 output.*=visits
 if ok {return 1}
 return 0
}
'''
class Vertex(c.Structure):
    _fields_=[(name,c.c_float) for name in ('x','y','red','green','blue','alpha','u','v')]

def vertex(x,y,color=(.8,.2,.6,.5)):
    return Vertex(x,y,*color,0,0)

rng=random.Random(70139)
cases=[([(1,1),(4,1),(1,4)],[0,1,2],(2147483647,2147483647,1,1),None,(1.,1.))]

# Deterministic boundaries, shared edges, windings, degenerates, subpixel and huge/offscreen coordinates.
for points in (((1,1),(3,1),(1,4)),((-.75,-.25),(30.1,2.3),(2.5,35.9)),
               ((0,0),(64,0),(0,48)),((2,2),(2,2),(2,2)),
               ((-1e15,-1e15),(1e15,0),(0,1e15)),((1e12,1e12),(1e12,2e12),(2e12,1e12)),
               ((-1000,-1000),(-900,-1000),(-1000,-900)),((.5,.5),(20.5,.5),(.5,20.5))):
    for winding in ((0,1,2),(0,2,1)):
        for clip in (None,(3,4,20,17),(-10,-20,15,25),(100,100,4,4)):
            cases.append((list(points),list(winding),(0,0,64,48),clip,(1.,1.)))
for _ in range(350):
    points=[(rng.uniform(-100,100),rng.uniform(-80,100)) for _ in range(3)]
    viewport=(rng.randint(-20,20),rng.randint(-20,20),rng.randint(1,80),rng.randint(1,70))
    clip=None if rng.randrange(3)==0 else (rng.randint(-20,50),rng.randint(-20,40),rng.randint(0,70),rng.randint(0,60))
    scale=(rng.choice((.5,1.,1.25,2.)),rng.choice((.5,1.,1.5,2.)))
    cases.append((points,[0,1,2],viewport,clip,scale))

with tempfile.TemporaryDirectory(prefix='dna-native-triangles-') as temporary:
    stage=Path(temporary)
    names=['native_surface','native_clip','native_blend','native_blend_at','native_edge','native_top_left']
    if 'fn native_draw_alpha(' in current.read_text():names.append('native_draw_alpha')
    shared='\n'.join(function(current,name) for name in names)
    bodies=[]
    for path,name in ((args.baseline,'baseline_geometry'),(current,'candidate_geometry')):
        body=function(path,'sdl_geometry').replace('fn sdl_geometry(',f'fn {name}(')
        body=body.replace('        wa:=native_edge','        visits+=1\n        wa:=native_edge')
        bodies.append(body)
    (stage/'main.dyn').write_text(HEADER+'\n'+shared+'\n'+'\n'.join(bodies)+'\n'+WRAPPER)
    reports={}
    for mode in ('debug','release'):
        binary=stage/(mode+'.so')
        subprocess.run([os.environ.get('DYN','dyn'),'build',str(stage),'--shared','--'+mode,'--output',str(binary)],check=True)
        lib=c.CDLL(str(binary))
        lib.probe_setup.argtypes=[c.c_void_p,c.c_int32,c.c_int32]
        lib.probe_viewport.argtypes=[c.c_int32]*4
        lib.probe_clip.argtypes=[c.c_int32]*5
        lib.probe_scale.argtypes=[c.c_float,c.c_float]
        lib.probe_geometry.argtypes=[c.c_int32,c.POINTER(Vertex),c.c_int32,c.POINTER(c.c_int32),c.c_int32,c.POINTER(c.c_uint64)]
        lib.probe_geometry.restype=c.c_int32
        def draw(which,points,indices,viewport,clip,scale,width=64,height=48):
            data=(c.c_ubyte*(width*height*4))()
            for i in range(len(data)):data[i]=(i*37+19)%256
            lib.probe_setup(data,width,height)
            lib.probe_viewport(*viewport)
            lib.probe_clip(*(clip or (0,0,0,0)),int(clip is not None))
            lib.probe_scale(*scale)
            vertices=(Vertex*len(points))(*(vertex(*p, color=((i+1)/4,.25,.75,(i+1)/4)) for i,p in enumerate(points)))
            order=(c.c_int32*len(indices))(*indices)
            visited=c.c_uint64()
            ok=lib.probe_geometry(which,vertices,len(vertices),order,len(order),c.byref(visited))
            return ok,bytes(data),visited.value
        for number,case in enumerate(cases):
            baseline=draw(0,*case);candidate=draw(1,*case)
            assert baseline[:2]==candidate[:2],(mode,number,case,baseline[0],candidate[0])
        # RGBA shared-edge quad and malformed index/count results remain identical.
        quad=([(2,2),(20,2),(20,22),(2,22)],[0,1,2,0,2,3],(0,0,64,48),None,(1.,1.))
        assert draw(0,*quad)[:2]==draw(1,*quad)[:2]
        invalid=(quad[0],[0,1,9],*quad[2:])
        assert draw(0,*invalid)[:2]==draw(1,*invalid)[:2]
        tiny=([(2,2),(4,2),(2,4)],[0,1,2],(0,0,1000,800),None,(1.,1.))
        baseline=draw(0,*tiny,width=1000,height=800)
        candidate=draw(1,*tiny,width=1000,height=800)
        assert baseline[:2]==candidate[:2]
        assert baseline[2]==800000 and candidate[2]==4,(baseline[2],candidate[2])
        reports[mode]={'pixel_equivalence_cases':len(cases)+3,'tiny_triangle_baseline_visits':baseline[2],'tiny_triangle_candidate_visits':candidate[2]}
        if args.timings:
            assert args.samples>=5
            timing={}
            for which,label in ((0,'baseline'),(1,'candidate')):
                # Keep every borrowed buffer alive and exclude allocation/setup
                # from timing the real production geometry function.
                retained=(c.c_ubyte*(1000*800*4))()
                vertices=(Vertex*3)(vertex(2,2),vertex(4,2),vertex(2,4))
                order=(c.c_int32*3)(0,1,2)
                visited=c.c_uint64()
                lib.probe_setup(retained,1000,800)
                lib.probe_geometry(which,vertices,3,order,3,c.byref(visited))
                samples=[]
                for _ in range(args.samples):
                    started=time.perf_counter_ns()
                    assert lib.probe_geometry(which,vertices,3,order,3,c.byref(visited))==1
                    samples.append(time.perf_counter_ns()-started)
                ordered=sorted(samples)
                timing[label]={'n':len(samples),'median_ns':statistics.median(samples),'p95_ns':ordered[(95*len(samples)+99)//100-1],'raw_ns':samples}
            reports[mode]['warm_geometry_timing']=timing
    report={'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'timing_note':'Warm production-function calls include FFI overhead; tiny triangle microbenchmark, not whole-frame latency.','baseline_sha256':hashlib.sha256(args.baseline.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256(current.read_bytes()).hexdigest(),'reports':reports}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
