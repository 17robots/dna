#!/usr/bin/env python3
"""Qualify Windows console ownership and bounded native record input."""
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
use "std/sync" sync
use "std/thread"
use "std/mem"
extern fn string_length "strlen"(text:*const u8) usize
extern fn rec_alloc "calloc"(count:usize,size:usize) rawptr
extern fn rec_free "free"(value:rawptr)
extern fn tty_atexit "atexit"(handler:fn())i32
struct TtySize { rows,columns,width,height:u16 }
tty_input:i32=0
tty_output:i32=1
tty_wake_descriptor:i32=-1
tty_active:sync.AtomicU32
tty_resize_pending:sync.AtomicU32
tty_command_line:[65536]u8
fn dna_tty_leave() { tty_leave_host()
  sync.store_u32(&tty_active,0) }
fn tty_exit_handler() { dna_tty_leave() }
read_result:i32=100
read_started:sync.AtomicU32
fn read_worker(context:rawptr)isize {
  _=context
  bytes:[64]u8=[]
  sync.store_u32(&read_started,1)
  for {
    read_result=tty_read_host(&bytes[0],64,-1)
    if read_result!=-2 || sync.exchange_u32(&tty_resize_pending,0)==0 { break }
  }
  return 0
}
fn expect_bytes(actual:[]const u8,expected:[]const u8) {
  if #len(actual)!=#len(expected) { #panic("console input length") }
  for at in 0..#len(actual) { if actual[at]!=expected[at] { #panic("console input bytes") } }
}
fn main() {
  win_tty_prepare()
  // A child mode validates real argument parsing, quoting and per-child env.
  length:=tty_arguments()
  if length<=0 { #panic("native argv") }
  at:=string_length(&tty_command_line[0])+1
  if at<#cast(usize,length) && tty_command_line[at]==45 {
    expected:[5][]const u8=["--child","", "space value", "quote\"slash\\", "日本語"]
    for argument in expected {
      expect_bytes(tty_command_line[at..at+#len(argument)],argument)
      if tty_command_line[at+#len(argument)]!=0 { #panic("handoff argv terminator") }
      at+=#len(argument)+1
    }
    value:[128]u8=[]
    result:=win_io_host.environment("DNA_HANDOFF",value[..])
    if !result.ok || !result.found { #panic("handoff environment") }
    expect_bytes(result.value,"session café 日本語")
    file:[]const u8="handoff-ok.txt\0"
    fd:=rec_open(&file[0],524481,384)
    if fd<0 || rec_close(fd)!=0 { #panic("handoff child acknowledgement") }
    return
  }
  kernel:=win_io_loader.open("kernel32.dll",0)
  allocate:=#cast(fn()i32,win_io_symbol(kernel.value,"AllocConsole"))
  release:=#cast(fn()i32,win_io_symbol(kernel.value,"FreeConsole"))
  standard:=#cast(fn(u32,rawptr)i32,win_io_symbol(kernel.value,"SetStdHandle"))
  write_input:=#cast(fn(rawptr,*const WinTtyRecord,u32,*u32)i32,win_io_symbol(kernel.value,"WriteConsoleInputW"))
  flush_input:=#cast(fn(rawptr)i32,win_io_symbol(kernel.value,"FlushConsoleInputBuffer"))
  handles:=#cast(fn(rawptr,*u32)i32,win_io_symbol(kernel.value,"GetProcessHandleCount"))
  sleep:=#cast(fn(u32),win_io_symbol(kernel.value,"Sleep"))
  original_input:=win_tty_api.standard(4294967286)
  original_output:=win_tty_api.standard(4294967285)
  // CI usually starts without a console. If attached, detach only this fixture
  // process before creating its isolated console; the parent remains untouched.
  _=release()
  if allocate()==0 { #panic("isolated console allocation") }
  input_name:[]const u8="CONIN$\0"
  output_name:[]const u8="CONOUT$\0"
  wide:[32]u16=[]
  if !win_io_path(&input_name[0],wide[..]) { #panic("console path") }
  input:=win_io_api.create(&wide[0],3221225472,3,nil,3,0,nil)
  if !win_io_path(&output_name[0],wide[..]) { #panic("console output path") }
  output:=win_io_api.create(&wide[0],3221225472,3,nil,3,0,nil)
  if #cast(isize,input)==-1 || #cast(isize,output)==-1 || standard(4294967286,input)==0 || standard(4294967285,output)==0 { #panic("isolated standard handles") }
  before_input:u32=0
  before_output:u32=0
  if win_tty_api.mode(input,&before_input)==0 || win_tty_api.mode(output,&before_output)==0 { #panic("saved console modes") }
  before_input_page:=win_tty_api.input_page()
  before_output_page:=win_tty_api.output_page()
  if !tty_enter_host() { #panic("console enter") }
  sync.store_u32(&tty_active,1)
  if tty_suspend_host()!=0 { #panic("Windows suspend unsupported") }
  mode:u32=0
  if win_tty_api.mode(input,&mode)==0 || (mode&7)!=0 || (mode&512)==0 || win_tty_api.input_page()!=65001 || win_tty_api.output_page()!=65001 { #panic("raw VT console mode") }
  _=flush_input(input)
  bytes:[64]u8=[]
  record:=WinTtyRecord{kind:1}
  key:=#cast(*WinTtyKey,&record.data[0])
  key.*=WinTtyKey{down:1,repeat:1,key:65,character:233}
  written:u32=0
  if write_input(input,&record,1,&written)==0 || tty_read_host(&bytes[0],64,100)!=2 { #panic("Unicode input") }
  expect_bytes(bytes[..2],"é")
  key.*=WinTtyKey{down:1,repeat:2,key:38,control:8}
  if write_input(input,&record,1,&written)==0 || tty_read_host(&bytes[0],64,100)!=12 { #panic("repeated modified arrow") }
  expect_bytes(bytes[..12],"\x1b[1;5A\x1b[1;5A")
  key.*=WinTtyKey{down:1,repeat:1,character:55357}
  _=write_input(input,&record,1,&written)
  key.character=56898
  _=write_input(input,&record,1,&written)
  if tty_read_host(&bytes[0],64,100)!=4 { #panic("surrogate input") }
  expect_bytes(bytes[..4],"🙂")
  key.*=WinTtyKey{down:0,repeat:1,key:65,character:65}
  _=write_input(input,&record,1,&written)
  start:=win_tty_api.ticks()
  if tty_read_host(&bytes[0],64,25)!=0 || win_tty_api.ticks()-start>500 { #panic("ignored key record deadline") }
  tty_wake_signal(nil)
  if tty_read_host(&bytes[0],64,100)!=-2 { #panic("wake-only read") }
  record.kind=4
  _=write_input(input,&record,1,&written)
  if tty_read_host(&bytes[0],64,100)!=-2 || sync.exchange_u32(&tty_resize_pending,0)!=1 { #panic("resize-only read") }
  _=flush_input(input)
  owner:=mem.arena_create(8192)
  worker:=thread.spawn_with_size(owner,1048576,read_worker,nil)
  if !worker.ok { #panic("pending reader thread") }
  for sync.load_u32(&read_started)==0 { sleep(1) }
  deadline:=win_tty_api.ticks()+1000
  for {
    win_io_sync.lock(&win_tty_lock)
    pending:=win_tty_readers!=0
    win_io_sync.unlock(&win_tty_lock)
    if pending { break }
    if win_tty_api.ticks()>=deadline { #panic("reader must enter pending wait") }
    sleep(1)
  }
  tty_leave_host()
  if !thread.join(worker.value).ok || (read_result!=-1 && read_result!=-2) { #panic("leave must release pending reader") }
  mem.arena_release(owner)
  if win_tty_api.mode(input,&mode)==0 || mode!=before_input || win_tty_api.input_page()!=before_input_page || win_tty_api.output_page()!=before_output_page { #panic("input mode and page restoration") }
  if win_tty_api.mode(output,&mode)==0 || mode!=before_output { #panic("output mode restoration") }
  before:u32=0
  after:u32=0
  if handles(win_tty_api.process(),&before)==0 { #panic("handle count") }
  for attempt in 0..64 {
    if !tty_enter_host() { #panic("console reenter") }
    _=flush_input(input)
    tty_wake_signal(nil)
    if tty_read_host(&bytes[0],64,100)!=-2 { #panic("wake reenter") }
    tty_leave_host()
  }
  if handles(win_tty_api.process(),&after)==0 || after!=before { #panic("console handle leak") }
  // Leave the restored console attached for the handoff child, exactly as the
  // real frontend switch does after terminating its TUI ownership.
  executable:=tty_executable_path()
  child:[]const u8="--child\0"
  empty:[]const u8="\0"
  spaced:[]const u8="space value\0"
  quoted:[]const u8="quote\"slash\\\0"
  unicode:[]const u8="日本語\0"
  arguments:[7]*const u8=[executable,&child[0],&empty[0],&spaced[0],&quoted[0],&unicode[0],nil]
  session:[]const u8="session café 日本語\0"
  if !tty_handoff_host(executable,&arguments[0],&session[0]) { #panic("frontend handoff") }
  parent_value:[128]u8=[]
  parent_environment:=win_io_host.environment("DNA_HANDOFF",parent_value[..])
  if !parent_environment.ok || !parent_environment.found { #panic("parent handoff environment") }
  expect_bytes(parent_environment.value,"parent value")
  _=standard(4294967286,original_input)
  _=standard(4294967285,original_output)
  _=win_io_api.close(input)
  _=win_io_api.close(output)
  _=release()
}
'''

compiler = real_dyn()
if compiler is None:
    raise SystemExit('Install the pinned Dyn SDK first.')
with tempfile.TemporaryDirectory(prefix='dna-tty-win-') as temporary:
    stage = Path(temporary)
    bridge = stage / 'native'
    bridge.mkdir()
    for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
        shutil.copytree(ROOT / 'src' / module, bridge / module)
    for name in ('rec_io_windows.dyn', 'tty_windows.dyn'):
        shutil.copyfile(ROOT / 'src/native/dyn' / name, bridge / name)
    (bridge / 'main.dyn').write_text(SOURCE, encoding='utf-8')
    environment = sdk_environment(compiler)
    for target in ('x86_64-windows', 'aarch64-windows'):
        for mode in ('debug', 'release'):
            subprocess.run([str(compiler), 'build', str(bridge), '--' + mode,
                '--target', target, '--emit-object', '--no-link', '--output',
                str(stage / (target + '-' + mode))], env=environment, check=True, timeout=120)
        print('PASS Windows console objects: ' + target, flush=True)
    if os.name != 'nt':
        print('UNAVAILABLE Windows runtime; objects do not qualify console behavior')
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
    environment['DNA_HANDOFF'] = 'parent value'
    for mode in ('debug', 'release'):
        binary = stage / ('tty-' + mode + '.exe')
        subprocess.run([str(compiler), 'build', str(bridge), '--' + mode,
            '--output', str(binary)], env=environment, check=True, timeout=120)
        working = stage / ('café 日本語-' + mode)
        working.mkdir()
        subprocess.run([str(binary)], cwd=working, env=environment, check=True, timeout=60)
        assert (working / 'handoff-ok.txt').exists()
        print('PASS Windows native console mode restoration, Unicode/keys, wake, resize, '
              'bounded ignored input, pending-read stop, reenter, handles and quoted handoff (' + mode + ')', flush=True)
