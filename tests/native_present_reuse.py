#!/usr/bin/env python3
"""Count real presenter GL calls without a display; cover storage reuse/retry."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'src/platform/native_present/native_present.dyn'

def function(source,name):
    start=source.index(('pub ' if 'pub fn '+name+'(' in source else '')+'fn '+name+'(')
    brace=source.index('{',start);depth,end=1,brace+1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return source[start:end]

FIXTURE=r'''use "std/testing" testing
images:u32
buffers:u32
parameters:u32
updates:u32
quads:u32
pending_error:u32
fail_buffer:bool
fail_image:bool
fail_update:bool
image_width:i32
image_height:i32
update_width:i32
update_height:i32
state:u32
fn noop_one(value:u32){}
fn noop_two(a,b:u32){}
fn noop_delete(n:i32,values:*const u32){}
fn bind_buffer(target,value:u32){if target==gl.PixelUnpackBuffer{testing.expect(value==0,"unpack buffer reset")} }
fn pixel_store(key:u32,value:i32){
 if key==gl.UnpackAlignment{testing.expect(value==1,"alignment reset")
state|=1}
 if key==gl.UnpackRowLength{testing.expect(value==0,"row length reset")
state|=2}
 if key==gl.UnpackSkipRows{testing.expect(value==0,"skip rows reset")
state|=4}
 if key==gl.UnpackSkipPixels{testing.expect(value==0,"skip pixels reset")
state|=8}
}
fn sampler(unit,value:u32){testing.expect(unit==0 && value==0,"sampler reset")
state|=16}
fn disable(value:u32){
 if value==gl.Blend{state|=32}
 if value==gl.DepthTest{state|=64}
 if value==gl.CullFace{state|=128}
 if value==gl.ScissorTest{state|=256}
}
fn texture_parameter(target,key:u32,value:i32){parameters+=1}
fn viewport(x,y,width,height:i32){testing.expect(x==0 && y==0 && width>0 && height>0,"viewport")}
fn uniform_one(location,value:i32){}
fn uniform_two(location:i32,x,y:f32){}
fn uniform_four(location:i32,x,y,z,w:f32){}
fn color(r,g,b,a:f32){}
fn buffer_data(target:u32,size:isize,bytes:rawptr,usage:u32){buffers+=1
 if fail_buffer{pending_error=1285
 fail_buffer=false}}
fn image(target:u32,level,internal,width,height,border:i32,format,kind:u32,bytes:rawptr){
 images+=1
 image_width=width
 image_height=height
 if fail_image{pending_error=1285
fail_image=false}
}
fn update(target:u32,level,x,y,width,height:i32,format,kind:u32,bytes:rawptr){
 testing.expect(x==0 && y==0 && bytes!=nil,"complete texture update")
 updates+=1
 update_width=width
 update_height=height
 if fail_update{pending_error=1282
fail_update=false}
}
fn error()u32{value:=pending_error
pending_error=0
return value}
fn draw_arrays(kind:u32,first,count:i32){testing.expect(state==511,"presenter resets complete inherited state")
state=0
quads+=1}
fn renderer()Presenter{
 api:=gl.Api{viewport:viewport,use_program:noop_one,bind_vertex_array:noop_one,bind_buffer:bind_buffer,active_texture:noop_one,bind_sampler:sampler,bind_texture:noop_two,pixel_store_i:pixel_store,tex_parameter_i:texture_parameter,disable:disable,clear_color:color,clear:noop_one,uniform_2f:uniform_two,uniform_1i:uniform_one,tex_image_2d:image,tex_sub_image_2d:update,uniform_4f:uniform_four,buffer_data:buffer_data,draw_arrays:draw_arrays,get_error:error,delete_program:noop_one,delete_vertex_arrays:noop_delete,delete_buffers:noop_delete,delete_textures:noop_delete}
 return Presenter{api:api,program:1,vao:2,buffer:3,texture:4,max_texture:1024}
}
fn main(){
 pixels:[4096]u8=[]
 surface:=software.Surface{pixels:pixels[..],width:16,height:8,stride:64}
 present:=renderer()
 for frame in 0..64{testing.expect(draw(&present,surface).ok,"warm present")}
 // This is the red-cap: the old presenter reallocates 64 times here.
 testing.expect(images==1,"same-size frames must allocate texture once")
 testing.expect(updates==64 && quads==64,"each frame updates and draws")
 testing.expect(buffers==1,"same-size frames must allocate vertices once")
 testing.expect(parameters==4,"private texture parameters set once")
 surface.width=24
surface.height=10
surface.stride=96
 testing.expect(draw(&present,surface).ok,"resize present")
 testing.expect(images==2 && updates==65 && image_width==24 && image_height==10 && update_width==24 && update_height==10,"resize storage and full update")
 testing.expect(buffers==1,"resize must keep static vertex storage")
 surface.width=32
surface.height=12
surface.stride=128
 fail_image=true
 before:=quads
 testing.expect(!draw(&present,surface).ok,"allocation error surfaced")
 testing.expect(images==3 && updates==65 && quads==before,"failed allocation never updates or draws")
 testing.expect(draw(&present,surface).ok,"allocation retry")
 testing.expect(images==4 && updates==66 && quads==before+1,"allocation failure does not cache dimensions")
 fail_update=true
 testing.expect(!draw(&present,surface).ok,"upload error surfaced")
 testing.expect(draw(&present,surface).ok,"upload retry")
 testing.expect(images==4 && updates==68,"upload failure preserves storage and retries content")
 surface.width=1025
 before=images
 testing.expect(!draw(&present,surface).ok && images==before,"over-limit input rejected before allocation")
 close(&present)
 testing.expect(present.program==0 && present.texture==0,"close clears resource state")
 present=renderer()
 surface.width=16
surface.height=8
surface.stride=64
 testing.expect(draw(&present,surface).ok && images==before+1,"recreated presenter allocates fresh storage")
 // A failed vertex allocation must retry even when texture storage succeeded.
 close(&present)
 present=renderer()
 surface.width=20
 surface.stride=80
 before=quads
 vertex_attempts:=buffers
 fail_buffer=true
 testing.expect(!draw(&present,surface).ok && quads==before,"vertex allocation error surfaced before drawing")
 testing.expect(draw(&present,surface).ok && buffers==vertex_attempts+2,"vertex allocation retried")
 close(&present)
}
'''
source=SOURCE.read_text()
header='use "vendor/opengl" gl\nuse "std/ui"\nuse "std/ui/software"\nuse "std/errors"\n'
header+=re.search(r'pub struct Presenter \{[^\n]+',source).group()+'\n'
header+='pub struct Result {kind:errors.Kind,ok:bool}\n'
header+='\n'.join(function(source,name) for name in ('healthy','quad','draw','close'))+'\n'
with tempfile.TemporaryDirectory(prefix='dna-present-reuse-') as temporary:
    stage=Path(temporary)
    (stage/'main.dyn').write_text(header+FIXTURE)
    for mode in ('debug','release'):
        output=stage/mode
        subprocess.run(['python3',str(ROOT/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(stage),'--'+mode,'--output',str(output)],check=True,timeout=120)
        subprocess.run([str(output)],check=True,timeout=15)
        print('PASS native presenter storage reuse, resize, error/retry and state reset ('+mode+')',flush=True)
