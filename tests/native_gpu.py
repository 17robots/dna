#!/usr/bin/env python3
"""Direct GPU/window rendering against the software reference, on a real context.

No full-window CPU buffer is permitted in the direct path. Pixel comparisons
allow one UNORM rounding step, not missing glyphs, clipping or alpha changes.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from native_gpu_probe import install as install_gpu_probe
from source_patch import patched
import private_display  # hides the desktop display; see tests/private_display.py
if not private_display.available():
    print('SKIP native_gpu: native windows need a private display; see tests/private_display.py')
    raise SystemExit(0)
ROOT=Path(__file__).resolve().parents[1]
BACKEND=os.environ.get('DNA_NATIVE_BACKEND','wayland')
DYN=os.environ['DYN']
SOURCE=r'''
use "std/mem"
use "std/c"
#link("c")
extern fn report "dprintf"(fd:i32,format:*const u8,x,y,a,b:i32)i32
fn check(ok:bool,message:[]const u8) {if !ok {#panic(message)}}
original_upload:fn(u32,i32,i32,i32,i32,i32,u32,u32,rawptr) = nil
original_storage:fn(u32,i32,i32,i32,i32,i32,u32,u32,rawptr) = nil
uploads:usize
storages:usize
fail_storage:bool
fail_attachment:bool
original_status:fn(u32)u32 = nil
fn framebuffer_status(target:u32)u32 {
 if fail_attachment {fail_attachment=false
  return 36054}
 return original_status(target)
}
original_draw:fn(u32,i32,i32) = nil
draws:usize
fn draw_arrays(kind:u32,first,count:i32) {draws+=1
 original_draw(kind,first,count)}
fn upload(target:u32,level,x,y,w,h:i32,format,kind:u32,data:rawptr) {
 uploads+=1
 original_upload(target,level,x,y,w,h,format,kind,data)
}
fn storage(target:u32,level,internal,w,h,border:i32,format,kind:u32,data:rawptr) {
 storages+=1
 if fail_storage {fail_storage=false
 original_storage(0,level,internal,w,h,border,format,kind,data)
 return}
 original_storage(target,level,internal,w,h,border,format,kind,data)
}
fn scene(renderer:rawptr,phase:i32) {
 check(gui_color(renderer,13,29,47,255) && gui_clear(renderer),"clear")
 check(gui_viewport(renderer,nil) && gui_scale(renderer,1.0,1.0),"reset")
 viewport:=PixelRect{x:7,y:9,width:120,height:90}
 clip:=PixelRect{x:3,y:4,width:80,height:65}
 check(gui_viewport(renderer,&viewport) && gui_clip(renderer,&clip),"clip")
 rect:=Rect{x:-5.0,y:2.0,width:90.0,height:45.0}
 check(gui_color(renderer,221,39,11,128) && gui_fill(renderer,&rect),"alpha fill")
 rect=Rect{x:28.0,y:20.0,width:50.0,height:50.0}
 check(gui_color(renderer,1,201,117,255) && gui_fill(renderer,&rect),"opaque fill")
 check(gui_viewport(renderer,nil),"viewport reset")
 mask:[35]u8=[0,31,63,127,191,223,255,255,223,191,127,63,31,0,0,128,255,128,0,128,255,255,0,255,0,255,0,255,1,2,3,4,5,6,7]
 for i in 0..20 {
  check(native_text_cached_bitmap(renderer,1,&mask[0],7,5,#cast(f32,10+i*8),105.0,239,151,33,201),"cached glyph")
 }
 check(gui_scale(renderer,2.0,3.0),"scale")
 check(native_text_cached_bitmap(renderer,1,&mask[0],7,5,90.0,35.0,233,147,17,128),"scaled mask")
 check(gui_scale(renderer,1.0,1.0),"scale reset")
 texture:=gui_create_texture(renderer,0,2,13,9)
 check(texture!=nil && gui_target(renderer,texture),"texture target")
 if native_gui.direct {
  cached:=#cast(*NativeTexture,texture)
  check(cached.storage==nil && cached.pixels.len==0 && cached.framebuffer!=0,"GPU target retained CPU pixels")
 }
 check(gui_color(renderer,19,203,77,123) && gui_clear(renderer),"target clear")
 rect=Rect{x:3.0,y:2.0,width:6.0,height:5.0}
 check(gui_color(renderer,223,31,89,111) && gui_fill(renderer,&rect),"target alpha")
 check(native_text_cached_bitmap(renderer,1,&mask[0],7,5,1.0,1.0,255,255,255,255),"target glyph")
 check(gui_target(renderer,nil),"window target")
 rect=Rect{x:145.0,y:12.0,width:26.0,height:18.0}
 native_gui.draw_alpha=193
 check(gui_texture_alpha(texture,177),"opacity")
 check(gui_render_texture(renderer,texture,nil,&rect),"target composite")
 rect.x=180.0
 check(gui_render_texture(renderer,texture,nil,&rect),"target reuse")
 native_gui.draw_alpha=255
 for sample in 0..8 {
  crop:=Rect{x:-2.5+#cast(f32,sample)*0.75,y:-0.5,width:16.75,height:11.25}
  destination:=Rect{x:#cast(f32,sample*30),y:155.0,width:23.5,height:14.5}
  check(gui_render_texture(renderer,texture,&crop,&destination),"fractional source crop")
 }
 check(gui_target(renderer,texture),"target edit")
 check(gui_color(renderer,37,99,211,255) && gui_clear(renderer),"target repaint")
 check(gui_target(renderer,nil),"target restore")
 rect.x=215.0
 check(gui_render_texture(renderer,texture,nil,&rect),"dirty target upload")
 gui_destroy_texture(texture)
 vertices:[4]Vertex=[Vertex{x:145.0,y:45.0,red:1.0,alpha:0.5},Vertex{x:175.0,y:45.0,red:1.0,alpha:0.5},Vertex{x:175.0,y:75.0,red:1.0,alpha:0.5},Vertex{x:145.0,y:75.0,red:1.0,alpha:0.5}]
 indices:[6]i32=[0,1,2,0,2,3]
 if phase==0 {
  // The software triangle rasterizer can leave floating-point cracks on a
  // shared diagonal. Use the mathematical square as the independent oracle.
  rect=Rect{x:145.0,y:45.0,width:30.0,height:30.0}
  check(gui_color(renderer,255,0,0,127) && gui_fill(renderer,&rect),"triangle reference")
 } else {check(gui_geometry(renderer,nil,&vertices[0],4,&indices[0],6),"triangles")}
 check(gui_scale(renderer,1.5,1.3),"fractional scale")
 check(native_text_cached_bitmap(renderer,1,&mask[0],7,5,140.0,80.0,233,147,17,128),"fractional scaled mask")
 check(gui_scale(renderer,1.0,1.0),"fractional scale reset")
 // More than one batch of rectangles, retaining order and bounded storage.
 for i in 0..1200 {
  rect=Rect{x:#cast(f32,i%200),y:140.0+#cast(f32,i/200),width:1.0,height:1.0}
  check(gui_color(renderer,#cast(u8,i%255),93,211,255) && gui_fill(renderer,&rect),"batch rollover")
 }
}
fn popup_scene(renderer:rawptr) {
 mask:[35]u8=[0,31,63,127,191,223,255,255,223,191,127,63,31,0,0,128,255,128,0,128,255,255,0,255,0,255,0,255,1,2,3,4,5,6,7]
 // Popups use a full-window framebuffer texture. Non-power-of-two desktop
 // dimensions must preserve every glyph texel during one-to-one composition.
 popup:=gui_create_texture(renderer,0,2,2548,1407)
 check(popup!=nil && gui_target(renderer,popup),"desktop popup target")
 check(gui_clip(renderer,nil) && gui_color(renderer,33,37,43,255) && gui_clear(renderer),"desktop popup clear")
 for row in 0..234 {
  for col in 0..318 {
   check(native_text_cached_bitmap(renderer,1,&mask[0],7,5,#cast(f32,col*8),#cast(f32,row*6),220,225,235,255),"desktop popup glyph")
  }
 }
 check(gui_target(renderer,nil),"desktop popup restore")
 popup_rect:=Rect{width:2548.0,height:1407.0}
 check(gui_render_texture(renderer,popup,nil,&popup_rect),"desktop popup composite")
 gui_destroy_texture(popup)
}
fn snapshot(destination:[]u8) {
 width:=native_gui.surface.width
 height:=native_gui.surface.height
 if !native_gui.direct {
  _=mem.copy(destination,native_gui.surface.pixels)
  return
 }
 check(native_present.gpu_flush(&native_gui.gpu),"flush")
 api:=&native_gui.gpu.api
 api.pixel_store_i(3333,1)
 api.pixel_store_i(3330,0)
 api.pixel_store_i(3331,0)
 api.pixel_store_i(3332,0)
 for y in 0..height {
  at:=#cast(usize,y*width)*4
  api.read_pixels(0,height-1-y,width,1,6408,5121,#cast(rawptr,&destination[at]))
 }
 check(api.get_error()==0,"readback")
}
fn main() {
 title:="DNA GPU parity\x00"
 window:=gui_create_window(&title[0],320,180,0)
 check(window!=nil,"window")
 defer gui_destroy_window(window)
 // The compositor may constrain the actual drawable; rendering below uses
 // an exact-size test framebuffer rather than reading beyond that drawable.
 native_gui.window.width=2548
 native_gui.window.height=1407
 native_probe_software=true
 renderer:=gui_create_renderer(window,nil)
 check(renderer!=nil && !native_gui.direct,"software reference")
 owner:=mem.arena_alloc(65536)
 defer mem.arena_release(owner)
 size:=#cast(usize,native_gui.surface.width*native_gui.surface.height)*4
 reference:=mem.push_bytes(owner,size)
 popup_reference:=mem.push_bytes(owner,size)
 actual:=mem.push_bytes(owner,size)
 scene(renderer,0)
 snapshot(reference)
 popup_scene(renderer)
 snapshot(popup_reference)
 gui_destroy_renderer(renderer)
 native_probe_software=false
 renderer=gui_create_renderer(window,nil)
 check(renderer!=nil && native_gui.direct,"direct renderer")
 check(gui_create_renderer(window,nil)==nil && native_gui.direct,"duplicate renderer changed active state")
 check(native_gui.pixels==nil && native_gui.surface.pixels.len==0,"direct path allocated window pixels")
 original_upload=native_gui.gpu.api.tex_sub_image_2d
 original_storage=native_gui.gpu.api.tex_image_2d
 native_gui.gpu.api.tex_sub_image_2d=upload
 native_gui.gpu.api.tex_image_2d=storage
 original_draw=native_gui.gpu.api.draw_arrays
 native_gui.gpu.api.draw_arrays=draw_arrays
 original_status=native_gui.gpu.framebuffer_status
 native_gui.gpu.framebuffer_status=framebuffer_status
 scene(renderer,1)
 snapshot(actual)
 check(uploads==1 && storages==1,"glyph reuploaded or target CPU upload requested")
 differences:usize=0
 for i in 0..size {
  a:=#cast(i32,reference[i])
  b:=#cast(i32,actual[i])
  if a-b>1 || b-a>1 {differences+=1}
 }
 if differences!=0 {
  message:="pixel %d %d: %d != %d\n\x00"
  count:usize=0
  for i in 0..size {
   a:=#cast(i32,reference[i])
   b:=#cast(i32,actual[i])
   if a-b>1 || b-a>1 {
    _=report(2,&message[0],#cast(i32,i/4%#cast(usize,native_gui.surface.width)),#cast(i32,i/4/#cast(usize,native_gui.surface.width)),a,b)
    count+=1
    if count==12 {break}
   }
  }
 }
 check(differences==0,"direct GPU pixels differ from software reference")
 popup_scene(renderer)
 snapshot(actual)
 for i in 0..size {
  a:=#cast(i32,popup_reference[i])
  b:=#cast(i32,actual[i])
  if a-b>1 || b-a>1 {
   message:="popup pixel %d %d: %d != %d\n\x00"
   _=report(2,&message[0],#cast(i32,i/4%#cast(usize,native_gui.surface.width)),#cast(i32,i/4/#cast(usize,native_gui.surface.width)),a,b)
   #panic("desktop popup glyph texels differ from software reference")
  }
 }
 // Atlas identity remains safe when CPU addresses are reused after font close.
 mask:[1]u8=[255]
 first_draw:=draws
 for i in 0..32 {
  check(native_text_cached_bitmap(renderer,#cast(u64,100000+i),&mask[0],1,1,#cast(f32,i),149.0,255,255,255,255),"cold glyph batch")
 }
 check(native_present.gpu_flush(&native_gui.gpu) && draws-first_draw==1,"new atlas glyphs broke a compatible vertex batch")
 first_draw=draws
 first_upload:=uploads
 for i in 0..32 {
  check(native_text_cached_bitmap(renderer,#cast(u64,100000+i),&mask[0],1,1,#cast(f32,i),149.0,255,255,255,255),"warm glyph batch")
 }
 check(native_present.gpu_flush(&native_gui.gpu) && draws-first_draw==1 && uploads==first_upload,"cached glyph batch reuploaded or split")
 check(native_text_cached_bitmap(renderer,2,&mask[0],1,1,2.0,2.0,255,255,255,255),"first identity")
 mask[0]=0
 check(native_text_cached_bitmap(renderer,3,&mask[0],1,1,3.0,2.0,255,255,255,255),"new identity same address")
 for i in 0..2050 {
  mask[0]=#cast(u8,i%255)
  check(native_text_cached_bitmap(renderer,#cast(u64,10+i),&mask[0],1,1,#cast(f32,i%300),150.0,255,255,255,255),"atlas eviction")
 }
 check(native_gui.gpu.slot_count<=2048 && native_present.gpu_flush(&native_gui.gpu),"bounded atlas")
 // Force atlas-space rollover with pending vertices. Earlier glyphs must
 // be submitted before their texels are overwritten by the new generation.
 large:=mem.push_bytes(owner,1024*512)
 clear:=Rect{x:250.0,y:150.0,width:3.0,height:1.0}
 check(gui_color(renderer,0,0,0,255) && gui_fill(renderer,&clear),"rollover background")
 check(gui_scale(renderer,1.0/1024.0,1.0/512.0),"rollover scale")
 for i in 0..3 {
  value:u8=55
  if i==1 {value=111}
  if i==2 {value=199}
  for at in 0..large.len {large[at]=value}
  check(native_text_cached_bitmap(renderer,#cast(u64,900000+i),&large[0],1024,512,#cast(f32,(250+i)*1024),150.0*512.0,255,255,255,255),"atlas space rollover")
 }
 check(gui_scale(renderer,1.0,1.0),"rollover scale reset")
 snapshot(actual)
 at:=#cast(usize,150*native_gui.surface.width+250)*4
 check(actual[at]==55 && actual[at+4]==111 && actual[at+8]==199,"atlas eviction overwrote pending glyph pixels")
 check(gui_present(renderer),"swap")
 retained:=gui_create_texture(renderer,0,2,2,2)
 check(retained!=nil,"retained target")
 retained_texture:=#cast(*NativeTexture,retained)
 fail_storage=true
 check(!gui_target(renderer,retained),"storage failure accepted")
 check(retained_texture.gpu==0 && retained_texture.framebuffer==0,"failed texture allocation retained an invalid ID")
 check(native_gui.target==nil,"failed target switch changed active target")
 fail_attachment=true
 check(!gui_target(renderer,retained),"incomplete framebuffer accepted")
 check(retained_texture.gpu==0 && retained_texture.framebuffer==0 && native_gui.target==nil,"incomplete framebuffer cleanup changed active target")
 binding:i32=-1
 native_gui.gpu.api.get_integer(36006,&binding)
 check(binding==#cast(i32,native_gui.gpu.window_framebuffer),"failed framebuffer switch did not restore binding")
 check(gui_target(renderer,retained),"storage allocation retry")
 check(gui_color(renderer,23,59,181,255) && gui_clear(renderer),"retained background")
 corner:=Rect{width:1.0,height:1.0}
 check(gui_color(renderer,177,11,55,255) && gui_fill(renderer,&corner),"retained corner")
 shifted:=Rect{x:1.0,width:2.0,height:2.0}
 check(gui_render_texture(renderer,retained,nil,&shifted),"sequential self-blit")
 check(retained_texture.storage==nil && retained_texture.pixels.len==0,"self-blit retained CPU scratch")
 check(gui_target(renderer,nil),"retained target reset")
 destination:=Rect{x:1.0,y:1.0,width:2.0,height:2.0}
 check(gui_render_texture(renderer,retained,nil,&destination),"retained composite")
 check(retained_texture.gpu!=0 && retained_texture.storage==nil,"texture allocation retry state")
 gui_destroy_renderer(renderer)
 check(retained_texture.gpu==0 && retained_texture.framebuffer==0 && retained_texture.pixels.len==16,"renderer recreation lost target backup")
 check(native_gui.gpu.program==0,"destroy resources")
 renderer=gui_create_renderer(window,nil)
 check(renderer!=nil && native_gui.gpu.slot_count==0,"recreate context resources")
 check(native_gui.pixels==nil,"recreate allocated window pixels")
 check(gui_render_texture(renderer,retained,nil,&destination),"recreated texture upload")
 check(retained_texture.storage==nil && retained_texture.pixels.len==0,"recreated target retained CPU backup")
 snapshot(actual)
 top:=#cast(usize,native_gui.surface.width+1)*4
 bottom:=#cast(usize,native_gui.surface.width*2+2)*4
 check(actual[top]==177 && actual[top+1]==11 && actual[top+2]==55,"recreated target top-left flipped or changed")
 check(actual[top+4]==177 && actual[top+5]==11 && actual[top+6]==55,"self-blit result lost on renderer recreation")
 check(actual[bottom]==23 && actual[bottom+1]==59 && actual[bottom+2]==181,"recreated target bottom-right flipped or changed")
 gui_destroy_renderer(renderer)
 native_probe_software=true
 renderer=gui_create_renderer(window,nil)
 check(renderer!=nil && !native_gui.direct,"software after GPU recreation")
 check(gui_render_texture(renderer,retained,nil,&destination),"software target restore")
 snapshot(actual)
 check(actual[top]==177 && actual[top+1]==11 && actual[bottom]==23 && actual[bottom+2]==181,"software restored target orientation")
 gui_destroy_texture(retained)
 check(native_gui.textures==nil,"texture owner list leaked")
 gui_destroy_renderer(renderer)
}
'''
with tempfile.TemporaryDirectory(prefix='dna-native-gpu-') as directory:
    work=Path(directory);stage=work/'platform';stage.mkdir()
    types=(ROOT/'src/platform/platform.dyn').read_text();declarations=[]
    for match in re.finditer(r'pub struct [A-Za-z_]+\s*\{',types):
        depth=1;end=match.end()
        while depth:
            if types[end]=='{':depth+=1
            if types[end]=='}':depth-=1
            end+=1
        declarations.append(types[match.start():end])
    (stage/'types.dyn').write_text('use "std/mem"\n#link("dna_native")\n'+'\n'.join(re.findall(r'^pub const [A-Za-z_]+\s*:\s*u32\s*=\s*[0-9]+$',types,re.M))+'\n'+'\n'.join(declarations))
    gui=patched((ROOT/'src/platform/gui.dyn').read_text(), 'native_gui.direct = !native_software_requested()', 'native_gui.direct=!native_probe_software')
    gui=install_gpu_probe(gui)
    gui+='\nnative_probe_software:bool\n'
    (stage/'platform.dyn').write_text(gui)
    for module in ('host','owned_arena','cstring'):
        shutil.copytree(ROOT/'src'/module,stage/module)
    for selection in [*(ROOT/'src/platform').glob('window_*.dyn'), *(ROOT/'src/platform').glob('memory_*.dyn')]:
        shutil.copyfile(selection,stage/selection.name)
    shutil.copytree(ROOT/'src/platform/native_present',stage/'native_present')
    (stage/'backend').mkdir();shutil.copyfile(ROOT/f'modules/native/platform_{BACKEND}.dyn',stage/'backend/backend.dyn')
    if BACKEND=='x11':
        for source in [stage/'platform.dyn',*stage.glob('window_*.dyn'),*(stage/'native_present').rglob('*.dyn')]:
            source.write_text(source.read_text().replace('"vendor/window/wayland"','"vendor/window"'))
    (stage/'main.dyn').write_text(SOURCE)
    library=ROOT/('build/native-wayland' if BACKEND=='wayland' else 'build/native-gui')
    environment=dict(os.environ,DYN_LIBRARY_PATH=str(library),LD_LIBRARY_PATH=str(library))
    for mode in ('debug','release'):
        output=work/mode
        subprocess.run([DYN,'build',str(stage),'--'+mode,'--quiet','--link','-rpath='+str(library),'--output',str(output)],env=environment,check=True,timeout=180)
        subprocess.run([str(output)],env=environment,check=True,timeout=60)
        print(f'PASS direct GPU parity, bounded batching/atlas, target upload reuse and renderer recreation ({mode}, {BACKEND})',flush=True)
