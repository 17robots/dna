"""Test-only framebuffer/readback adapter for existing editor frame oracles.

A private FBO gives each fake resize its exact dimensions, independent of the
window manager. Readback storage and FBOs never enter the production executable.
"""
HELPER=r'''
native_probe_framebuffer:u32
native_probe_texture:u32
native_probe_owner:*mem.Arena
native_probe_buffer:[]u8
native_probe_width:i32
native_probe_height:i32
native_probe_dirty:bool=true
fn native_probe_resize()bool {
 if !native_resize() {return false}
 if !native_gui.direct {return true}
 if native_probe_width==native_gui.surface.width && native_probe_height==native_gui.surface.height {return true}
 if !native_present.gpu_flush(&native_gui.gpu) {return false}
 api:=&native_gui.gpu.api
 gen_name:="glGenFramebuffers\x00"
 bind_name:="glBindFramebuffer\x00"
 attach_name:="glFramebufferTexture2D\x00"
 status_name:="glCheckFramebufferStatus\x00"
 gen:=#cast(fn(i32,*u32),window_api.gl_proc(&gen_name[0]))
 bind:=#cast(fn(u32,u32),window_api.gl_proc(&bind_name[0]))
 attach:=#cast(fn(u32,u32,u32,u32,i32),window_api.gl_proc(&attach_name[0]))
 status:=#cast(fn(u32)u32,window_api.gl_proc(&status_name[0]))
 if gen==nil || bind==nil || attach==nil || status==nil {return false}
 if native_probe_framebuffer==0 {gen(1,&native_probe_framebuffer)}
 if native_probe_texture==0 {api.gen_textures(1,&native_probe_texture)}
 api.active_texture(33984)
 api.bind_texture(3553,native_probe_texture)
 api.bind_buffer(35052,0)
 api.tex_image_2d(3553,0,32856,native_gui.surface.width,native_gui.surface.height,0,6408,5121,nil)
 bind(36160,native_probe_framebuffer)
 attach(36160,36064,3553,native_probe_texture,0)
 if status(36160)!=36053 || api.get_error()!=0 {return false}
 native_gui.gpu.window_framebuffer=native_probe_framebuffer
 native_gui.gpu.framebuffer=native_probe_framebuffer
 native_probe_width=native_gui.surface.width
 native_probe_height=native_gui.surface.height
 return true
}
fn native_probe_pixels()[]const u8 {
 if !native_gui.direct {return native_gui.surface.pixels}
 if !native_probe_dirty && #len(native_probe_buffer)>0 {return native_probe_buffer}
 if !native_probe_resize() || !native_present.gpu_flush(&native_gui.gpu) {#panic("GPU probe flush")}
 size:=#cast(usize,native_gui.surface.width)*#cast(usize,native_gui.surface.height)*4
 if #len(native_probe_buffer)!=size {
  if native_probe_owner==nil {native_probe_owner=mem.arena_create(65536)}
  else {mem.arena_reset(native_probe_owner)}
  native_probe_buffer=mem.push_bytes_uninit(native_probe_owner,size)
 }
 api:=&native_gui.gpu.api
 api.pixel_store_i(3333,1)
 api.pixel_store_i(3330,0)
 api.pixel_store_i(3331,0)
 api.pixel_store_i(3332,0)
 for y in 0..native_gui.surface.height {
  at:=#cast(usize,y)*native_gui.surface.stride
  api.read_pixels(0,native_gui.surface.height-1-y,native_gui.surface.width,1,6408,5121,#cast(rawptr,&native_probe_buffer[at]))
 }
 if api.get_error()!=0 {#panic("GPU probe readback")}
 native_probe_dirty=false
 return native_probe_buffer
}
fn native_probe_blank() {
 if native_gui.direct {
  if !native_present.gpu_clear(&native_gui.gpu,native_gui.surface.width,native_gui.surface.height,ui.Color{}) {#panic("GPU blank probe")}
 } else {
  for i in 0..#len(native_gui.surface.pixels) {native_gui.surface.pixels[i]=0}
 }
}
fn native_probe_destroy() {
 native_gui.gpu.window_framebuffer=0
 native_gui.gpu.framebuffer=0
 if native_probe_framebuffer!=0 {
  name:="glDeleteFramebuffers\x00"
  remove:=#cast(fn(i32,*const u32),window_api.gl_proc(&name[0]))
  remove(1,&native_probe_framebuffer)
  native_gui.gpu.api.delete_textures(1,&native_probe_texture)
 }
 mem.arena_release(native_probe_owner)
 native_probe_owner=nil
 native_probe_framebuffer=0
 native_probe_texture=0
 native_probe_width=0
 native_probe_height=0
 native_probe_buffer=native_probe_buffer[..0]
}
'''
def install(source):
    source=source.replace("fn sdl_present(renderer:rawptr)bool{", "fn sdl_present(renderer:rawptr)bool{native_probe_dirty=true\n")
    source=source.replace('return native_gui.surface.pixels','return native_probe_pixels()')
    source=source.replace('if !native_resize()', 'if !native_probe_resize()')
    source=source.replace('native_memory.zero(native_gui.surface.pixels)','native_probe_blank()')
    source=source.replace('fn sdl_destroy_renderer(renderer: rawptr) {','fn sdl_destroy_renderer(renderer: rawptr) {\n native_probe_destroy()')
    return source+'\n'+HELPER
