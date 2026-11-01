#!/usr/bin/env python3
"""Private Windows executables receive owner-only execute rights at creation."""
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

SOURCE = r'''use "./filesystem" fs
use "std/dynlib" loader
fn write_payload(executable:bool, path:[]const u8) {
  created:=fs.FileResult{}
  if executable { created=fs.create_private_executable_exclusive(path)
  } else { created=fs.create_private_exclusive(path) }
  if !created.ok { #panic("private output creation") }
  opened:=fs.open("payload.exe")
  if !opened.ok { #panic("PE fixture open") }
  buffer:[16384]u8=[]
  for {
    read:=fs.read(&opened.value,buffer[..])
    if !read.ok { #panic("PE fixture read") }
    if read.transferred==0 { break }
    at:usize=0
    for at<read.transferred {
      written:=fs.write(&created.value,buffer[at..read.transferred])
      if !written.ok || written.transferred==0 { #panic("private PE write") }
      at+=written.transferred
    }
  }
  if !fs.close(&opened.value).ok || !fs.sync(&created.value).ok || !fs.close(&created.value).ok { #panic("private PE close") }
}
fn main() {
  // Both files contain the same valid PE. Their only intended difference is
  // the creation-time execute right in the protected owner-rights DACL.
  write_payload(true,"private café 日本語.exe")
  write_payload(false,"data café 日本語.exe")
  if !fs.executable("private café 日本語.exe") || fs.executable("data café 日本語.exe") || fs.executable("missing.exe") || fs.executable(".") || fs.executable("reparse-payload.exe") { #panic("effective executable access must match private DACL and reject non-regular paths") }
  if fs.create_private_executable_exclusive("private café 日本語.exe").ok || fs.create_private_exclusive("data café 日本語.exe").ok { #panic("private creation must not overwrite") }
  kernel:=loader.open("kernel32.dll",0)
  process_symbol:=loader.symbol(kernel.value,"GetCurrentProcess")
  count_symbol:=loader.symbol(kernel.value,"GetProcessHandleCount")
  if !kernel.ok || !process_symbol.ok || !count_symbol.ok { #panic("handle API") }
  process:=#cast(fn()rawptr,process_symbol.value)
  handles:=#cast(fn(rawptr,*u32)i32,count_symbol.value)
  // Warm both creation paths before checking steady ownership.
  for attempt in 0..2 {
    file:=fs.create_private_executable_exclusive("temporary.exe")
    if !file.ok || !fs.close(&file.value).ok || !fs.remove("temporary.exe").ok { #panic("warmup") }
  }
  before:u32=0
  after:u32=0
  if handles(process(),&before)==0 { #panic("initial handle count") }
  for attempt in 0..128 {
    file:=fs.create_private_executable_exclusive("temporary.exe")
    if !file.ok || !fs.close(&file.value).ok || !fs.remove("temporary.exe").ok { #panic("executable creation lifecycle") }
    file=fs.create_private_exclusive("temporary.data")
    if !file.ok || !fs.close(&file.value).ok || !fs.remove("temporary.data").ok { #panic("data creation lifecycle") }
    if !fs.executable("private café 日本語.exe") || fs.executable("data café 日本語.exe") || fs.executable("missing.exe") || fs.executable(".") || fs.executable("reparse-payload.exe") { #panic("effective executable access lifecycle") }
  }
  if handles(process(),&after)==0 || before!=after { #panic("private creation handle leak") }
}
'''


def acl_mask(path):
    """Return the sole owner-rights allow mask after verifying protection."""
    advapi = c.WinDLL('advapi32', use_last_error=True)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    advapi.GetNamedSecurityInfoW.argtypes = [c.c_wchar_p, c.c_uint32, c.c_uint32,
        c.c_void_p, c.c_void_p, c.POINTER(c.c_void_p), c.c_void_p, c.POINTER(c.c_void_p)]
    advapi.GetNamedSecurityInfoW.restype = c.c_uint32
    advapi.GetSecurityDescriptorControl.argtypes = [c.c_void_p,
        c.POINTER(c.c_uint16), c.POINTER(c.c_uint32)]
    advapi.GetSecurityDescriptorControl.restype = c.c_int
    advapi.GetAce.argtypes = [c.c_void_p, c.c_uint32, c.POINTER(c.c_void_p)]
    advapi.GetAce.restype = c.c_int
    advapi.ConvertSidToStringSidW.argtypes = [c.c_void_p, c.POINTER(c.c_void_p)]
    advapi.ConvertSidToStringSidW.restype = c.c_int
    kernel.LocalFree.argtypes = [c.c_void_p]
    kernel.LocalFree.restype = c.c_void_p
    descriptor, dacl, sid = c.c_void_p(), c.c_void_p(), c.c_void_p()
    assert advapi.GetNamedSecurityInfoW(str(path), 1, 4, None, None, c.byref(dacl),
        None, c.byref(descriptor)) == 0
    try:
        control, revision = c.c_uint16(), c.c_uint32()
        assert advapi.GetSecurityDescriptorControl(descriptor, c.byref(control), c.byref(revision))
        assert control.value & 0x1000, 'private DACL must be protected from inheritance'
        assert dacl.value and c.c_uint16.from_address(dacl.value + 4).value == 1, 'one ACE, no inherited Everyone/Users grants'
        ace = c.c_void_p()
        assert advapi.GetAce(dacl, 0, c.byref(ace))
        assert c.c_uint8.from_address(ace.value).value == 0, 'access-allowed ACE'
        assert advapi.ConvertSidToStringSidW(c.c_void_p(ace.value + 8), c.byref(sid))
        assert c.wstring_at(sid) == 'S-1-3-4', 'sole grant must belong to owner-rights SID'
        return c.c_uint32.from_address(ace.value + 4).value
    finally:
        if sid.value:
            kernel.LocalFree(sid)
        kernel.LocalFree(descriptor)


def main():
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first.')
    environment = sdk_environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-private-executable-') as temporary:
        work = Path(temporary)
        stage = work / 'stage'
        stage.mkdir()
        for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
            shutil.copytree(ROOT / 'src' / module, stage / module)
        # Compile the exact production filesystem adapter, not an ACL mock.
        (stage / 'main.dyn').write_text(SOURCE, encoding='utf-8')
        for target in ('x86_64-windows', 'aarch64-windows'):
            for mode in ('debug', 'release'):
                subprocess.run([str(compiler), 'build', str(stage), '--' + mode,
                    '--target', target, '--emit-object', '--no-link', '--output',
                    str(work / (target + '-' + mode))], env=environment, check=True, timeout=120)
            print('PASS private executable objects: ' + target, flush=True)
        if os.name != 'nt':
            print('UNAVAILABLE Windows runtime; objects do not prove ACL or execution behavior')
            return
        kits = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits/10/Lib'
        libraries = work / 'lib'
        libraries.mkdir()
        for name in ('kernel32', 'advapi32'):
            candidates = sorted(kits.glob('*/um/x64/' + name + '.lib'))
            if not candidates:
                raise SystemExit('Windows SDK x64 ' + name + '.lib is required.')
            shutil.copyfile(candidates[-1], libraries / ('lib' + name + '.dll.a'))
        environment['DYN_LIBRARY_PATH'] = str(libraries)
        source = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/whoami.exe'
        assert source.is_file(), 'native known-good PE fixture is required'
        payload = source.read_bytes()
        for mode in ('debug', 'release'):
            binary = work / ('private-' + mode + '.exe')
            subprocess.run([str(compiler), 'build', str(stage), '--' + mode,
                '--output', str(binary)], env=environment, check=True, timeout=120)
            working = work / ('café 日本語-' + mode)
            working.mkdir()
            (working / 'payload.exe').write_bytes(payload)
            os.symlink('payload.exe', working / 'reparse-payload.exe')
            subprocess.run([str(binary)], cwd=working, env=environment, check=True, timeout=30)
            executable = working / 'private café 日本語.exe'
            data = working / 'data café 日本語.exe'
            assert executable.read_bytes() == data.read_bytes() == payload
            executable_mask = acl_mask(executable)
            data_mask = acl_mask(data)
            assert executable_mask & 0x20 and not data_mask & 0x20, (executable_mask, data_mask)
            assert executable_mask == data_mask | 0x20, 'only FILE_EXECUTE differs'
            result = subprocess.run([str(executable)], cwd=working, env=environment,
                check=True, capture_output=True, timeout=10)
            assert result.stdout.strip(), 'real private PE execution must produce whoami output'
            try:
                subprocess.run([str(data)], cwd=working, env=environment, capture_output=True, timeout=10)
            except PermissionError as error:
                assert error.winerror == 5, error
            else:
                raise AssertionError('private data DACL must not grant executable access')
            print('PASS Windows private executable: creation-time protected owner-only DACL, '
                  'Unicode PE execution, effective ACL access, nofollow, non-executable data default, no-overwrite and handle cleanup (' + mode + ')', flush=True)


if __name__ == '__main__':
    main()
