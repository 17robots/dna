#!/usr/bin/env python3
"""Compare native text's actual shaped IDs/positions with independent HarfBuzz C."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
DYN=str(Path(os.environ.get('DYN',ROOT.parent/'dyn/compiler/build/dyn-release')).resolve())
C=r'''#include <hb.h>
#include <hb-ot.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char**argv){
 if(argc!=3)return 2;
 hb_blob_t*b=hb_blob_create_from_file_or_fail(argv[1]);if(!b)return 3;
 hb_face_t*f=hb_face_create(b,0);hb_font_t*font=hb_font_create(f);hb_ot_font_set_funcs(font);hb_font_set_scale(font,1024,1024);hb_font_set_ppem(font,16,16);
 hb_buffer_t*buffer=hb_buffer_create();hb_buffer_add_utf8(buffer,argv[2],-1,0,-1);hb_buffer_guess_segment_properties(buffer);hb_shape(font,buffer,NULL,0);
 unsigned n=0;hb_glyph_info_t*infos=hb_buffer_get_glyph_infos(buffer,&n);hb_glyph_position_t*p=hb_buffer_get_glyph_positions(buffer,&n);
 for(unsigned i=0;i<n;i++)printf("%u %u %d %d %d\n",infos[i].codepoint,infos[i].cluster,p[i].x_advance,p[i].x_offset,p[i].y_offset);
 hb_buffer_destroy(buffer);hb_font_destroy(font);hb_face_destroy(f);hb_blob_destroy(b);return 0;
}
'''
PLATFORM=r'''pub fn native_color(renderer:rawptr,r,g,b,a:u8)bool{return renderer!=nil}
pub fn native_fill(renderer:rawptr,x,y,w,h:f32)bool{return renderer!=nil}
pub fn native_text_cached_bitmap(renderer:rawptr,key:u64,pixels:*const u8,width,height:i32,x,y:f32,r,g,b,a:u8)bool{return renderer!=nil && pixels!=nil && width>0 && height>0}
'''
SOURCE=r'''pub struct Substring {flags:u32,offset:i32,length:i32,line:i32,cluster:i32,x:i32,y:i32,width:i32,height:i32}
fn check(ok:bool){if !ok{#panic("native shaping oracle")}}
fn close_enough(a,b:f64)bool{return a-b<0.0001 && b-a<0.0001}
fn main(){
 check(init())
 defer quit()
 name: [4096]u8=[]
 path: []const u8="FONT_PATH"
 _=mem.copy(name[..#len(path)],path)
 font:=ttf_open(&name[0],16.0)
 check(font!=nil)
 defer ttf_close(font)
 renderer:=ttf_engine(#cast(rawptr,1))
 check(renderer!=nil)
 FIXTURES
}
'''
def literal(data):
    return '"'+''.join(f'\\x{byte:02x}' for byte in data)+'"'
font=next((Path(x) for x in [os.environ.get('DNA_SHAPING_FONT',''),'/usr/share/fonts/TTF/DejaVuSans.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'] if x and Path(x).is_file()),None)
if font is None:raise SystemExit('Native shaping oracle requires DejaVuSans.ttf or DNA_SHAPING_FONT')
if not shutil.which('cc') or not shutil.which('pkg-config'):raise SystemExit('Native shaping oracle requires C compiler and HarfBuzz development headers')
with tempfile.TemporaryDirectory(prefix='dna-shaping-') as directory:
    work=Path(directory)
    (work/'oracle.c').write_text(C)
    flags=subprocess.check_output(['pkg-config','--cflags','--libs','harfbuzz'],text=True).split()
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(work/'oracle.c'),*flags,'-o',str(work/'oracle')],check=True)
    platform=work/'platform';platform.mkdir();(platform/'platform.dyn').write_text(PLATFORM)
    backend=(ROOT/'src/text/native.dyn').read_text().replace('use "../platform" sdl','use "./platform" sdl')
    backend=re.sub(r'extern fn native_text_attach[^\n]+','fn native_text_attach(callbacks:*const NativeTextCallbacks)bool{return dna_native_text_attach(callbacks)}',backend)
    backend=re.sub(r'extern fn native_tracked_create[^\n]+','fn native_tracked_create(engine:rawptr,font:rawptr,text:*const u8,length:usize)rawptr{return dna_text_create(engine,font,text,length)}',backend)
    backend=re.sub(r'extern fn native_tracked_destroy[^\n]+','fn native_tracked_destroy(text:rawptr){dna_text_destroy(text)}',backend)
    bridge=(ROOT/'src/native/dyn/memory_text.dyn').read_text();bridge=bridge[bridge.index('native_text_callbacks:'):]
    (work/'bridge.dyn').write_text(bridge+'\nfn memory_active()bool{return false}\nfn memory_record(category:u32,size:usize,lifetime:u64,release:bool){}\n')
    (work/'text.dyn').write_text(backend)
    cases=[]
    for index,text in enumerate(['office','سلام','שָׁלוֹם','e\u0301','कर्म']):
        rows=[list(map(int,line.split())) for line in subprocess.check_output([str(work/'oracle'),str(font),text],text=True).splitlines()]
        data=text.encode();clusters=sorted(set(row[1] for row in rows))+[len(data)]
        lines=[f'if true {{ source:[]const u8={literal(data)}', 'handle:=ttf_create(renderer,font,&source[0],#len(source))','check(handle!=nil)','text:=#cast(*NativeText,handle)',f'check(#len(text.layout.glyphs)=={len(rows)})']
        x=0
        for i,(glyph,cluster,advance,xoff,yoff) in enumerate(rows):
            end=clusters[clusters.index(cluster)+1]
            if text=='कर्म' and cluster>=3:
                cluster,end=3,len(data)  # UAX29 conjunct grapheme, even without font coverage.
            lines += [f'check(text.layout.glyphs[{i}].id=={glyph} && text.layout.glyphs[{i}].start=={cluster} && text.layout.glyphs[{i}].end=={end})',f'check(close_enough(text.layout.glyphs[{i}].x,{x/64:.8f}) && close_enough(text.layout.glyphs[{i}].advance,{advance/64:.8f}) && close_enough(text.layout.glyphs[{i}].x_offset,{xoff/64:.8f}) && close_enough(text.layout.glyphs[{i}].y_offset,{-yoff/64:.8f}))']
            x+=advance
        lines+=['check(ttf_draw(handle,0.0,0.0))','ttf_destroy(handle)','}']
        cases.append('\n'.join(lines))
    cases.append(r'''if true {
 source:="office"
 handle:=ttf_create(renderer,font,&source[0],6)
 check(handle!=nil)
 first:=Substring{}
 second:=Substring{}
 third:=Substring{}
 check(ttf_substring(handle,1,&first) && ttf_substring(handle,2,&second) && ttf_substring(handle,3,&third))
 // Every interior ffi byte returns the same source cluster.
 check(first.offset==1 && first.length==3 && second.offset==1 && second.length==3 && third.offset==1 && third.length==3)
 check(first.x==second.x && first.x==third.x && (first.flags&255)==4)
 check(ttf_at_point(handle,first.x+first.width/2,0,&second) && second.offset==1 && second.length==3)
 check(ttf_substring(handle,4,&second) && second.x>first.x)
 ttf_destroy(handle)
}
if true {
 source:="سلام"
 handle:=ttf_create(renderer,font,&source[0],#len(source))
 check(handle!=nil)
 start:=Substring{}
 end:=Substring{}
 check(ttf_substring(handle,0,&start) && ttf_substring(handle,#cast(i32,#len(source)),&end))
 check((start.flags&255)==5 && start.offset==0 && start.x>end.x && end.offset==#cast(i32,#len(source)))
 check(ttf_at_point(handle,-1000,0,&end) && end.offset==#cast(i32,#len(source)) && end.length==0 && (end.flags&255)==5)
 check(ttf_at_point(handle,100000,0,&end) && end.offset==0 && end.length==0 && (end.flags&255)==5)
 check(ttf_at_point(handle,start.x+start.width/2,0,&end) && end.offset==start.offset && end.length==start.length)
 ttf_destroy(handle)
}''')
    source=SOURCE.replace('FONT_PATH',str(font)).replace('FIXTURES','\n'.join(cases))
    counter=[0]
    def numbered(match):
        counter[0]+=1
        return 'check_'+str(counter[0])+'('
    source=re.sub(r'\bcheck\(',numbered,source)
    definitions='\n'.join('fn check_'+str(i)+'(ok:bool){if !ok{#panic("native shaping oracle '+str(i)+'")}}' for i in range(2,counter[0]+1))
    (work/'main.dyn').write_text(source+'\n'+definitions)

    for flags in (['--debug'],['--release']):
        binary=work/'test'
        subprocess.run([DYN,'build',str(work),*flags,'--quiet','--output',str(binary)],check=True,timeout=180)
        subprocess.run([str(binary)],check=True,timeout=60)
print('PASS native shaping: independent C HarfBuzz glyph IDs, byte clusters, advances/offsets and drawing (debug/release)')
