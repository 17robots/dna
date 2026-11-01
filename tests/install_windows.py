#!/usr/bin/env python3
"""Qualify retained-handle Windows directory transport; cross objects elsewhere."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn
from sdk_compat import environment as sdk_environment

SOURCE = r'''#link("ucrt")
use "std/io"
extern fn string_length "strlen"(text:*const u8) usize
extern fn rec_alloc "calloc"(count:usize, size:usize) rawptr
extern fn rec_free "free"(value:rawptr)
extern fn test_read "_read"(fd:i32, bytes:*u8, length:u32) i32
fn equal(left:*const u8, right:[]const u8) bool {
  length:=string_length(left)
  if length!=#len(right) { return false }
  for at in 0..length { if left[..length][at]!=right[at] { return false } }
  return true
}
fn main() {
  record:=InstallWinDirectoryRecord{}
  rename:=InstallWinRename{}
  attributes:=InstallWinAttributes{}
  if #cast(usize,&record.name[0])-#cast(usize,&record)!=104 || #cast(usize,&rename.name[0])-#cast(usize,&rename)!=20 || #sizeof(InstallWinUnicode)!=16 || #sizeof(InstallWinAttributes)!=48 || #sizeof(InstallWinStatus)!=16 { #panic("native directory ABI layout") }
  root:[]const u8="parent\0"
  moved:[]const u8="renamed-parent\0"
  leaf:[]const u8="café 日本語.txt\0"
  link:[]const u8="reparse-link\0"
  root_fd:=rec_open(&root[0],720896,0)
  if root_fd<0 { #panic("retained directory open") }
  info:=InstallStat{}
  if install_fstat(root_fd,&info)!=0 || (info.mode&61440)!=16384 { #panic("directory metadata") }
  // Move the parent while the descriptor remains open. Subsequent operations
  // must still address that same object, without reopening its stale pathname.
  if install_rename(-100,&root[0],-100,&moved[0],1)!=0 { #panic("parent rename") }
  fd:=install_openat(root_fd,&leaf[0],655360|2048,0)
  text:[5]u8=[]
  if fd<0 || test_read(fd,&text[0],5)!=5 || text[0]!=72 || text[4]!=79 || install_fstat(fd,&info)!=0 || info.size!=5 || rec_close(fd)!=0 { #panic("relative file after parent rename") }
  if install_fstatat(root_fd,&leaf[0],&info,256)!=0 || (info.mode&61440)!=32768 || info.inode==0 { #panic("relative metadata") }
  original:=info
  native_path:[]const u8="renamed-parent/café 日本語.txt\0"
  if disk_stat(&native_path[0],&info)!=0 || info.inode!=original.inode || info.modify_seconds!=original.modify_seconds || info.change_seconds!=original.change_seconds { #panic("path and retained metadata agree") }
  paths:[5][]const u8=["../escape\0","folder/child\0","folder\\child\0","file:stream\0","..\0"]
  for path in paths {
    if install_openat(root_fd,&path[0],655360,0)>=0 || rec_errno().*!=22 { #panic("unsafe relative component") }
  }
  if install_openat(root_fd,&link[0],720896,0)>=0 || rec_errno().*!=95 { #panic("relative reparse refusal") }
  if install_fstatat(root_fd,&link[0],&info,256)!=0 || (info.mode&61440)!=40960 { #panic("nofollow reparse metadata") }
  duplicate:=install_dup(root_fd)
  if duplicate<0 { #panic("descriptor duplicate") }
  directory:=install_fdopendir(duplicate)
  if directory==nil { _=rec_close(duplicate)
    #panic("directory stream") }
  found:bool=false
  found_link:bool=false
  count:usize=0
  for {
    entry:=install_readdir(directory)
    if entry==nil { break }
    count+=1
    if equal(&entry.name[0],"café 日本語.txt") { found=entry.kind==8 }
    if equal(&entry.name[0],"reparse-link") { found_link=entry.kind==10 }
    if count>4096 { #panic("directory enumeration must terminate") }
  }
  if !found || !found_link || count<700 || rec_errno().*!=0 || search_dirfd(directory)!=duplicate || install_closedir(directory)!=0 { #panic("Unicode multi-batch directory enumeration") }
  // fdopendir failure must leave the caller's descriptor valid and owned.
  fd=install_openat(root_fd,&leaf[0],655360,0)
  if fd<0 || install_fdopendir(fd)!=nil || install_fstat(fd,&info)!=0 || rec_close(fd)!=0 { #panic("failed fdopendir ownership") }
  destination:[]const u8="renamed.txt\0"
  renamed:=install_rename(root_fd,&leaf[0],root_fd,&destination[0],1)
  if renamed!=0 { _=io.println(io.stderr(), "relative rename failed: errno {}", rec_errno().*)
    #panic("relative no-replace rename") }
  old:=install_openat(root_fd,&leaf[0],655360,0)
  if old>=0 { _=rec_close(old)
    #panic("relative rename must retire old name") }
  fd=install_openat(root_fd,&destination[0],655360,0)
  if fd<0 || rec_close(fd)!=0 { #panic("relative renamed file") }
  occupied:[]const u8="occupied.txt\0"
  if install_rename(root_fd,&destination[0],root_fd,&occupied[0],1)==0 || rec_errno().*!=17 { #panic("rename must not overwrite") }
  if install_rename(root_fd,&destination[0],root_fd,&occupied[0],2)==0 || rec_errno().*!=95 { #panic("exchange must report unsupported") }
  kernel:=win_io_loader.open("kernel32.dll",0)
  handles:=#cast(fn(rawptr,*u32)i32,win_io_symbol(kernel.value,"GetProcessHandleCount"))
  before:u32=0
  after:u32=0
  if handles(install_win_api.process(),&before)==0 { #panic("initial handle count") }
  for attempt in 0..256 {
    fd=install_openat(root_fd,&destination[0],655360,0)
    if fd<0 || rec_close(fd)!=0 { #panic("repeated relative file lifecycle") }
    duplicate=install_dup(root_fd)
    directory=install_fdopendir(duplicate)
    if directory==nil { _=rec_close(duplicate)
      #panic("repeated directory open") }
    // Closing a partially consumed enumeration mirrors cancelled search.
    _=install_readdir(directory)
    if install_closedir(directory)!=0 { #panic("cancelled directory cleanup") }
  }
  if handles(install_win_api.process(),&after)==0 || before!=after { #panic("relative IO handle leak") }
  if rec_close(root_fd)!=0 { #panic("root ownership") }
  temporary:[32]u8=[]
  pattern:[]const u8="private-XXXXXX"
  for at in 0..#len(pattern) { temporary[at]=pattern[at] }
  if install_mkdtemp(&temporary[0])==nil || install_lstat(&temporary[0],&info)!=0 || (info.mode&61440)!=16384 || install_rmdir(&temporary[0])!=0 { #panic("private temporary directory") }
}
'''

compiler = real_dyn()
if compiler is None:
    raise SystemExit('Install the pinned Dyn SDK first.')
with tempfile.TemporaryDirectory(prefix='dna-install-win-') as temporary:
    stage = Path(temporary)
    bridge = stage / 'native'
    bridge.mkdir()
    for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
        shutil.copytree(ROOT / 'src' / module, bridge / module)
    for name in ('rec_io_windows.dyn', 'install_windows.dyn'):
        shutil.copyfile(ROOT / 'src/native/dyn' / name, bridge / name)
    (bridge / 'main.dyn').write_text(SOURCE, encoding="utf-8")
    environment = sdk_environment(compiler)
    for target in ('x86_64-windows', 'aarch64-windows'):
        for mode in ('debug', 'release'):
            subprocess.run([str(compiler), 'build', str(bridge), '--' + mode,
                '--target', target, '--emit-object', '--no-link', '--output',
                str(stage / (target + '-' + mode))], env=environment, check=True, timeout=120)
        print('PASS Windows retained-directory objects: ' + target, flush=True)
    if os.name != 'nt':
        print('UNAVAILABLE Windows runtime; object checks do not qualify directory transport')
        raise SystemExit
    kits = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits/10/Lib'
    libraries = stage / 'lib'
    libraries.mkdir()
    for name, folder in (('kernel32', 'um'), ('advapi32', 'um'), ('ucrt', 'ucrt')):
        candidates = sorted(kits.glob('*/' + folder + '/x64/' + name + '.lib'))
        if not candidates:
            raise SystemExit('Windows SDK x64 ' + name + '.lib is required.')
        shutil.copyfile(candidates[-1], libraries / ('lib' + name + '.dll.a'))
    environment['DYN_LIBRARY_PATH'] = str(libraries)
    for mode in ('debug', 'release'):
        binary = stage / ('install-' + mode + '.exe')
        subprocess.run([str(compiler), 'build', str(bridge), '--' + mode,
            '--output', str(binary)], env=environment, check=True, timeout=120)
        working = stage / ('café 日本語-' + mode)
        working.mkdir()
        parent = working / 'parent'
        parent.mkdir()
        (parent / 'café 日本語.txt').write_bytes(b'HELLO')
        (parent / 'occupied.txt').write_bytes(b'KEEP')
        for index in range(700):
            (parent / ('entry-' + str(index) + '.txt')).touch()
        escape = working / 'escape'
        escape.mkdir()
        subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', 'reparse-link', str(escape)],
            cwd=parent, check=True, capture_output=True)
        try:
            subprocess.run([str(binary)], cwd=working, env=environment, check=True, timeout=60)
            assert (working / 'renamed-parent/occupied.txt').read_bytes() == b'KEEP'
            assert (working / 'renamed-parent/renamed.txt').read_bytes() == b'HELLO'
            print('PASS Windows native retained parent, Unicode enumeration, relative opens, '
                  'nofollow, no-overwrite rename and cancelled stream cleanup (' + mode + ')', flush=True)
        finally:
            root = working / ('renamed-parent' if (working / 'renamed-parent').exists() else 'parent')
            os.rmdir(root / 'reparse-link')
