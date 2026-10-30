#!/usr/bin/env python3
"""Selection adapters: native visual unions and linear TUI cells."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import shlex
import struct
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
SDK=ROOT.parent/'dyn/compiler'
DYN=str(Path(os.environ.get('DYN',SDK/'build/dyn-release')).resolve())
# Independent HarfBuzz/FriBidi oracle, adapted from Dyn (MIT).
C_ORACLE=r'''/* Independent HarfBuzz/FriBidi oracle, adapted from Dyn (MIT). */
#include <hb.h>
#include <hb-ot.h>
#include <fribidi.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void u(FILE*f,uint32_t n){for(int i=0;i<4;i++)fputc((n>>(i*8))&255,f);}
struct Run {int start,end,first,last,level,fallback;hb_script_t script;hb_glyph_info_t *infos;hb_glyph_position_t *positions;unsigned count;};
int main(int argc,char**argv){
 if(argc!=4&&argc!=5)return 2;int fallback_mode=argc==5;FILE*font_file=fopen(argv[1],"rb");if(!font_file)return 3;fseek(font_file,0,SEEK_END);long size=ftell(font_file);rewind(font_file);char*data=malloc(size);if(fread(data,1,size,font_file)!=(size_t)size)return 4;fclose(font_file);
 hb_blob_t*blob=hb_blob_create(data,size,HB_MEMORY_MODE_DUPLICATE,NULL,NULL);hb_face_t*face=hb_face_create(blob,0);hb_font_t*font=hb_font_create(face);hb_ot_font_set_funcs(font);hb_font_set_scale(font,2048,2048);hb_font_t*other=hb_font_create(face);hb_ot_font_set_funcs(other);hb_font_set_scale(other,2048,2048);
 FILE*input=fopen(argv[2],"rb");fseek(input,0,SEEK_END);long length=ftell(input);rewind(input);char*text=calloc(length+1,1);if(fread(text,1,length,input)!=(size_t)length)return 5;fclose(input);
 FriBidiChar*cp=calloc(length+1,sizeof(*cp));int n=fribidi_charset_to_unicode(FRIBIDI_CHAR_SET_UTF8,text,length,cp);int*starts=calloc(n+1,sizeof(int));int at=0;for(int i=0;i<n;i++){starts[i]=at;unsigned c=(unsigned char)text[at++];while(c>=0xc0 && at<length && ((unsigned char)text[at]&0xc0)==0x80)at++;}starts[n]=length;
 FriBidiLevel*levels=calloc(n+1,sizeof(*levels));FriBidiCharType*types=calloc(n+1,sizeof(*types));FriBidiParType base=FRIBIDI_PAR_ON;fribidi_get_bidi_types(cp,n,types);if(n&&!fribidi_log2vis(cp,n,&base,NULL,NULL,NULL,levels))return 6;
 FriBidiStrIndex*map=calloc(n+1,sizeof(*map));for(int i=0;i<n;i++)map[i]=i;if(n&&!fribidi_reorder_line(0,types,n,0,base,levels,NULL,map))return 7;
 hb_script_t*scripts=calloc(n+1,sizeof(*scripts));hb_script_t previous=HB_SCRIPT_INVALID;for(int i=0;i<n;i++){hb_script_t s=hb_unicode_script(hb_unicode_funcs_get_default(),cp[i]);if(s!=HB_SCRIPT_COMMON && s!=HB_SCRIPT_INHERITED && s!=HB_SCRIPT_INVALID)previous=s;else s=previous;scripts[i]=s;}hb_script_t next=HB_SCRIPT_INVALID;for(int i=n-1;i>=0;i--){if(scripts[i]!=HB_SCRIPT_INVALID && scripts[i]!=HB_SCRIPT_COMMON && scripts[i]!=HB_SCRIPT_INHERITED)next=scripts[i];else scripts[i]=next;}
 struct Run*runs=calloc(n+1,sizeof(*runs));int nr=0;for(int i=0;i<n;){struct Run*r=&runs[nr++];r->first=i;r->start=starts[i];r->level=levels[i];r->script=scripts[i];r->fallback=fallback_mode&&cp[i]==1580;i++;while(i<n && (fallback_mode&&cp[i]==1580)==r->fallback && cp[i]!=9 && cp[r->first]!=9 && levels[i]==r->level && scripts[i]==r->script)i++;r->last=i;r->end=starts[i];if(cp[r->first]==9)continue;hb_buffer_t*b=hb_buffer_create();hb_buffer_add_utf8(b,text,length,r->start,r->end-r->start);hb_buffer_set_direction(b,r->level&1?HB_DIRECTION_RTL:HB_DIRECTION_LTR);hb_buffer_set_script(b,r->script);hb_buffer_set_cluster_level(b,HB_BUFFER_CLUSTER_LEVEL_MONOTONE_GRAPHEMES);hb_buffer_set_flags(b,(r->first==0?HB_BUFFER_FLAG_BOT:0)|(r->last==n?HB_BUFFER_FLAG_EOT:0));hb_buffer_guess_segment_properties(b);hb_shape(r->fallback?other:font,b,NULL,0);unsigned count=0;hb_glyph_info_t*infos=hb_buffer_get_glyph_infos(b,&count);hb_glyph_position_t*pos=hb_buffer_get_glyph_positions(b,&count);r->count=count;r->infos=malloc(count*sizeof(*infos));r->positions=malloc(count*sizeof(*pos));memcpy(r->infos,infos,count*sizeof(*infos));for(unsigned k=0;k<count;k++)r->infos[k].cluster-=r->start;memcpy(r->positions,pos,count*sizeof(*pos));hb_buffer_destroy(b);}
 int*order=calloc(nr+1,sizeof(int));int*seen=calloc(nr+1,sizeof(int));int used=0;for(int i=0;i<n;i++)for(int r=0;r<nr;r++)if(!seen[r]&&map[i]>=runs[r].first&&map[i]<runs[r].last){seen[r]=1;order[used++]=r;break;}
 unsigned total=0;for(int r=0;r<nr;r++)total+=cp[runs[r].first]==9?1:runs[r].count;FILE*out=fopen(argv[3],"wb");u(out,total);int x=0;for(int o=0;o<used;o++){struct Run*r=&runs[order[o]];if(cp[r->first]==9){int tab=2604;int advance=(x/tab+1)*tab-x;u(out,0);u(out,r->start);u(out,r->end);u(out,x);u(out,0);u(out,0);u(out,0);u(out,advance);x+=advance;continue;}unsigned i=0;int previous_end=r->end;while(i<r->count){unsigned next=i+1;while(next<r->count&&r->infos[next].cluster==r->infos[i].cluster)next++;int start=r->start+r->infos[i].cluster;int end=(r->level&1)?previous_end:next<r->count?r->start+r->infos[next].cluster:r->end;for(unsigned j=i;j<next;j++){u(out,r->infos[j].codepoint);u(out,start);u(out,end);u(out,x);u(out,0);u(out,r->positions[j].x_offset);u(out,-r->positions[j].y_offset);u(out,r->positions[j].x_advance);x+=r->positions[j].x_advance;}previous_end=start;i=next;}}
 fclose(out);hb_font_destroy(other);hb_font_destroy(font);hb_face_destroy(face);hb_blob_destroy(blob);free(data);return 0;
}
'''
SUBSTRING='pub struct Substring {flags:u32,offset:i32,length:i32,line:i32,cluster:i32,x:i32,y:i32,width:i32,height:i32}\n'
PLATFORM=r'''pub fn native_color(renderer:rawptr,r,g,b,a:u8)bool{return renderer!=nil}
pub fn native_fill(renderer:rawptr,x,y,w,h:f32)bool{return renderer!=nil}
pub fn native_text_bitmap(renderer:rawptr,pixels:*const u8,width,height:i32,x,y:f32,r,g,b,a:u8)bool{return renderer!=nil}
'''
NATIVE=r'''fn check(ok:bool){if !ok{#panic("native selection adapter")}}
struct Captured {regions:[64]Substring,count:usize,stop:bool}
fn capture(data:rawptr,region:*const Substring)bool {
 result:=#cast(*Captured,data)
 check(result.count<64)
 result.regions[result.count]=region.*
 result.count+=1
 return !result.stop
}
fn main(){
 check(init())
 defer quit()
 path: [4096]u8=[]
 name:="FONT_PATH"
 _=mem.copy(path[..#len(name)],name)
 font:=ttf_open(&path[0],32.0)
 check(font!=nil)
 defer ttf_close(font)
 renderer:=ttf_engine(#cast(rawptr,1))
 check(renderer!=nil)
 CASES
 if true {
  source:="aéz"
  text:=ttf_create(renderer,font,&source[0],#len(source))
  check(text!=nil)
  recorded:=Captured{}
  check(!ttf_selection(text,2,3,capture,&recorded) && recorded.count==0)
  check(!ttf_selection(text,0,2,capture,&recorded) && recorded.count==0)
  check(!ttf_selection(text,4,3,capture,&recorded) && recorded.count==0)
  check(!ttf_selection(text,0,5,capture,&recorded) && recorded.count==0)
  check(!ttf_selection(text,0,1,nil,&recorded) && recorded.count==0)
  check(ttf_selection(text,1,1,capture,&recorded) && recorded.count==0)
  recorded.stop=true
  check(!ttf_selection(text,0,4,capture,&recorded) && recorded.count==1)
  recorded=Captured{}
  check(ttf_selection(text,0,4,capture,&recorded) && recorded.count==1)
  ttf_destroy(text)
 }
 if true {
  source:="ab\n\nאב"
  text:=ttf_create(renderer,font,&source[0],#len(source))
  check(text!=nil)
  recorded:=Captured{}
  check(ttf_selection(text,0,#len(source),capture,&recorded) && recorded.count==2)
  check(recorded.regions[0].line==0 && recorded.regions[1].line==2 && recorded.regions[1].y>recorded.regions[0].y)
  recorded=Captured{}
  check(ttf_selection(text,2,4,capture,&recorded) && recorded.count==0)
  ttf_destroy(text)
 }
 if true {
  source:="ab"
  handle:=ttf_create(renderer,font,&source[0],2)
  check(handle!=nil)
  text:=#cast(*NativeText,handle)
  check(#len(text.layout.glyphs)==2)
  text.layout.glyphs[0].x= -2147483647.0
  text.layout.glyphs[0].advance=2147483647.0
  text.layout.glyphs[1].x=0.0
  text.layout.glyphs[1].advance=2147483647.0
  recorded:=Captured{}
  check(!ttf_selection(handle,0,2,capture,&recorded) && recorded.count==0)
  ttf_destroy(handle)
 }
}
'''
TUI=r'''use "./text" text
use "./platform" sdl
fn check(ok:bool){if !ok{#panic("TUI selection geometry")}}
struct Captured {count:usize,width:i32,first:i32,last:i32,stop:bool}
fn capture(data:rawptr,region:*const text.Substring)bool {
 result:=#cast(*Captured,data)
 if result.count==0 {result.first=region.x}
 result.last=region.x+region.width
 result.width+=region.width
 result.count+=1
 check(region.height==16 && region.width>0)
 return !result.stop
}
fn main(){
 sdl.selection_probe_active()
 handle:=text.create(#cast(rawptr,1),#cast(rawptr,1),nil,0)
 check(handle!=nil)
 defer text.destroy(handle)
 source:="a\xcc\x81\t中z"
 check(text.set(handle,&source[0],#len(source)))
 result:=Captured{}
 check(text.selection(handle,1,3,capture,&result) && result.count==1 && result.width==8 && result.first==0)
 result=Captured{}
 check(text.selection(handle,3,4,capture,&result) && result.count==1 && result.width==24 && result.first==8 && result.last==32)
 result=Captured{}
 check(text.selection(handle,4,7,capture,&result) && result.count==1 && result.width==16 && result.first==32)
 result=Captured{}
 check(!text.selection(handle,2,3,capture,&result) && result.count==0)
 check(!text.selection(handle,0,5,capture,&result) && result.count==0)
 check(!text.selection(handle,0,99,capture,&result) && result.count==0)
 check(text.selection(handle,7,7,capture,&result) && result.count==0)
 result.stop=true
 check(!text.selection(handle,0,#len(source),capture,&result) && result.count==1)
 // A long selected line walks cells once rather than querying each prefix.
 owner:=mem.arena_create(0)
 defer mem.arena_release(owner)
 bytes:=mem.push_bytes_uninit(owner,20000)
 for i in 0..#len(bytes) {bytes[i]=97}
 check(text.set(handle,&bytes[0],#len(bytes)))
 result=Captured{}
 check(text.selection(handle,0,#len(bytes),capture,&result) && result.count==20000 && result.width==160000)
}
'''
def literal(data): return '"'+''.join(f'\\x{x:02x}' for x in data)+'"'
def union(records,start,end):
    if start==end:return []
    groups={}
    for _,low,high,x,_,_,_,advance in records:
        a,b=sorted((x,x+advance));key=(low,high)
        groups[key]=(min(a,groups.get(key,(a,b))[0]),max(b,groups.get(key,(a,b))[1]))
    result=[]
    for a,b,low,high in sorted((a,b,low,high) for (low,high),(a,b) in groups.items() if low<end and high>start and a<b):
        if result and a<=result[-1][1]:
            old=result[-1];result[-1]=(old[0],max(old[1],b),min(old[2],low),max(old[3],high))
        else:result.append((a,b,low,high))
    return result

def visual_regions(cells,start,end):
    result=[];pending=None
    for index,cell in sorted(enumerate(cells),key=lambda item:(item[1][2],item[1][3],item[0])):
        offset,length,line,x,y,width,height=cell
        selected=offset<end and offset+length>start
        if pending and (not selected or line!=pending[2]):
            result.append(pending);pending=None
        if not selected or width<=0 or height<=0:continue
        if pending is None:pending=list(cell)
        else:
            old_offset,old_length,_,old_x,old_y,old_width,old_height=pending
            low=min(old_offset,offset);high=max(old_offset+old_length,offset+length)
            left=min(old_x,x);top=min(old_y,y);right=max(old_x+old_width,x+width);bottom=max(old_y+old_height,y+height)
            pending=[low,high-low,line,left,top,right-left,bottom-top]
    if pending:result.append(pending)
    return result

def run_fixture(stage,environment,flags=('--debug','--release')):
    for flag in flags:
        output=stage/'test'
        subprocess.run([DYN,'build',str(stage),flag,'--quiet','--output',str(output)],env=environment,check=True,timeout=180)
        subprocess.run([str(output)],env=environment,check=True,timeout=30)
font=next((p for p in [Path('/usr/share/fonts/TTF/DejaVuSans.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists()),None)
if font is None:raise SystemExit('Selection adapter oracle requires DejaVuSans.ttf')
with tempfile.TemporaryDirectory(prefix='dna-selection-') as directory:
    work=Path(directory)
    # Generate expected visual cell unions only from the independent C glyph oracle.
    (work/'oracle.c').write_text(C_ORACLE)
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','harfbuzz','fribidi'],text=True))
    subprocess.run(['cc','-std=c11','-O2',str(work/'oracle.c'),*flags,'-o',str(work/'oracle')],check=True)
    stage=work/'native';stage.mkdir();(stage/'platform').mkdir();(stage/'platform/platform.dyn').write_text(PLATFORM)
    backend=(ROOT/'src/text/native.dyn').read_text().replace('use "../platform" sdl','use "./platform" sdl')
    backend=re.sub(r'extern fn native_text_attach[^\n]+','fn native_text_attach(callbacks:*const NativeTextCallbacks)bool{return dna_native_text_attach(callbacks)}',backend)
    backend=re.sub(r'extern fn native_tracked_create[^\n]+','fn native_tracked_create(engine:rawptr,font:rawptr,text:*const u8,length:usize)rawptr{return dna_text_create(engine,font,text,length)}',backend)
    backend=re.sub(r'extern fn native_tracked_destroy[^\n]+','fn native_tracked_destroy(text:rawptr){dna_text_destroy(text)}',backend)
    bridge=(ROOT/'src/native/dyn/memory_text.dyn').read_text();bridge=bridge[bridge.index('native_text_callbacks:'):]
    (stage/'bridge.dyn').write_text(bridge+'\nfn memory_active()bool{return false}\nfn memory_record(category:u32,size:usize,lifetime:u64,release:bool){}\n')
    (stage/'text.dyn').write_text(backend)
    cases=[]
    for index,source in enumerate(['office AV','abc אבג xyz','אבג 123, abc!','abc سلام 123 (xyz)','e\u0301 שָׁלוֹם','A\tאבג\tB']):
        path=work/f'source-{index}';path.write_text(source,encoding='utf-8');output=work/f'records-{index}'
        subprocess.run([str(work/'oracle'),str(font),str(path),str(output)],check=True)
        records=output.read_bytes();records=[struct.unpack('<8i',records[i:i+32]) for i in range(4,len(records),32)]
        data=source.encode();offsets=[0]
        for char in source:offsets.append(offsets[-1]+len(char.encode()))
        lines=[f'if true {{ source:[]const u8={literal(data)}','handle:=ttf_create(renderer,font,&source[0],#len(source))','check(handle!=nil)']
        for start in offsets:
            for end in offsets:
                if end<start:continue
                expected=union(records,start,end)
                lines+=['if true { received:=Captured{}',f'check(ttf_selection(handle,{start},{end},capture,&received) && received.count=={len(expected)})']
                for i,(a,b,low,high) in enumerate(expected):
                    left=(a+32)//64;right=(b+32)//64
                    lines+=[f'check(received.regions[{i}].x=={left} && received.regions[{i}].width=={right-left} && received.regions[{i}].offset=={low} && received.regions[{i}].length=={high-low} && received.regions[{i}].line==0 && received.regions[{i}].y==0 && received.regions[{i}].height>0)']
                lines+=['}']
        lines+=['ttf_destroy(handle)','}'];cases.append('\n'.join(lines))
    source=SUBSTRING+NATIVE.replace('FONT_PATH',str(font)).replace('CASES','\n'.join(cases))
    counter=[0]
    def number(match):counter[0]+=1;return 'check_'+str(counter[0])+'('
    source=re.sub(r'\bcheck\(',number,source)
    definitions='\n'.join('fn check_'+str(i)+'(ok:bool){if !ok{#panic("native selection adapter '+str(i)+'")}}' for i in range(2,counter[0]+1))
    (stage/'main.dyn').write_text(source+'\n'+definitions)
    run_fixture(stage,dict(os.environ))
    # Real TUI layout functions run without changing the terminal or opening a GUI.
    stage=work/'tui';stage.mkdir()
    for name in ['platform','text','host','cstring','owned_arena']:shutil.copytree(ROOT/'src'/name,stage/name)
    shutil.copyfile(ROOT/'modules/stubs/platform_gui.dyn',stage/'platform/gui.dyn')
    shutil.copyfile(ROOT/'modules/stubs/text_native.dyn',stage/'text/native.dyn')
    shutil.rmtree(stage/'platform/native_present')
    shutil.rmtree(stage/'platform/backend')
    with (stage/'platform/tui.dyn').open('a') as stream:stream.write('\npub fn selection_probe_active(){state.active=true}\n')
    (stage/'main.dyn').write_text('use "std/mem"\n'+TUI)
    native=ROOT/'build/deps/install/lib'
    if not (native/'libdna_native.so').exists():raise SystemExit('Run just deps before TUI selection adapter oracle')
    run_fixture(stage,dict(os.environ,DYN_LIBRARY_PATH=str(native),LD_LIBRARY_PATH=str(native)))
print('PASS selection adapters: C-derived native visual unions, partial clusters, callback cancellation, bounds and linear TUI cells (debug/release)')
