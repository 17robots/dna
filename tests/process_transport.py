#!/usr/bin/env python3
"""Exercise the shared owned-process interface in debug and release."""
import os, shutil, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
stage=root/'build/test-process-transport'
stage.mkdir(parents=True,exist_ok=True)
for source in (root/'src/native/dyn').glob('*.dyn'):shutil.copyfile(source,stage/source.name)
(stage/'main.dyn').write_text('''fn main() {
  command: []const u8 = "/bin/cat\\0" directory: []const u8 = "/tmp\\0"
  first := proc_open(&command[0], &directory[0], false)
  if first.pid <= 0 { #panic("spawn direct") }
  second := proc_take(&first) proc_close(&first) proc_close(&first)
  if first.pid != 0 || first.input != -1 || second.pid <= 0 { #panic("transfer invalidates source") }
  text: []const u8 = "owned child" if proc_write(second.input, &text[0], #len(text)) != #cast(isize) #len(text) { #panic("child input") }
  _ = rec_close(second.input) second.input = -1
  output: [32]u8 = [] used: usize = 0 deadline := proc_ticks() + 2000
  for proc_ticks() < deadline && used < #len(text) {
    got := proc_read(second.output, &output[used], 32 - used)
    if got > 0 { used += #cast(usize) got }
    else if got != -11 && got != -4 { break }
  }
  if used != #len(text) { #panic("transferred child stays alive") }
  index: usize = 0 for index < used { if output[index] != text[index] { #panic("child bytes") } index += 1 }
  proc_close(&second) proc_close(&second)
  missing: []const u8 = "/dna-does-not-exist/invalid\\0"
  failed := proc_open(&command[0], &missing[0], false) if failed.pid != 0 { proc_close(&failed) #panic("bad cwd must fail synchronously") }
  // Standalone test process may safely close stdin; pipe creation must lift it.
  _ = rec_close(0)
  closed_stdio := proc_open(&command[0], &directory[0], false)
  if closed_stdio.pid <= 0 || closed_stdio.input < 3 || closed_stdio.output < 3 || closed_stdio.error < 3 { #panic("closed stdio") }
  if proc_write(closed_stdio.input, &text[0], #len(text)) != #cast(isize) #len(text) { #panic("closed stdio input") }
  proc_close(&closed_stdio)
}
''')
for mode in ('debug','release'):
    binary=stage/f'probe-{mode}'
    subprocess.run(['python3',str(root/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(stage),'--'+mode,'--output',str(binary),'--link',str(root/'build/deps/install/lib/libdna_native.so')],check=True)
    subprocess.run([str(binary)],check=True,timeout=5)
    print('PASS owned process transfer, idempotent invalidated close, spawn failure, closed stdio:',mode)
