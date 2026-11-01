#!/usr/bin/env python3
"""Qualify the exact frontend environment and CPU-clock Windows boundary."""
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
use "std/c"
use "./host" host
struct ThreadTime { seconds, nanoseconds: i64 }
fn main() {
  key := "DNA_FRONTEND_QUALIFICATION\0"
  first := "session café 日本語\0"
  second := "changed\0"
  if handoff_setenv(&key[0], &first[0], 1) != 0 { #panic("Unicode environment set") }
  storage: [4096]u8 = []
  value := host.environment(key[..#len(key)-1], storage[..])
  if !value.ok || !value.found || #len(value.value) != #len(first)-1 { #panic("Unicode environment read") }
  for at in 0..#len(value.value) {
    if value.value[at] != first[at] { #panic("Unicode environment bytes") }
  }
  if handoff_setenv(&key[0], &second[0], 0) != 0 { #panic("environment no-overwrite") }
  value = host.environment(key[..#len(key)-1], storage[..])
  if #len(value.value) != #len(first)-1 { #panic("environment must retain original") }
  if handoff_unsetenv(&key[0]) != 0 { #panic("environment removal") }
  value = host.environment(key[..#len(key)-1], storage[..])
  if !value.ok || value.found { #panic("removed environment") }
  thread_before := ThreadTime{}
  process_before := ThreadTime{}
  if thread_clock(3, &thread_before) != 0 || thread_clock(2, &process_before) != 0 { #panic("native CPU clocks") }
  total: u64 = 0
  for at in 0..1000000 { total = #wrap(total + #cast(u64, at)) }
  if total != 499999500000 { #panic("CPU clock workload") }
  thread_after := ThreadTime{}
  process_after := ThreadTime{}
  if thread_clock(3, &thread_after) != 0 || thread_clock(2, &process_after) != 0 || thread_clock(99, &thread_after) == 0 { #panic("CPU clock samples") }
  if thread_after.seconds < thread_before.seconds || process_after.seconds < process_before.seconds || thread_after.nanoseconds < 0 || thread_after.nanoseconds >= 1000000000 || process_after.nanoseconds < 0 || process_after.nanoseconds >= 1000000000 { #panic("CPU clock normalization") }
  _ = frontend_isatty(0)
  _ = frontend_isatty(1)
  _ = frontend_display_available()
}
'''
compiler = real_dyn()
with tempfile.TemporaryDirectory(prefix='dna-frontend-win-') as temporary:
    stage = Path(temporary)
    for module in ('host', 'cstring', 'owned_arena'):
        shutil.copytree(ROOT / 'src' / module, stage / module)
    shutil.copyfile(ROOT / 'src/c_windows.dyn', stage / 'c_windows.dyn')
    (stage / 'main.dyn').write_text(FIXTURE, encoding='utf-8')
    env = environment(compiler)
    for target in ('x86_64-windows', 'aarch64-windows'):
        for mode in ('debug', 'release'):
            subprocess.run([sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler), 'build', str(stage), '--'+mode,
                '--target', target, '--emit-object', '--no-link', '--output', str(stage/(target+'-'+mode))], env=env, check=True)
        print('PASS frontend Windows objects: '+target, flush=True)
    if os.name == 'nt':
        kits = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits/10/Lib'
        libraries = stage / 'lib'
        libraries.mkdir()
        for name, folder in (('kernel32', 'um'), ('ucrt', 'ucrt')):
            candidates = sorted(kits.glob('*/'+folder+'/x64/'+name+'.lib'))
            if not candidates:
                raise SystemExit('Windows SDK '+name+'.lib required')
            shutil.copyfile(candidates[-1], libraries/('lib'+name+'.dll.a'))
        env['DYN_LIBRARY_PATH'] = str(libraries)
        for mode in ('debug', 'release'):
            output = stage/(mode+'.exe')
            subprocess.run([sys.executable, str(ROOT/'scripts/compile.py'), str(compiler), 'build', str(stage), '--'+mode, '--output', str(output)], env=env, check=True)
            subprocess.run([str(output)], env=env, check=True, timeout=15)
            print('PASS native Windows frontend environment, CPU clocks and display ('+mode+')', flush=True)
