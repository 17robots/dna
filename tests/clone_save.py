#!/usr/bin/env python3
"""Run production APFS clone setup and save writer with a Linux copy emulator."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get('DYN', 'dyn')

def function(source, name):
    start = source.index('pub fn ' + name + '(')
    body = source.index('{', start)
    depth, end = 1, body + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

SHIM = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <unistd.h>
static int clones,source_fd,mutated;
int probe_mode(void) {return atoi(getenv("DNA_CLONE_MODE"));}
int probe_edit(void) {return atoi(getenv("DNA_CLONE_EDIT"));}
int probe_mapped(void) {return atoi(getenv("DNA_CLONE_MAP"));}
int probe_clones(void) {return clones;}
_Bool probe_expect_seed(void) {int m=probe_mode();return probe_edit()!=6&&probe_edit()!=8&&(m==0||m==8||m==9||m==10||m==11);}
int probe_descriptors(void) {DIR*d=opendir("/proc/self/fd");assert(d);int n=0;struct dirent*e;while((e=readdir(d)))if(e->d_name[0]!='.')n++;closedir(d);return n;}
int *probe_errno(void) {return &errno;}
int probe_clone(int source,int directory,const char *path,uint32_t flags) {
 assert(directory==-2&&flags==3);clones++;source_fd=source;
 int mode=probe_mode();if(mode==1){errno=EOPNOTSUPP;return -1;}
 int target=open(path,O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
 if(target<0)return -1;
 struct stat info;assert(!fstat(source,&info));assert(!fchmod(target,info.st_mode&0777));
 char bytes[65536];off_t at=0;ssize_t n;
 while((n=pread(source,bytes,sizeof(bytes),at))>0){assert(write(target,bytes,n)==n);at+=n;}
 assert(n==0);
 if(mode==7)assert(!ftruncate(target,at-1));
 assert(!close(target));
 if(mode==4){char fdpath[64];snprintf(fdpath,sizeof(fdpath),"/proc/self/fd/%d",source);int changed=open(fdpath,O_WRONLY);assert(changed>=0);assert(pwrite(changed,"Z",1,0)==1);close(changed);}
 if(mode==5){assert(!unlink(path));assert(!symlink("victim.txt",path));}
 if(mode==6){assert(!unlink(path));assert(!mkfifo(path,0600));}
 return 0;
}
int probe_open(const char *path,int flags) {assert(flags==16777478);if(probe_mode()==3){errno=EACCES;return -1;}return open(path,O_RDWR|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);}
int probe_unlink(const char *path) {return unlink(path);}
void probe_mutate(void) {char path[64];snprintf(path,sizeof(path),"/proc/self/fd/%d",source_fd);int fd=open(path,O_WRONLY);assert(fd>=0);assert(pwrite(fd,"Z",1,0)==1);close(fd);}
void probe_after_write(void) {if(probe_mode()==11&&!mutated){mutated=1;probe_mutate();}}
void *probe_map(intptr_t fd,uint64_t size) {if(!probe_mapped())return NULL;void *p=mmap(NULL,size,PROT_READ,MAP_PRIVATE,(int)fd,0);return p==MAP_FAILED?NULL:p;}
void probe_unmap(void *p,uint64_t size) {assert(!munmap(p,size));}
int probe_truncate(int fd,int64_t length) {if(probe_mode()==10&&!mutated){mutated=1;probe_mutate();}if(probe_mode()==8){errno=ENOSPC;return -1;}return ftruncate(fd,length);}
'''
with tempfile.TemporaryDirectory(prefix='dna-clone-save-') as directory:
    stage = Path(directory)
    for module in ('owned_arena', 'cstring', 'host', 'filesystem', 'files', 'buffer'):
        shutil.copytree(ROOT/'src'/module, stage/module)
    (stage/'main.dyn').write_text((ROOT/'tests/clone_save/main.dyn').read_text())
    subprocess.run(['cc','-x','c','-c','-o',str(stage/'shim.o'),'-'],input=SHIM,text=True,check=True)
    macos = (ROOT/'src/filesystem/macos.dyn').read_text()
    linux_path = stage/'filesystem/linux.dyn'
    linux = linux_path.read_text().replace('WholeFileClones: bool = false', 'WholeFileClones: bool = true')
    linux = linux.replace(function(linux, 'clone_exclusive'), function(macos, 'clone_exclusive'))
    linux = linux.replace(function(linux, 'resize'), function(macos, 'resize'))
    linux = linux.replace(function(linux, 'copy_range'), '''pub fn copy_range(source:*const File,offset:u64,target:*File,length:usize) Result {return Result{kind:errors.Kind.Unsupported}}''')
    linux = linux.replace(function(linux, 'map_file'), 'pub fn map_file(fd:isize,length:u64) *u8 {return test_map(fd,length)}')
    linux = linux.replace(function(linux, 'unmap_file'), 'pub fn unmap_file(bytes:*u8,length:u64) {test_unmap(bytes,length)}')
    linux += '''
extern fn test_map "probe_map"(fd:isize,length:u64) *u8
extern fn test_unmap "probe_unmap"(bytes:*u8,length:u64)
fn darwin_prepare_errno() {}
extern fn darwin_clone "probe_clone"(source:i32,directory:i32,path:*const u8,flags:u32) i32
extern fn darwin_open "probe_open"(path:*const u8,flags:i32) i32
extern fn darwin_unlink "probe_unlink"(path:*const u8) i32
extern fn darwin_truncate "probe_truncate"(file:i32,length:i64) i32
extern fn darwin_errno "probe_errno"() *i32
fn darwin_error() isize {return 0-#cast(isize,darwin_errno().*)}
fn darwin_path(path:[]const u8,storage:[]u8) *const u8 {
 result:=bounded_string(storage,path)
 if !result.ok || #len(path)==0 {return nil}
 return result.value
}
fn darwin_result(code:i32) Result {
 if code==0 {return Result{ok:true}}
 return Result{error:darwin_error(),kind:errors.Kind.System}
}
'''
    linux_path.write_text(linux)
    boundary = stage/'filesystem/filesystem.dyn'
    source = boundary.read_text().replace('pub fn write(file: *File, source: []const u8) Result {', '''pub test_written:usize=0
pub test_seeks:usize=0
extern fn probe_mode "probe_mode"() i32
pub fn test_mode() i32 {return probe_mode()}
extern fn probe_after_write "probe_after_write"()
pub fn write(file: *File, source: []const u8) Result {
  if probe_mode()==9 {return Result{error:-5,kind:errors.Kind.System}}
  probe_after_write()
  test_written+=#len(source)''').replace('pub fn seek(file: *File, offset: usize) Result {', 'pub fn seek(file: *File, offset: usize) Result {\n test_seeks+=1')
    boundary.write_text(source)
    line = b'original line of text\n'
    data = line * ((17 << 20) // len(line))
    middle = len(data)//2
    expected = [data+b'APPEND', data[:middle]+b'EDIT'+data[middle+4:],
                data[:middle]+b'INSERT'+data[middle:], data[:middle]+data[middle+12345:],
                data[:middle], b'X'+data[1:], data+b'APPEND', data+b'APPENDSECOND', b'BEGIN'+data]
    cases = [(0, edit, 0) for edit in range(9)] + [(mode, 0, 0) for mode in (1,2,3,4,5,6,7,8,9,10,11,12)]
    cases += [(0, edit, 1) for edit in (*range(6), 7, 8)] + [(mode, 0, 1) for mode in (4,10,11)]
    for mode in ('debug', 'release'):
        binary = stage/mode
        subprocess.run(['python3',str(ROOT/'scripts/compile.py'),DYN,'build',str(stage),'--'+mode,'--link',str(stage/'shim.o'),'--output',str(binary)],check=True)
        for fault, edit, mapped in cases:
            with tempfile.TemporaryDirectory(prefix='dna-clone-case-') as temporary:
                work = Path(temporary)
                original = work/'original.txt'
                original.write_bytes(data)
                original.chmod(0o440 if fault==12 else 0o640)
                (work/'victim.txt').write_bytes(b'untouched victim')
                if fault == 2:
                    (work/'original.txt.dna-write').write_bytes(b'existing temporary')
                try:
                    subprocess.run([str(binary)],cwd=work,env=dict(os.environ,DNA_CLONE_MODE=str(fault),DNA_CLONE_EDIT=str(edit),DNA_CLONE_MAP=str(mapped)),check=True,timeout=30)
                except subprocess.CalledProcessError as error:
                    raise AssertionError((mode, fault, edit, mapped)) from error
                wanted = data if fault in (2,8,9) else (b'Z'+data[1:] if fault in (4,10,11) else expected[edit])
                if edit==6:
                    assert (work/'copy.txt').read_bytes()==wanted
                    wanted=data
                assert original.read_bytes() == wanted, (mode, fault, edit, mapped)
                assert original.stat().st_mode & 0o777 == (0o440 if fault==12 else 0o640)
                assert (work/'victim.txt').read_bytes() == b'untouched victim'
                if fault == 2:
                    assert (work/'original.txt.dna-write').read_bytes() == b'existing temporary'
                else:
                    assert not (work/'original.txt.dna-write').exists(), (mode, fault, edit)
    for target in ('x86_64-macos', 'aarch64-macos', 'x86_64-windows', 'aarch64-windows'):
        subprocess.run(['python3', str(ROOT/'scripts/compile.py'), DYN, 'check', str(stage), '--target', target], check=True)
print('PASS clone saves: append, replacement, shifted insert/delete, truncation, first-byte edit; fallback, races, failures, mode, descriptor cleanup and portable buffer targets (debug/release; clone syscall emulated)')
