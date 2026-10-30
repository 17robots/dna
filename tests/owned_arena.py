#!/usr/bin/env python3
"""Qualify fixed-capacity ownership over SDK pointer handles."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get('DYN', 'dyn')
SOURCE = r'''use "./owned_arena" owner
use "./cstring" cstring
use "std/mem"
fn check(ok: bool) { if !ok { #panic("arena ownership contract") } }
fn main() {
  check(owner.try_create(#cast(usize, -1)) == nil)
  check(owner.try_create(#cast(usize, -1) - 4095) == nil)
  arena := owner.try_create(3145728)
  check(arena != nil)
  check(mem.arena_used(arena) == 0 && mem.arena_capacity(arena) == 3145728)
  bytes := mem.push_bytes_uninit(arena, 2500000)
  bytes[0] = 11
  bytes[2499999] = 99
  check(bytes[0] == 11 && bytes[2499999] == 99)
  // A nonoverflowing but impossible reservation must preserve an existing owner.
  // LINUX_RESERVATION_CHECK
  mem.arena_reset(arena)
  check(mem.arena_used(arena) == 0)
  again := mem.push_bytes_uninit(arena, 2500000)
  check(&again[0] == &bytes[0])
  transferred := arena
  arena = nil
  owner.release(arena)
  owner.release(transferred)
  lazy := owner.create(0)
  check(mem.arena_used(lazy) == 0)
  _ = mem.push_bytes_uninit(lazy, 32)
  owner.release(lazy)
  storage: [5]u8 = [7,7,7,7,7]
  check(!cstring.bounded(storage[..], "large").ok && storage[0] == 7)
  check(!cstring.bounded(storage[..], "a\0b").ok && storage[0] == 7)
  check(cstring.bounded(storage[..], "text").ok && storage[4] == 0)
}
'''
with tempfile.TemporaryDirectory(prefix='dna-arena-') as directory:
    work = Path(directory)
    for module in ('owned_arena', 'cstring'):
        shutil.copytree(ROOT / 'src' / module, work / module)
    native_source = SOURCE
    if os.uname().sysname == 'Linux':
        native_source = SOURCE.replace('// LINUX_RESERVATION_CHECK', 'check(owner.try_create(#cast(usize, 1) << 62) == nil)\n  check(bytes[0] == 11 && bytes[2499999] == 99 && mem.arena_used(arena) == 2500000)')
    (work / 'main.dyn').write_text(native_source)
    for mode in ('debug', 'release'):
        output = work / mode
        subprocess.run([DYN, 'build', str(work), '--' + mode, '--output', str(output)], check=True, timeout=300)
        subprocess.run([str(output)], check=True, timeout=60)
    (work / 'main.dyn').write_text(SOURCE)
    for target in ('aarch64-linux', 'riscv64-linux', 'x86_64-macos', 'aarch64-macos', 'x86_64-windows', 'aarch64-windows'):
        output = work / target
        subprocess.run([DYN, 'build', str(work), '--release', '--target', target, '--output', str(output)], check=True, timeout=300)
        emulator = {'aarch64-linux': 'qemu-aarch64', 'riscv64-linux': 'qemu-riscv64', 'x86_64-windows': 'wine'}.get(target)
        if emulator and shutil.which(emulator):
            subprocess.run([emulator, str(output)], check=True, timeout=120)
print('PASS transferable arena ownership, zero marks, reset, demand commitment, release and bounded C strings')
