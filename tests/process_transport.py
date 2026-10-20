#!/usr/bin/env python3
"""Exercise the shared owned-process interface in debug and release."""
import os, shutil, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
stage=root/'build/test-process-transport'
stage.mkdir(parents=True,exist_ok=True)
for source in (root/'src/native/dyn').glob('*.dyn'):shutil.copyfile(source,stage/source.name)
(stage/'main.dyn').write_text('fn main() {\n  command: []const u8 = "/bin/cat\\0"\n  directory: []const u8 = "/tmp\\0"\n  first := proc_open(&command[0], &directory[0], false)\n  if first.pid <= 0 { #panic("spawn direct") }\n  second := proc_take(&first)\n  proc_close(&first)\n  proc_close(&first)\n  if first.pid != 0 || first.input != -1 || second.pid <= 0 { #panic("transfer invalidates source") }\n  text: []const u8 = "owned child"\n  if proc_write(second.input, &text[0], #len(text)) != #cast(isize, #len(text)) { #panic("child input") }\n  _ = rec_close(second.input)\n  second.input = -1\n  output: [32]u8 = []\n  used: usize = 0\n  deadline := proc_ticks() + 2000\n  for proc_ticks() < deadline && used < #len(text) {\n    got := proc_read(second.output, &output[used], 32 - used)\n    if got > 0 { used += #cast(usize, got) }\n    else if got != -11 && got != -4 { break }\n  }\n  if used != #len(text) { #panic("transferred child stays alive") }\n  index: usize = 0\n  for index < used { if output[index] != text[index] { #panic("child bytes") }\n    index += 1 }\n  proc_close(&second)\n  proc_close(&second)\n  missing: []const u8 = "/dna-does-not-exist/invalid\\0"\n  failed := proc_open(&command[0], &missing[0], false)\n  if failed.pid != 0 { proc_close(&failed)\n    #panic("bad cwd must fail synchronously") }\n  // Standalone test process may safely close stdin; pipe creation must lift it.\n  _ = rec_close(0)\n  closed_stdio := proc_open(&command[0], &directory[0], false)\n  if closed_stdio.pid <= 0 || closed_stdio.input < 3 || closed_stdio.output < 3 || closed_stdio.error < 3 { #panic("closed stdio") }\n  if proc_write(closed_stdio.input, &text[0], #len(text)) != #cast(isize, #len(text)) { #panic("closed stdio input") }\n  proc_close(&closed_stdio)\n}\n')
for mode in ('debug','release'):
    binary=stage/f'probe-{mode}'
    subprocess.run(['python3',str(root/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(stage),'--'+mode,'--output',str(binary),'--link',str(root/'build/deps/install/lib/libdna_native.so')],check=True)
    subprocess.run([str(binary)],check=True,timeout=5)
    print('PASS owned process transfer, idempotent invalidated close, spawn failure, closed stdio:',mode)
