#!/usr/bin/env python3
"""Execute platform storage adapters against deterministic OS seams on Linux."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get('DYN', 'dyn')
FAKE = '''use "std/errors"
pub struct File { descriptor:isize=-1,active,owned:bool }
pub struct Result { transferred:usize,error:isize,kind:errors.Kind,ok:bool }
pub struct OffsetResult { value:usize,error:isize,kind:errors.Kind,ok:bool }
extern fn probe_seek "probe_seek"(file:isize,offset:isize,origin:usize) isize
extern fn probe_read "probe_read"(file:isize,bytes:*u8,length:usize) isize
extern fn probe_write "probe_write"(file:isize,bytes:*const u8,length:usize) isize
extern fn probe_close "probe_close"(file:isize) i32
pub fn seek(file:*File,offset:isize,origin:usize) OffsetResult {
 n:=probe_seek(file.descriptor,offset,origin)
 if n<0 {return OffsetResult{error:n,kind:errors.Kind.System}}
 return OffsetResult{value:#cast(usize,n),ok:true}
}
pub fn read(file:*File,bytes:[]u8) Result {
 n:=probe_read(file.descriptor,&bytes[0],#len(bytes))
 if n<0 {return Result{error:n,kind:errors.Kind.System}}
 return Result{transferred:#cast(usize,n),ok:true}
}
pub fn write(file:*File,bytes:[]const u8) Result {
 n:=probe_write(file.descriptor,&bytes[0],#len(bytes))
 if n<0 {return Result{error:n,kind:errors.Kind.System}}
 return Result{transferred:#cast(usize,n),ok:true}
}
pub fn close(file:*File) Result { _=probe_close(file.descriptor) file.active=false return Result{ok:true} }
'''.replace(') file.active', ')\n file.active').replace('false return', 'false\n return')
BASE = '''#link("c")
use "./fake" std_fs
use "std/errors"
type File=std_fs.File
type Result=std_fs.Result
struct Metadata { size:u64,error:isize,kind:errors.Kind,ok:bool }
fn is_open(file:*const File) bool {return file.active}
fn adopt_handle(value:isize) File {return File{descriptor:value,active:true,owned:true}}
fn close(file:*File) Result {return std_fs.close(file)}
extern fn probe_size "probe_size"() u64
fn file_metadata(file:*const File) Metadata {return Metadata{size:probe_size(),ok:true}}
fn windows_failure(code:u32) Result {return Result{error:0-#cast(isize,code),kind:errors.Kind.System}}
extern fn fs_reopen "ReOpenFile"(file:rawptr,access:u32,share:u32,flags:u32) rawptr
extern fn fs_set_basic "SetFileInformationByHandle"(file:rawptr,kind:u32,data:rawptr,size:u32) i32
extern fn fs_ioctl "DeviceIoControl"(file:rawptr,code:u32,input:rawptr,input_length:u32,output:rawptr,output_length:u32,returned:*u32,overlapped:rawptr) i32
extern fn fs_close "CloseHandle"(file:rawptr) i32
extern fn fs_error "GetLastError"() u32
extern fn probe_reset "probe_reset"(mode:i32)
extern fn probe_check "probe_check"(transferred:usize,ok:bool) i32
'''
SHIM = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define S ((intptr_t)(1ULL<<40)+1)
#define D (S+1)
#define R (S+2)
static unsigned char src[300000], dst[300000], mapped[32];
static size_t pos, readpos, size;
static int mode, clones, closes, reopenings;
void probe_reset(int m) {mode=m;pos=1;readpos=7;size=1;clones=closes=reopenings=0;memset(dst,0,sizeof(dst));dst[0]='Z';for(size_t i=0;i<sizeof(src);i++)src[i]=(unsigned char)(i%251+1);}
uint64_t probe_size(void) {return size;}
intptr_t probe_seek(intptr_t f,intptr_t off,size_t origin) {size_t *p=f==D?&pos:&readpos;assert(f==D||f==R);*p=origin==1?*p+off:(size_t)off;return *p;}
intptr_t probe_read(intptr_t f,void *p,size_t n) {assert(f==R);if(n>sizeof(src)-readpos)n=sizeof(src)-readpos;memcpy(p,src+readpos,n);readpos+=n;return n;}
intptr_t probe_write(intptr_t f,const void *p,size_t n) {assert(f==D);if(mode==3)return -5;assert(pos+n<=sizeof(dst));memcpy(dst+pos,p,n);pos+=n;return n;}
int probe_close(intptr_t f) {assert(f==R);closes++;return 1;}
void *ReOpenFile(void *f,uint32_t access,uint32_t share,uint32_t flags) {assert((intptr_t)f==S&&access==0x80000000&&share==7&&flags==0);reopenings++;return (void*)R;}
int SetFileInformationByHandle(void *f,uint32_t kind,const int64_t *end,uint32_t n) {assert((intptr_t)f==D&&kind==6&&n==8&&*end==200001);size=*end;return 1;}
struct range {void *source;int64_t from,to,length;};
int DeviceIoControl(void *f,uint32_t code,const struct range *r,uint32_t n,void *out,uint32_t outn,uint32_t *returned,void *overlapped) {
 assert((intptr_t)f==D&&code==0x98344&&n==32&&!out&&!outn&&!overlapped);assert((intptr_t)r->source==S&&r->from==65536&&r->to==65536&&r->length==131072);*returned=0;clones++;if(mode==1)return 0;memcpy(dst+r->to,src+r->from,r->length);return 1;
}
uint32_t GetLastError(void) {return 50;}
int probe_check(size_t transferred,_Bool ok) {
 if(mode==0){assert(ok&&transferred==200000&&pos==200001&&clones==1&&closes==1&&reopenings==1);assert(dst[0]=='Z'&&!memcmp(dst+1,src+1,200000));}
 if(mode==1){assert(!ok&&!transferred&&pos==1&&clones==1&&closes==1);}
 if(mode==2){assert(!ok&&!transferred&&pos==1&&!clones&&!reopenings);}
 if(mode==3){assert(!ok&&transferred>=131072&&clones==1&&closes==1);}
 return 1;
}
void *CreateFileMappingW(void *f,void *security,uint32_t protection,uint32_t high,uint32_t low,const uint16_t *name) {assert((intptr_t)f==S&&!security&&protection==2&&high==1&&low==17&&!name);return mode==1?NULL:(void*)123;}
void *MapViewOfFile(void *m,uint32_t access,uint32_t high,uint32_t low,size_t n) {assert(m==(void*)123&&access==4&&!high&&!low&&n==4294967313ULL);return mode==2?NULL:mapped;}
int CloseHandle(void *m) {assert(m==(void*)123);closes++;return 1;}
int UnmapViewOfFile(void *p) {assert(p==mapped);return 1;}
void *probe_mmap(void *p,size_t n,int protection,int flags,int fd,int64_t offset) {assert(!p&&n==4294967313ULL&&protection==1&&flags==(2|0x4000)&&fd==1&&!offset);return mode==1?(void*)-1:mapped;}
int probe_munmap(void *p,size_t n) {assert(p==mapped&&n==4294967313ULL);return 0;}
int probe_mapping_check(_Bool present) {assert(present==(mode==0));return 1;}
'''
with tempfile.TemporaryDirectory(prefix='dna-platform-storage-') as directory:
    stage = Path(directory)
    (stage/'fake').mkdir()
    (stage/'fake/fake.dyn').write_text(FAKE)
    subprocess.run(['cc','-x','c','-c','-o',str(stage/'shim.o'),'-'],input=SHIM,text=True,check=True)
    windows = (ROOT/'src/filesystem/windows.dyn').read_text()
    copy = windows[windows.index('struct WinCloneRange'):windows.index('extern fn fs_mapping')]
    mapping = windows[windows.index('extern fn fs_mapping'):windows.index('pub const WholeFileClones')]
    (stage/'main.dyn').write_text(BASE+copy+mapping+'''
fn main() {
 for mode in 0..4 {
  probe_reset(#cast(i32,mode))
  origin:=adopt_handle(1099511627777)
  target:=adopt_handle(1099511627778)
  offset:u64=1
  if mode==2 {offset=2}
  result:=copy_range(&origin,offset,&target,200000)
  if probe_check(result.transferred,result.ok)!=1 {#panic("range result")}
 }
 for mode in 0..3 {
  probe_reset(#cast(i32,mode))
  mapped:=map_file(1099511627777,4294967313)
  if probe_mapping_check(mapped!=nil)!=1 {#panic("mapping result")}
  if mapped!=nil {unmap_file(mapped,4294967313)}
 }
}
extern fn probe_mapping_check "probe_mapping_check"(present:bool) i32
''')
    for mode in ('debug','release'):
        binary=stage/mode
        subprocess.run([DYN,'build',str(stage),'--'+mode,'--link',str(stage/'shim.o'),'--output',str(binary)],check=True)
        subprocess.run([str(binary)],check=True,timeout=10)
    macos=(ROOT/'src/filesystem/macos.dyn').read_text()
    macos=macos[macos.index('extern fn darwin_mmap'):macos.index('// APFS can seed')].replace('"mmap"','"probe_mmap"').replace('"munmap"','"probe_munmap"')
    (stage/'main.dyn').write_text(BASE+macos+'''
extern fn probe_mapping_check "probe_mapping_check"(present:bool) i32
fn main() {
 for mode in 0..2 {
  probe_reset(#cast(i32,mode))
  mapped:=map_file(1,4294967313)
  if probe_mapping_check(mapped!=nil)!=1 {#panic("resilient mapping")}
  if mapped!=nil {unmap_file(mapped,4294967313)}
 }
}
''')
    for mode in ('debug','release'):
        binary=stage/('mac-'+mode)
        subprocess.run([DYN,'build',str(stage),'--'+mode,'--link',str(stage/'shim.o'),'--output',str(binary)],check=True)
        subprocess.run([str(binary)],check=True,timeout=10)
    for module in ('filesystem','host','cstring','owned_arena'):
        shutil.copytree(ROOT/'src'/module,stage/module)
    (stage/'main.dyn').write_text('use "./filesystem" fs\nfn main() { file:=fs.File{}\n _=fs.map_file(file.descriptor,1)\n _=fs.copy_range(&file,0,&file,1)\n _=fs.clone_exclusive(&file,"unused")\n _=fs.resize(&file,1) }\n')
    for target in ('x86_64-macos','aarch64-macos','x86_64-windows','aarch64-windows'):
        subprocess.run([DYN,'check',str(stage),'--target',target],check=True)
print('PASS platform storage seams: 64-bit mappings, resilient flags, range cloning/edges, failures, source handles; four target checks (not native OS execution)')
