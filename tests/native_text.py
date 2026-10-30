#!/usr/bin/env python3
"""Optional Dyn font/layout backend: source byte ranges and owned lifetime."""
import os
from pathlib import Path
import shutil
import subprocess
import struct
import re
import tempfile
ROOT = Path(__file__).resolve().parents[1]
DYN = str(Path(os.environ.get('DYN', ROOT.parent/'dyn/compiler/build/dyn-release')).resolve())
SOURCE = r'''
use "std/bytes" byte_ops
pub struct Substring { flags:u32, offset:i32, length:i32, line:i32, cluster:i32, x:i32, y:i32, width:i32, height:i32 }
fn check(ok:bool) { if !ok { #panic("native text contract") } }
fn main() {
 path: [4096]u8 = []
 name := "FONT_PATH"
 _ = mem.copy(path[..#len(name)],name)
 font := ttf_open(&path[0],16.0)
 check(font!=nil)
 check(ttf_font_height(nil)==0)
 first_height:=ttf_font_height(font)
 check(first_height>0)
 check(native_libraries.fonts==1)
 if #sizeof(NativeFont)>16384 {#panic("font metadata startup budget")}
 // Verify the real HarfBuzz blob shares the font bytes we retain, rather than
 // silently copying an entire font file again.
 get_face:=#cast(fn(rawptr)rawptr,dynlib.symbol(native_libraries.harfbuzz,"hb_font_get_face").value)
 reference_blob:=#cast(fn(rawptr)rawptr,dynlib.symbol(native_libraries.harfbuzz,"hb_face_reference_blob").value)
 get_data:=#cast(fn(rawptr,*u32)*const u8,dynlib.symbol(native_libraries.harfbuzz,"hb_blob_get_data").value)
 real_font:=#cast(*NativeFont,font)
 blob:=reference_blob(get_face(real_font.shaped))
 blob_length:u32=0
 blob_bytes:=get_data(blob,&blob_length)
 check(blob_bytes==&real_font.face.data[0] && #cast(usize,blob_length)==#len(real_font.face.data))
 native_libraries.hb.blob_destroy(blob)
 large_name:="LARGE_FONT_FILE\x00"
 large:=ttf_open(&large_name[0],16.0)
 check(large!=nil)
 large_font:=#cast(*NativeFont,large)
 if large_font.file.backing>#len(large_font.face.data)+131072 {#panic("font reader retained geometric growth copies")}
 replacement:=std_fs.create(large_name[..#len(large_name)-1])
 check(replacement.ok && std_fs.close(&replacement.value).ok)
 a_text_for_large:[1]u8=[97]
 large_width:i32=0
 check(ttf_measure(large,&a_text_for_large[0],1,&large_width,nil))
 check(large_width==EXPECTED_A)
 ttf_close(large)
 oversized_name:="OVERSIZED_FONT_FILE\x00"
 check(ttf_open(&oversized_name[0],16.0)==nil)
 check(ttf_open(&path[0],0.0)==nil)
 check(ttf_open(&path[0],257.0)==nil)
 a_text: [1]u8=[97]
 a_width:i32=0
 check(ttf_measure(font,&a_text[0],1,&a_width,nil) && a_width==EXPECTED_A)
 renderer := ttf_engine(#cast(rawptr,1))
 check(renderer!=nil)
 bytes: [8]u8 = ['a',0xc3,0xa9,0xf0,0x9f,0x98,0x80,'z']
 text := ttf_create(renderer,font,&bytes[0],8)
 check(text!=nil)
 owned:=#cast(*NativeText,text)
 if mem.arena_capacity(owned.owner)>1048576 || mem.arena_capacity(owned.payload)>1048576 {#panic("text arena startup budget")}
 build_count:=native_build_count
 payload_before:=owned.payload
 check(ttf_set(text,&bytes[0],8) && ttf_set_font(text,font) && ttf_wrap(text,0))
 if native_build_count!=build_count || owned.payload!=payload_before {#panic("unchanged text reshaped")}
 check(tracked_texts==1)
 first_value:[]const u8="a"
 next_value:[]const u8="b"
 check(ttf_set(text,&first_value[0],1) && ttf_set(text,&next_value[0],1))
 warmed_allocations:=native_arena_count
 for iteration in 0..32 {
  check(ttf_set(text,&first_value[0],1) && ttf_set(text,&next_value[0],1))
 }
 if native_arena_count!=warmed_allocations {#panic("small text edits keep allocating owner arenas")}
 check(ttf_set(text,&bytes[0],8))
 measurement_allocations:=native_arena_count
 measurement_builds:=native_build_count
 for iteration in 0..16 {check(ttf_measure(font,&a_text[0],1,&a_width,nil))}
 if native_arena_count!=measurement_allocations {#panic("font measurements keep allocating scratch arenas")}
 if native_build_count!=measurement_builds {#panic("identical font measurement reshaped")}
 bytes[0]='x'
 check(byte_ops.equal(#cast(*NativeText,text).layout.text,"aé😀z"))
 hit := Substring{}
 check(ttf_substring(text,2,&hit) && hit.offset==1 && hit.length==2)
 check(ttf_substring(text,5,&hit) && hit.offset==3 && hit.length==4)
 check(ttf_substring(text,-1,&hit) && hit.offset==0 && hit.length==0 && (hit.flags&256)!=0)
 check(ttf_substring(text,8,&hit) && hit.offset==8 && hit.length==0 && (hit.flags&2048)!=0)
 width:i32=0
 height:i32=0
 check(ttf_size(text,&width,&height) && width>0 && height>0)
 before:=width
 check(ttf_draw(text,2.0,3.0))
 check(!dna_native_text_attach(nil))
 missing_callbacks:=NativeTextCallbacks{}
 check(!dna_native_text_attach(&missing_callbacks))
 check(ttf_draw(text,2.0,3.0))
 invalid: [1]u8=[0xff]
 check(!ttf_set(text,&invalid[0],1))
 check(ttf_size(text,&width,&height) && width==before)
 old_a_width:=a_width
 check(ttf_font_size(font,32.0))
 check(ttf_measure(font,&a_text[0],1,&a_width,nil) && a_width>old_a_width)
 resized_height:=ttf_font_height(font)
 check(resized_height>=first_height*2-1)
 check(ttf_size(text,&width,&height) && width>before)
 multiline := "ab\ncd"
 check(ttf_set(text,&multiline[0],5))
 check(ttf_substring(text,3,&hit) && hit.line==1 && hit.offset==3 && hit.x==0)
 check(ttf_substring(text,2,&hit) && hit.line==0 && hit.offset==2 && hit.length==0)
 check(ttf_at_point(text,100000,0,&hit) && hit.line==0 && hit.offset==2)
 check(ttf_substring(text,3,&hit))
 check(ttf_at_point(text,0,hit.y,&hit) && hit.offset==3)
 check(ttf_at_point(text,100000,100000,&hit) && hit.offset==5 && hit.length==0)
 wrapped := "abc def"
 check(ttf_set(text,&wrapped[0],7))
 check(ttf_wrap(text,30))
 check(ttf_size(text,&width,&height) && height>native_line(#cast(*NativeFont,font)))
 check(ttf_wrap(text,0))
 decomposed := "e\xcc\x81"
 check(ttf_set(text,&decomposed[0],3))
 check(ttf_substring(text,1,&hit) && hit.offset==0 && hit.length==3)
 owned_text:=#cast(*NativeText,text).layout.text
 check(ttf_set(text,&owned_text[0],3))
 check(byte_ops.equal(#cast(*NativeText,text).layout.text,decomposed))
 check(ttf_whitespace_visible(text,true) && !ttf_whitespace_visible(text,false))
 fallback:=ttf_open(&path[0],16.0)
 check(fallback!=nil)
 check(ttf_add_fallback(font,fallback) && ttf_add_fallback(font,fallback))
 check(#cast(*NativeFont,font).fallback_count==1)
 fallback_measurements:=native_build_count
 check(ttf_measure(font,&a_text[0],1,&a_width,nil))
 check(native_build_count==fallback_measurements+1)
 check(ttf_font_size(fallback,20.0))
 check(ttf_measure(font,&a_text[0],1,&a_width,nil))
 check(native_build_count==fallback_measurements+2)
 ttf_remove_fallback(font,fallback)
 check(#cast(*NativeFont,font).fallback_count==0)
 ttf_close(fallback)
 ttf_line_skip(font,50)
 check(ttf_font_height(font)==resized_height)
 spaced := "a\nb"
 check(ttf_set(text,&spaced[0],3))
 check(ttf_substring(text,2,&hit) && hit.y==50 && hit.height==50)
 // A large one-off layout/measurement must not remain as reusable scratch.
 large_memory:=mem.arena_create(65536)
 large_bytes:=mem.push_bytes_uninit(large_memory,20000)
 for index in 0..#len(large_bytes) {large_bytes[index]=120}
 check(ttf_set(text,&large_bytes[0],#len(large_bytes)))
 check(ttf_measure(font,&large_bytes[0],#len(large_bytes),&a_width,nil))
 check(real_font.measure.backing<=65536)
 check(ttf_set(text,&a_text[0],1))
 check(owned.spare==nil || owned.spare.backing<=65536)
 mem.arena_release(large_memory)
 ttf_destroy(text)
 check(tracked_texts==0)
 OTHER_FORMATS
 ttf_close(font)
 check(native_libraries.fonts==0)
 quit()
 check(native_libraries.harfbuzz==nil && native_libraries.bidi==nil)
 check(init())
 remaining:=ttf_open(&path[0],16.0)
 check(remaining!=nil)
 quit()
 check(native_libraries.harfbuzz!=nil && native_libraries.closing && !init())
 ttf_close(remaining)
 check(native_libraries.harfbuzz==nil && native_libraries.bidi==nil)
}
'''
PLATFORM = r'''pub fn native_color(renderer:rawptr,r,g,b,a:u8) bool { return renderer!=nil }
pub fn native_fill(renderer:rawptr,x,y,w,h:f32) bool { return renderer!=nil }
pub fn native_text_cached_bitmap(renderer:rawptr,key:u64,pixels:*const u8,width,height:i32,x,y:f32,r,g,b,a:u8) bool {
 return renderer!=nil && pixels!=nil && width>0 && height>0 && x==x && y==y && r==255 && g==255 && b==255 && a==255
}
'''
font_candidates = [os.environ.get('DNA_FONT',''), '/usr/share/fonts/TTF/DejaVuSansMono.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf']
font = next((Path(x) for x in font_candidates if x and Path(x).is_file()),None)
if font is None:
    raise SystemExit('Native text tests require DNA_FONT or DejaVuSansMono.ttf')

def advance_a(path):
    data=path.read_bytes()
    u16=lambda at: struct.unpack_from('>H',data,at)[0]
    u32=lambda at: struct.unpack_from('>I',data,at)[0]
    tables={data[12+16*i:16+16*i]:u32(20+16*i) for i in range(u16(4))}
    cmap=tables[b'cmap']
    selected=None
    for i in range(u16(cmap+2)):
        record=cmap+4+8*i
        platform,encoding=u16(record),u16(record+2)
        sub=cmap+u32(record+4)
        if (platform==0 or platform==3 and encoding in (1,10)) and u16(sub) in (4,12):
            selected=sub
            if u16(sub)==12: break
    assert selected is not None
    index=0
    if u16(selected)==12:
        for i in range(u32(selected+12)):
            at=selected+16+12*i
            if u32(at)<=97<=u32(at+4): index=u32(at+8)+97-u32(at);break
    else:
        n=u16(selected+6)//2
        for i in range(n):
            end=u16(selected+14+2*i);start=u16(selected+16+2*n+2*i)
            if start<=97<=end:
                delta=u16(selected+16+4*n+2*i);at=selected+16+6*n+2*i;skip=u16(at)
                index=97 if not skip else u16(at+skip+2*(97-start))
                if index: index=(index+delta)&65535
                break
    count=u16(tables[b'hhea']+34)
    advance=u16(tables[b'hmtx']+4*min(index,count-1))
    units=u16(tables[b'head']+18)
    return (advance*16+units-1)//units
expected_a=advance_a(font)
with tempfile.TemporaryDirectory(prefix='dna-native-text-') as directory:
    work=Path(directory)
    module=work
    platform=work/'platform';platform.mkdir()
    (platform/'platform.dyn').write_text(PLATFORM)
    shutil.copyfile(font,work/'font.ttf')
    (work/'large.ttf').write_bytes(font.read_bytes()+bytes(4*1024*1024))
    SOURCE=SOURCE.replace('LARGE_FONT_FILE',str(work/'large.ttf'))
    with (work/'oversized.ttf').open('wb') as output:output.truncate(67108865)
    SOURCE=SOURCE.replace('OVERSIZED_FONT_FILE',str(work/'oversized.ttf'))
    backend=(ROOT/'src/text/native.dyn').read_text().replace('use "../platform" sdl','use "./platform" sdl')
    backend=re.sub(r'extern fn native_text_attach[^\n]+','fn native_text_attach(callbacks:*const NativeTextCallbacks) bool { return dna_native_text_attach(callbacks) }',backend)
    backend=re.sub(r'extern fn native_tracked_create[^\n]+','fn native_tracked_create(engine:rawptr,font:rawptr,text:*const u8,length:usize) rawptr { return dna_text_create(engine,font,text,length) }',backend)
    backend=re.sub(r'extern fn native_tracked_destroy[^\n]+','fn native_tracked_destroy(text:rawptr) { dna_text_destroy(text) }',backend)
    bridge=(ROOT/'src/native/dyn/memory_text.dyn').read_text()
    bridge=bridge[bridge.index('native_text_callbacks:'):]
    (module/'bridge.dyn').write_text(bridge+'\ntracked_texts:usize\nfn memory_active() bool { return true }\nfn memory_record(category:u32,size:usize,lifetime:u64,release:bool) { if release { tracked_texts-=1 } else { tracked_texts+=1 } }\n')
    backend=backend.replace('fn native_build(', 'fn native_build_actual(',1)
    backend=backend.replace('mem.arena_create(', 'native_probe_arena_create(')
    backend+='''\nnative_arena_count:usize
fn native_probe_arena_create(capacity:usize)*mem.Arena {native_arena_count+=1
 return mem.arena_create(capacity)}
native_build_count:usize
fn native_build(arena:*mem.Arena,font:*NativeFont,text:[]const u8,wrap:i32)text_layout.Result {
 native_build_count+=1
 return native_build_actual(arena,font,text,wrap)
}
'''
    (module/'text.dyn').write_text(backend)
    # A one-face collection exercises the FreeType fallback with the same data.
    original=bytearray(font.read_bytes())
    for index in range(struct.unpack_from('>H',original,4)[0]):
        at=12+16*index+8
        struct.pack_into('>I',original,at,struct.unpack_from('>I',original,at)[0]+16)
    collection=work/'font.ttc'
    collection.write_bytes(b'ttcf'+struct.pack('>III',0x10000,1,16)+original)
    formats=[collection]
    cff=next((Path(x) for x in [os.environ.get('DNA_CFF_FONT',''),'/usr/share/fonts/gsfonts/NimbusMonoPS-Regular.otf','/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Regular.otf'] if x and Path(x).is_file()),None)
    if cff is not None:formats.append(cff)
    else:print('SKIP native CFF font: set DNA_CFF_FONT to an OpenType CFF face')
    other=[]
    for path in formats:
        other.append('''if true {
 format_name:[4096]u8=[]
 format_path:[]const u8="'''+str(path)+'''"
 _=mem.copy(format_name[..#len(format_path)],format_path)
 format_font:=ttf_open(&format_name[0],16.0)
 check(format_font!=nil && #cast(*NativeFont,format_font).freetype.face!=nil)
 sample:="abc"
 format_text:=ttf_create(renderer,format_font,&sample[0],3)
 check(format_text!=nil && ttf_draw(format_text,0.0,0.0))
 original_width:i32=0
 larger_width:i32=0
 check(ttf_size(format_text,&original_width,nil) && original_width>0)
 check(ttf_font_size(format_font,32.0) && ttf_size(format_text,&larger_width,nil) && larger_width>original_width)
 check(ttf_draw(format_text,0.0,0.0))
 ttf_destroy(format_text)
 ttf_close(format_font)
 check(tracked_texts==0 && native_libraries.fonts==1)
}''')
    source=SOURCE.replace('FONT_PATH',str(work/'font.ttf')).replace('EXPECTED_A',str(expected_a)).replace('OTHER_FORMATS','\n'.join(other))
    import re
    count=[0]
    def numbered(match):
        count[0]+=1
        return 'check_'+str(count[0])+'('
    source=re.sub(r'\bcheck\(',numbered,source)
    definitions='\n'.join('fn check_'+str(i)+'(ok:bool) { if !ok { #panic("native text contract '+str(i)+'") } }' for i in range(2,count[0]+1))
    (module/'main.dyn').write_text(source+'\n'+definitions)
    for flags in (['--debug'],['--release']):
        output=work/'test'
        subprocess.run([DYN,'build',str(module),*flags,'--quiet','--output',str(output)],check=True,timeout=180)
        (work/'large.ttf').write_bytes(font.read_bytes()+bytes(4*1024*1024))
        subprocess.run([str(output)],check=True,timeout=60)
    for target in ('x86_64-linux','aarch64-linux','riscv64-linux','x86_64-macos','aarch64-macos','x86_64-windows','aarch64-windows'):
        subprocess.run([DYN,'build',str(module),'--release','--target',target,'--no-link','--emit-object','--quiet','--output',str(work/(target+'.o'))],check=True,timeout=180)
print('PASS native Dyn text: owned UTF8, byte-range/point queries, multiline/wrap, metrics revision, fallback lifetime, draw callback, TTC/CFF fallback and library lifetime (debug/release; seven desktop object targets)')
