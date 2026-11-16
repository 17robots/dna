#!/usr/bin/env python3
"""Bounded Windows adapter regression with a substituted process wrapper.

Runs production host/Windows adapter source on the build host, removing only
Windows target/link directives and substituting std/process. This proves name
rejection precedes wrapper invocation; it does not run the native Windows runtime.
DYN may select a compiler; the default is the adjacent migration SDK build.
"""
import os
import shutil
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get('DYN', str(ROOT.parent / 'dyn/compiler/build/dyn-release'))

with tempfile.TemporaryDirectory(prefix='dna-host-environment-') as directory:
    stage = Path(directory)
    host = stage / 'host'
    host.mkdir()
    for module in ("owned_arena", "cstring"):
        shutil.copytree(ROOT / "src" / module, stage / module)
    (host / 'host.dyn').write_text((ROOT / 'src/host/host.dyn').read_text())
    adapter = (ROOT / 'src/host/windows.dyn').read_text()
    adapter = adapter.replace('#target(kernel: windows)\n', '').replace('#link("kernel32")\n', '')
    adapter = adapter.replace('use process "std/process"', 'use process "../process"')
    (host / 'windows.dyn').write_text(adapter)
    process = stage / 'process'
    process.mkdir()
    (process / 'process.dyn').write_text('''use "std/mem"
use "std/io"
extern fn invoked "probe_invoked"() i32
pub fn environment(arena: *mem.Arena, name: []const u8) []u8!io.IoErr {
  _ = name
  mode := invoked()
  if mode == 0 { #panic("rejected name reached allocating wrapper") }
  if mode == 2 { fail io.linux_err(-5) }
  if mode == 3 { fail .NotFound }
  if mode == 4 {
    empty: []u8
    return empty
  }
  value := mem.push_bytes(arena, 3)
  value[0] = 97
  value[1] = 98
  value[2] = 99
  return value
}
pub fn arguments(arena: *mem.Arena) [][]const u8!io.IoErr {
  _ = arena
  empty: [][]const u8
  return empty
}
''')
    (stage / 'probe.c').write_text('''#include <stdlib.h>
#include <stdint.h>
/* Unrelated foreign adapter entry points must never run in this probe. */
uint32_t GetCurrentDirectoryW(uint32_t n, uint16_t *p) { __builtin_trap(); }
int32_t SetCurrentDirectoryW(const uint16_t *p) { __builtin_trap(); }
uint32_t GetCurrentProcessId(void) { __builtin_trap(); }
int32_t MultiByteToWideChar(uint32_t p, uint32_t f, const uint8_t *s, int32_t n, uint16_t *o, int32_t c) { __builtin_trap(); }
int32_t WideCharToMultiByte(uint32_t p, uint32_t f, const uint16_t *s, int32_t n, uint8_t *o, int32_t c, void *r, void *u) { __builtin_trap(); }
static int mode, calls;
void probe_set(int value) { mode = value; calls = 0; }
int probe_invoked(void) { ++calls; if (!mode) __builtin_trap(); return mode; }
int probe_calls(void) { return calls; }
''')
    subprocess.run(['cc', '-c', str(stage / 'probe.c'), '-o', str(stage / 'probe.o')], check=True, timeout=30)
    source = ['''use host "./host"
use "std/io"
extern fn set "probe_set"(mode: i32)
extern fn calls "probe_calls"() i32
fn rejected(name: []const u8, expected: io.IoErr) {
  set(0)
  output: [4]u8 = [90,90,90,90]
  _ = host.environment(name, output[..3]) catch err {
    if calls() != 0 { #panic("rejection reached wrapper") }
    case expected {
      .Capacity => {
        case err {
          .Capacity => {}
          _ => { #panic("expected Capacity") }
        }
      }
      .InvalidInput => {
        case err {
          .InvalidInput => {}
          _ => { #panic("expected InvalidInput") }
        }
      }
      _ => { #panic("unexpected rejection expectation") }
    }
    for byte in output { if byte != 90 { #panic("rejected output changed") } }
    return
  }
  #panic("rejection succeeded")
}
fn accepted(name: []const u8) {
  set(1)
  output: [4]u8 = [90,90,90,90]
  result := host.environment(name, output[..3]) catch { #panic("accepted boundary") }
  if result.len != 3 || calls() != 1 { #panic("accepted boundary") }
  if &result[0] != &output[0] || output[0] != 97 || output[2] != 99 || output[3] != 90 { #panic("destination ownership") }
}
fn expect_err(name: []const u8, output: []u8, expected: i32) {
  _ = host.environment(name, output) catch err {
    case err {
      .Capacity => { if expected != 1 { #panic("unexpected Capacity") } }
      .System(code) => { if expected != 2 || code != -5 { #panic("unexpected System") } }
      .NotFound => { if expected != 3 { #panic("unexpected NotFound") } }
      _ => { #panic("unexpected err") }
    }
    return
  }
  #panic("expected error")
}
fn main() {''']
    # Raw byte arrays cover malformed sequences without relying on source decoding.
    for value in (b'\x80', b'\xc0\xaf', b'\xe0\x80\x80', b'\xed\xa0\x80', b'\xf4\x90\x80\x80', b'\xf0\x9f\x98', b'a\xff'):
        source += [f'  bad{len(source)}: [{len(value)}]u8 = [{",".join(map(str, value))}]', f'  rejected(bad{len(source)}[..], io.IoErr.Capacity)']
    source += ['''  rejected("", io.IoErr.InvalidInput)
  rejected("a=b", io.IoErr.InvalidInput)
  nul: [3]u8 = [97,0,98]
  rejected(nul[..], io.IoErr.InvalidInput)
  ascii: [32768]u8
  for i in 0..32768 { ascii[i] = 97 }
  accepted(ascii[..32767])
  rejected(ascii[..], io.IoErr.Capacity)
  bmp: [98304]u8
  for i in 0..32768 { bmp[i*3] = 226
    bmp[i*3+1] = 130
    bmp[i*3+2] = 172 }
  accepted(bmp[..98301])
  rejected(bmp[..], io.IoErr.Capacity)
  astral: [65537]u8
  for i in 0..16384 { astral[i*4] = 240
    astral[i*4+1] = 159
    astral[i*4+2] = 152
    astral[i*4+3] = 128 }
  accepted(astral[..65532])
  astral[65532] = 97
  accepted(astral[..65533])
  astral[65532] = 240
  rejected(astral[..65536], io.IoErr.Capacity)
  output: [4]u8 = [90,90,90,90]
  for capacity in 0..3 {
    set(1)
    expect_err("valid", output[..capacity], 1)
    if calls() != 1 { #panic("short output calls") }
    for byte in output { if byte != 90 { #panic("short output overwritten") } }
  }
  set(2)
  expect_err("valid", output[..], 2)
  if calls() != 1 { #panic("native diagnostic calls") }
  set(3)
  expect_err("valid", output[..0], 3)
  if calls() != 1 { #panic("missing calls") }
  set(4)
  empty := host.environment("valid", output[..0]) catch { #panic("empty") }
  if empty.len != 0 || calls() != 1 { #panic("empty") }
}''']
    (stage / 'main.dyn').write_text('\n'.join(source))
    for mode in ('debug', 'release'):
        binary = stage / ('check-' + mode)
        subprocess.run([DYN, 'build', str(stage), '--' + mode, '--link', str(stage / 'probe.o'), '--output', str(binary)], check=True, timeout=120)
        subprocess.run([str(binary)], check=True, timeout=5)
# Keep target-selected imports honest as well as the mocked Windows behavior.
with tempfile.TemporaryDirectory(prefix='dna-host-targets-') as directory:
    stage = Path(directory)
    for module in ('host', 'owned_arena', 'cstring'):
        shutil.copytree(ROOT / 'src' / module, stage / module)
    (stage / 'main.dyn').write_text('use host "./host"\nfn main() { storage: [32]u8\n _ = host.environment("PATH", storage[..]) catch storage[..0] }\n')
    for target in ('x86_64-macos', 'aarch64-macos', 'x86_64-windows', 'aarch64-windows'):
        subprocess.run([DYN, 'check', str(stage), '--target', target], check=True, timeout=120)
print('PASS Windows environment preflight, UTF-16 boundaries, diagnostics and bounded borrowed output (mock wrapper; no native Windows runtime)')
