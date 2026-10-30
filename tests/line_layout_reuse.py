#!/usr/bin/env python3
"""Production line-pool work probe: edit one window of four on one document."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build/render-reuse'
DYN=str(Path(os.environ.get('DYN',ROOT.parent/'dyn/compiler/build/dyn-release')).resolve())
parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true');args=parser.parse_args()
WORK.mkdir(parents=True,exist_ok=True)
source=(ROOT/'src/line_layout.dyn').read_text();baseline=WORK/'baseline-line_layout.dyn'
if not baseline.exists():baseline.write_text(source)
name='layout-baseline' if args.baseline else 'layout-candidate';stage=WORK/name;stage.mkdir(exist_ok=True)
for module in ('buffer','owned_arena'):
 shutil.copytree(ROOT/'src'/module,stage/module,dirs_exist_ok=True)
(stage/'ttf').mkdir(exist_ok=True)
(stage/'ttf/ttf.dyn').write_text('''pub struct Substring {flags:u32,offset:i32,length:i32,line:i32,cluster:i32,x:i32,y:i32,width:i32,height:i32}
pub fn create(engine,font:rawptr,bytes:*const u8,length:usize)rawptr{return #cast(rawptr,1)}
pub fn destroy(text:rawptr){}
pub fn set(text:rawptr,bytes:*const u8,length:usize)bool{return true}
pub fn wrap(text:rawptr,width:i32)bool{return true}
pub fn whitespace_visible(text:rawptr,visible:bool)bool{return true}
pub fn set_font(text,font:rawptr)bool{return true}
pub fn draw(text:rawptr,x,y:f32)bool{return true}
pub fn substring(text:rawptr,offset:i32,out:*Substring)bool{return true}
''')
main='''use "std/mem"
use "./owned_arena" arena_owner
use "./buffer" buffer
use "./ttf" ttf
struct Typography {font:rawptr,engine:rawptr,line:f32}
struct Rgb {red:u8,green:u8,blue:u8}
fn tint(text:rawptr,color:Rgb)bool{return true}
struct TextViewport {start:usize,end:usize,y:f32}
pub fn probe()u64 {
 arena:=arena_owner.create(0)
 defer arena_owner.release(arena)
 doc:=buffer.allocate(arena)
 source:[12000]u8=[]
 used:usize=0
 for i in 0..600 {for byte in "office אבג é AV\\n" {source[used]=byte
   used+=1}}
 if !buffer.load(doc,source[..used]) {#panic("line layout probe document")}
 typography:=Typography{font:#cast(rawptr,1),engine:#cast(rawptr,1),line:16.0}
 layouts:[4]LineLayout=[]
 first:[4]usize=[0,50,100,450]
 for i in 0..4 {_=line_layout_update(&typography,&layouts[i],doc,1,TextViewport{start:buffer.row_start(doc,first[i]),end:buffer.row_start(doc,first[i]+20)})}
 before:u64=0
 for i in 0..4 {before+=layouts[i].builds}
 buffer.move_to(doc,buffer.row_start(doc,450),false)
 if !buffer.replace(doc,"x") {#panic("line layout probe edit")}
 after:u64=0
 for i in 0..4 {_=line_layout_update(&typography,&layouts[i],doc,1,TextViewport{start:buffer.row_start(doc,first[i]),end:buffer.row_start(doc,first[i]+20)})
  after+=layouts[i].builds}
 return after-before
}
'''
# Document exceeds the inline fixture source buffer on multibyte text; reserve
# the exact test bound independently of production layout/cache capacities.
main=main.replace('source:[12000]u8','source:[18000]u8')
(stage/'main.dyn').write_text(main+(baseline.read_text() if args.baseline else source))
output=WORK/(name+'.so')
subprocess.run([DYN,'build',str(stage),'--shared','--release','--quiet','--no-cache','--output',str(output)],check=True,timeout=120)
library=ctypes.CDLL(str(output));library.probe.restype=ctypes.c_uint64
report={'visible_layout_rebuilds_after_one_edit':library.probe(),'panes':4}
(WORK/(name+'-counts.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if not args.baseline:assert report['visible_layout_rebuilds_after_one_edit']==1,'unchanged earlier viewports must retain layout pools'
