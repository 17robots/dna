#!/usr/bin/env python3
"""Actual LSP JSON helper regression; no editor/native adapters required."""
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get('DYN', str(ROOT.parent / 'dyn/compiler/build/dyn-release'))


def bytes_literal(value):
    return '[' + ','.join(str(byte) for byte in value) + ']'


source = (ROOT / 'src/language_server.dyn').read_text()
helpers = source[source.index('// Preflight the complete encoding'):source.index('extern fn rpc_open')]
fixture = '''use "std/encoding/json"
use "std/mem"
use "std/io"
use "std/thread"
use "./buffer" buffer
''' + helpers + '''
fn same(a: []const u8, b: []const u8) bool {
  if #len(a) != #len(b) { return false }
  for index in 0..#len(a) { if a[index] != b[index] { return false } }
  return true
}
fn unchanged(value: []const u8) {
  for byte in value { if byte != 165 { #panic("failed encoding changed backing") } }
}
fn check_string(input: []const u8, expected: []const u8) {
  output: [1024]u8
  for index in 0..#len(output) { output[index] = 165 }
  for capacity in [#cast(usize, 0), #len(expected) - 1] {
    if #len(lsp_json_string(output[..capacity], input)) != 0 { #panic("short output accepted") }
    unchanged(output[..])
  }
  encoded := lsp_json_string(output[..#len(expected)], input)
  if !same(encoded, expected) || &encoded[0] != &output[0] { #panic("string exact-fit encoding") }
  unchanged(output[#len(expected)..])
}
fn check_value(input: []const u8, expected: []const u8) {
  arena := mem.arena_create(4096)
  defer mem.arena_release(arena)
  parsed := json.parse(arena, input)
  if !parsed.ok { #panic("invalid test input") }
  output: [1024]u8
  for index in 0..#len(output) { output[index] = 165 }
  if #len(lsp_json_encode(output[..#len(expected) - 1], parsed.root)) != 0 { #panic("short nested output accepted") }
  unchanged(output[..])
  if !same(lsp_json_encode(output[..#len(expected)], parsed.root), expected) { #panic("nested exact-fit encoding") }
  unchanged(output[#len(expected)..])
}
fn aliased(input: []const u8) {
  output: [128]u8
  for index in 0..#len(output) { output[index] = 165 }
  _ = mem.move(output[4..], input)
  saved := output
  if #len(lsp_json_string(output[..64], output[4..4 + #len(input)])) != 0 { #panic("alias accepted") }
  if !same(output[..], saved[..]) { #panic("alias modified backing") }
  if #len(lsp_json_string(output[5..64], output[4..4 + #len(input)])) != 0 || !same(output[..], saved[..]) { #panic("reverse alias") }
  value := json.Value{ kind: json.KindNumber, text: output[4..4 + #len(input)] }
  if #len(lsp_json_encode(output[..64], &value)) != 0 || !same(output[..], saved[..]) { #panic("number alias") }
  value = json.Value{ kind: json.KindObject }
  child := json.Value{ kind: json.KindNull, key: output[4..4 + #len(input)] }
  value.first = &child
  if #len(lsp_json_encode(output[..64], &value)) != 0 || !same(output[..], saved[..]) { #panic("key alias") }
}
fn main() {
  arena := mem.arena_create(#sizeof(buffer.Document) + 4096)
  defer mem.arena_release(arena)
  document := buffer.allocate(arena)
  defer buffer.release(document)
  if !buffer.load(document, "a\\\"\\\\\\n\\té😀") { #panic("document fixture") }
  expected: []const u8 = "\\\"a\\\\\\\"\\\\\\\\\\\\n\\\\té😀\\\""
  encoded: [128]u8
  if !same(lsp_json_document(encoded[..#len(expected)], document, 0, document.length), expected) { #panic("document JSON exact fit") }
  if #len(lsp_json_document(encoded[..#len(expected) - 1], document, 0, document.length)) != 0 { #panic("document JSON short output") }
  if #len(lsp_json_document(encoded[..0], document, 0, document.length)) != 0 { #panic("document JSON empty output") }
  // Past LspParallelEscape the encoder splits across threads; slices meet at
  // arbitrary bytes, so the result must still match the serial encoding.
  large_arena := mem.arena_create(160000000)
  defer mem.arena_release(large_arena)
  large := mem.push_bytes_uninit(large_arena, 20000003)
  pattern: [10]u8 = [97, 98, 34, 92, 10, 9, 1, 195, 169, 122]
  for index in 0..#len(large) { large[index] = pattern[index % 10] }
  large_document := buffer.allocate(large_arena)
  defer buffer.release(large_document)
  if !buffer.load(large_document, large) { #panic("large fixture") }
  parallel := mem.push_bytes_uninit(large_arena, #len(large) * 6 + 2)
  serial := mem.push_bytes_uninit(large_arena, #len(large) * 6 + 2)
  whole := lsp_json_document(parallel, large_document, 0, large_document.length)
  serial_used: usize = 1
  serial[0] = '"'
  serial_used += lsp_escape(&serial[1], large)
  serial[serial_used] = '"'
  if #len(whole) == 0 || !same(whole, serial[..serial_used + 1]) { #panic("parallel document JSON") }
  if #len(lsp_json_document(parallel[..#len(whole) - 1], large_document, 0, large_document.length)) != 0 { #panic("parallel short output") }
'''
strings = ['', 'plain', 'a"b\\c\n\r\t\b\f', ''.join(chr(i) for i in range(32)), 'é😀']
for index, value in enumerate(strings):
    raw = value.encode()
    expected = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
    fixture += f'  string{index}: [{len(raw)}]u8 = {bytes_literal(raw)}\n  expected{index}: [{len(expected)}]u8 = {bytes_literal(expected)}\n  check_string(string{index}[..], expected{index}[..])\n'
for index, value in enumerate(({'outer': [None, True, False, 12, 'a\nb', {'x': 'é'}]}, [[], {}, [0, -12]], {})):
    encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
    fixture += f'  json{index}: [{len(encoded)}]u8 = {bytes_literal(encoded)}\n  check_value(json{index}[..], json{index}[..])\n'
for index, value in enumerate((b'raw', b'\n\t', bytes([1, 2, 3]), b'"\\')):
    fixture += f'  alias{index}: [{len(value)}]u8 = {bytes_literal(value)}\n  aliased(alias{index}[..])\n'
fixture += '''  output: [16]u8
  for index in 0..#len(output) { output[index] = 165 }
  invalid: [1]u8 = [255]
  if #len(lsp_json_string(output[..], invalid[..])) != 0 { #panic("invalid utf8 accepted") }
  unchanged(output[..])
  missing := json.Value{}
  if #len(lsp_json_encode(output[..], &missing)) != 0 { #panic("missing value accepted") }
  unchanged(output[..])
  state := LspJsonOutput{ bytes: output[..2], writing: true }
  rejected := lsp_json_write(#cast(rawptr, &state), "long")
  if rejected.status != io.Status.Error || rejected.transferred != 0 || state.used != 0 { #panic("callback partial failure") }
  unchanged(output[..])
  state.writing = false
  rejected = lsp_json_write(#cast(rawptr, &state), "long")
  if rejected.status != io.Status.Error || state.used != 0 { #panic("count callback failure") }
  unchanged(output[..])
  node_storage: [16]u64 = []
  node := #cast(*json.Value, &node_storage[0])
  node.* = json.Value{ kind: json.KindNull }
  before := node_storage
  if #len(lsp_json_encode((#cast(*u8, node))[..#sizeof(json.Value)], node)) != 0 { #panic("node alias accepted") }
  for index in 0..#len(before) { if before[index] != node_storage[index] { #panic("node alias changed metadata") } }
}
'''
with tempfile.TemporaryDirectory(prefix='dna-json-scratch-') as directory:
    stage = Path(directory)
    shutil.copytree(ROOT / 'src/buffer', stage / 'buffer')
    shutil.copytree(ROOT / 'src/owned_arena', stage / 'owned_arena')
    (stage / 'main.dyn').write_text(fixture)
    for mode in ('debug', 'release'):
        executable = stage / mode
        subprocess.run([DYN, 'build', str(stage), '--' + mode, '--output', str(executable)], check=True, timeout=120)
        result = subprocess.run([str(executable)], capture_output=True, timeout=15)
        if result.returncode or result.stdout or result.stderr:
            raise AssertionError((mode, result.returncode, result.stdout, result.stderr))
        print(f'PASS JSON scratch {mode}: exact capacity, nested values, escapes, aliases, untouched failure backing')
