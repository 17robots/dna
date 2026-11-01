#!/usr/bin/env python3
"""Compile Windows recovery IO on both architectures; execute on Windows only."""
import ctypes as c
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
extern fn string_length "strlen"(text:*const u8) usize
extern fn test_read "_read"(fd:i32, output:*u8, length:u32) i32
extern fn test_handle_info "GetHandleInformation"(handle:rawptr, flags:*u32) i32
extern fn test_process "GetCurrentProcess"() rawptr
extern fn test_handles "GetProcessHandleCount"(process:rawptr, count:*u32) i32
fn main() {
  path:[]const u8="café 日本語.txt\0"
  replacement:[]const u8="replacement.txt\0"
  missing:[]const u8="missing.txt\0"
  fd:=rec_open(&path[0], 524481, 384)
  if fd<0 { #panic("private Unicode create") }
  inheritance:u32=0
  if test_handle_info(win_io_handle(fd), &inheritance)==0 || (inheritance&1)!=0 { #panic("descriptor must not inherit") }
  bytes:[4]u8=[65,0,13,10]
  if rec_write(fd,&bytes[0],4)!=4 || rec_sync(fd)!=0 || rec_close(fd)!=0 { #panic("binary write and flush") }
  if rec_open(&path[0],524481,384)>=0 || rec_errno().*!=17 { #panic("exclusive create must preserve existing file") }
  fd=rec_open(&path[0],657408,0)
  read:[4]u8=[]
  if fd<0 || test_read(fd,&read[0],4)!=4 || read[0]!=65 || read[1]!=0 || read[2]!=13 || read[3]!=10 || rec_close(fd)!=0 { #panic("binary read") }
  fd=rec_open(&replacement[0],524481,448)
  changed:[]const u8="NEW"
  if fd<0 || rec_write(fd,&changed[0],3)!=3 || rec_sync(fd)!=0 || rec_close(fd)!=0 || rec_rename(&replacement[0],&path[0])!=0 { #panic("atomic file replacement") }
  fd=rec_open(&path[0],0,0)
  if fd<0 || test_read(fd,&read[0],4)!=3 || read[0]!=78 || read[2]!=87 || rec_close(fd)!=0 { #panic("replacement bytes") }
  if rec_open(&missing[0],0,0)>=0 || rec_errno().*!=2 { #panic("normalized missing error") }
  saved:=rec_errno()
  environment:[]const u8="DNA_REC_IO_ASCII\0"
  value:=memory_environment(&environment[0])
  if value==nil || value.*!=49 || saved!=rec_errno() || saved.*!=2 { #panic("thread-local error preservation") }
  bad:[2]u8=[255,0]
  if rec_open(&bad[0],0,0)>=0 { #panic("invalid UTF-8 must fail") }
  directory:[]const u8="private-directory\0"
  if rec_mkdir(&directory[0],448)!=0 || rec_mkdir(&directory[0],448)==0 || rec_errno().*!=17 { #panic("private directory") }
  fd=rec_open(&directory[0],720896,0)
  if fd<0 || rec_sync(fd)==0 || rec_errno().*!=95 || rec_close(fd)!=0 { #panic("directory flush must report unsupported") }
  if rec_open(&path[0],720896,0)>=0 || rec_errno().*!=20 { #panic("directory validation") }
  junction:[]const u8="reparse-link\0"
  if rec_open(&junction[0],720896,0)>=0 || rec_errno().*!=95 { #panic("nofollow must refuse a junction") }
  template:[32]u8=[]
  pattern:[]const u8="private-XXXXXX"
  for at in 0..#len(pattern) { template[at]=pattern[at] }
  fd=rec_temp(&template[0])
  if fd<0 || rec_write(fd,&changed[0],3)!=3 || rec_sync(fd)!=0 || rec_close(fd)!=0 { #panic("exclusive private temporary") }
  if rec_unlink(&template[0])!=0 { #panic("temporary cleanup") }
  library_name:[]const u8="kernel32.dll\0"
  library:=syntax_dlopen(&library_name[0],0)
  if library==nil || syntax_dlclose(library)!=0 { #panic("native library lifecycle") }
  for attempt in 0..8 {
    fd=rec_open(&path[0],0,0)
    if fd<0 || rec_close(fd)!=0 { #panic("warmup") }
  }
  before:u32=0
  after:u32=0
  if test_handles(test_process(),&before)==0 { #panic("handle count") }
  for attempt in 0..256 {
    fd=rec_open(&path[0],0,0)
    if fd<0 || rec_close(fd)!=0 { #panic("repeated lifecycle") }
    if rec_open(&junction[0],720896,0)>=0 { #panic("reparse refusal lifecycle") }
  }
  if test_handles(test_process(),&after)==0 || before!=after { #panic("IO handle leak") }
}
'''


def private_acl(path):
    """Inspect the actual protected owner-rights DACL, not POSIX mode emulation."""
    advapi = c.WinDLL('advapi32', use_last_error=True)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    advapi.GetNamedSecurityInfoW.argtypes = [c.c_wchar_p, c.c_uint32, c.c_uint32,
        c.c_void_p, c.c_void_p, c.POINTER(c.c_void_p), c.c_void_p, c.POINTER(c.c_void_p)]
    advapi.GetNamedSecurityInfoW.restype = c.c_uint32
    advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [c.c_void_p,
        c.c_uint32, c.c_uint32, c.POINTER(c.c_void_p), c.POINTER(c.c_uint32)]
    advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = c.c_int
    kernel.LocalFree.argtypes = [c.c_void_p]
    kernel.LocalFree.restype = c.c_void_p
    descriptor, dacl, text = c.c_void_p(), c.c_void_p(), c.c_void_p()
    assert advapi.GetNamedSecurityInfoW(str(path), 1, 4, None, None, c.byref(dacl),
        None, c.byref(descriptor)) == 0
    try:
        length = c.c_uint32()
        assert advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor,
            1, 4, c.byref(text), c.byref(length))
        value = c.wstring_at(text)
        assert value.startswith('D:P') and value.count('(') == 1 and ';;;OW)' in value, value
    finally:
        if text.value:
            kernel.LocalFree(text)
        kernel.LocalFree(descriptor)


compiler = real_dyn()
if compiler is None:
    raise SystemExit('Install the pinned Dyn SDK first.')
with tempfile.TemporaryDirectory(prefix='dna-rec-io-') as temporary:
    stage = Path(temporary) / 'stage'
    stage.mkdir()
    bridge = stage / 'native'
    bridge.mkdir()
    for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
        shutil.copytree(ROOT / 'src' / module, bridge / module)
    shutil.copyfile(ROOT / 'src/native/dyn/rec_io_windows.dyn', bridge / 'rec_io_windows.dyn')
    # The fixture lives in the production adapter's module, so private policy
    # functions are exercised without inventing a public testing ABI.
    (bridge / 'main.dyn').write_text(SOURCE, encoding="utf-8")
    environment = sdk_environment(compiler)
    for target in ('x86_64-windows', 'aarch64-windows'):
        for mode in ('debug', 'release'):
            subprocess.run([str(compiler), 'build', str(bridge), '--' + mode,
                '--target', target, '--emit-object', '--no-link', '--output',
                str(stage / (target + '-' + mode))], env=environment, check=True, timeout=120)
        print('PASS Windows recovery IO objects: ' + target, flush=True)
    if os.name != 'nt':
        print('UNAVAILABLE Windows runtime; object checks do not qualify native IO')
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
    environment['DNA_REC_IO_ASCII'] = '1'
    for mode in ('debug', 'release'):
        binary = stage / ('rec-io-' + mode + '.exe')
        subprocess.run([str(compiler), 'build', str(bridge), '--' + mode,
            '--output', str(binary)], env=environment, check=True, timeout=120)
        working = stage / ('café 日本語-' + mode)
        working.mkdir()
        destination = working / 'real-directory'
        destination.mkdir()
        subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', 'reparse-link', str(destination)],
            cwd=working, check=True, capture_output=True)
        try:
            subprocess.run([str(binary)], cwd=working, env=environment, check=True, timeout=30)
            assert (working / 'café 日本語.txt').read_bytes() == b'NEW'
            private_acl(working / 'café 日本語.txt')
            private_acl(working / 'private-directory')
            print('PASS Windows recovery IO native Unicode, binary descriptors, private ACLs, '
                  'atomic replacement, nofollow, errno and handle lifecycle (' + mode + ')', flush=True)
        finally:
            # Remove the junction itself before TemporaryDirectory recurses.
            os.rmdir(working / 'reparse-link')
