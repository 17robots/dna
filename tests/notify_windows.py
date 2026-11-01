#!/usr/bin/env python3
"""Compile production Windows readiness; native hosts exercise one-shot lifecycle."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn
from sdk_compat import environment

FIXTURE = r'''
#link("ucrt")
use "std/sync"
use "std/time"
extern fn rec_malloc "malloc"(size: usize) *u8
extern fn rec_free "free"(value: rawptr)
fn native_initialize() {}
fn dna_tty_wake() {}
struct PollDescriptor { fd: i32, events, returned: i16 }
ready: sync.AtomicU32
received: sync.AtomicU32
fn proc_poll(descriptors: *PollDescriptor, count: usize, timeout: i32) i32 {
  if count != 1 || timeout != 0 { #panic("notification probe must not block") }
  if sync.load_u32(&ready) != 0 {
    descriptors.returned = descriptors.events
    return 1
  }
  return 0
}
fn callback(context: rawptr) { _ = context
  sync.store_u32(&received, sync.load_u32(&received) + 1)
}
fn wait_received(expected: u32) {
  for attempt in 0..500 {
    if sync.load_u32(&received) >= expected { return }
    _ = time.sleep(1000000)
  }
  #panic("readiness delivery timed out")
}
fn main() {
  dna_native_gui_attach(callback, nil)
  for cycle in 0..10 {
    sync.store_u32(&received, 0)
    sync.store_u32(&ready, 1)
    if dna_notify_start() != 1 || dna_notify_start() != 0 { #panic("notification start ownership") }
    dna_watch(7, 0)
    wait_received(1)
    _ = time.sleep(40000000)
    if sync.load_u32(&received) != 1 { #panic("registration must be one-shot") }
    dna_watch(7, 0)
    wait_received(2)
    dna_unwatch(7)
    _ = time.sleep(40000000)
    if sync.load_u32(&received) != 2 { #panic("unwatch must retire registration") }
    dna_notify_stop()
    dna_notify()
    if sync.load_u32(&received) != 2 { #panic("stop must disable callbacks") }
    dna_notify_stop()
  }
  dna_native_gui_attach(nil, nil)
}
'''

def main():
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first')
    env = environment(compiler)
    with tempfile.TemporaryDirectory(prefix='dna-windows-notify-') as temporary:
        stage = Path(temporary)
        native = ROOT / 'src/native/dyn'
        for name in ('notify_windows.dyn', 'notify_gui.dyn', 'sync_desktop.dyn', 'sync_windows.dyn'):
            shutil.copyfile(native / name, stage / name)
        (stage / 'sync.dyn').write_text((native / 'sync.dyn').read_text(encoding="utf-8").split("// Dyn's current executable entry point", 1)[0], encoding="utf-8")
        (stage / 'main.dyn').write_text(FIXTURE, encoding="utf-8")
        for target in ('x86_64-windows', 'aarch64-windows'):
            for mode in ('debug', 'release'):
                output = stage / (target + '-' + mode)
                subprocess.run([sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler),
                                'build', str(stage), '--' + mode, '--target', target,
                                '--emit-object', '--no-link', '--output', str(output)], env=env, check=True)
            print('PASS Windows readiness objects: ' + target, flush=True)
        if os.name == 'nt':
            kits = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits/10/Lib'
            libraries = stage / 'lib'
            libraries.mkdir()
            for name, folder in (('kernel32', 'um'), ('ucrt', 'ucrt')):
                candidates = sorted(kits.glob('*/' + folder + '/x64/' + name + '.lib'))
                if not candidates:
                    raise SystemExit('Windows SDK x64 ' + name + '.lib is required.')
                shutil.copyfile(candidates[-1], libraries / ('lib' + name + '.dll.a'))
            env['DYN_LIBRARY_PATH'] = str(libraries)
            for mode in ('debug', 'release'):
                output = stage / (mode + '.exe')
                subprocess.run([sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler),
                                'build', str(stage), '--' + mode, '--output', str(output)], env=env, check=True)
                subprocess.run([str(output)], env=env, check=True, timeout=15)
                print('PASS Windows readiness: one-shot/rearm/unwatch/stop/restart (' + mode + ')', flush=True)
        else:
            print('Native Windows readiness runtime still requires a Windows host', flush=True)

if __name__ == '__main__':
    main()
