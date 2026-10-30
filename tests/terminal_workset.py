#!/usr/bin/env python3
"""Production terminal scheduling queries visit terminal owners, not file buffers."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', type=Path, default=ROOT)
parser.add_argument('--expect-bounded', action='store_true')
args = parser.parse_args()
source = (args.source_root/'src/terminal.dyn').read_text()

def function(name):
    start = source.index('fn '+name+'(')
    at = source.index('{', start)
    depth = 1
    end = at+1
    while depth:
        depth += (source[end] == '{')-(source[end] == '}')
        end += 1
    body = source[start:end]
    for loop in ('for slot != nil {', 'for index in 0..#len(app.documents.slots) {'):
        body = body.replace(loop, loop+'\n    visits += 1')
    return body

helpers = ''
if 'fn terminal_track(' in source:
    helpers = function('terminal_track')+'\n'+function('terminal_untrack')
checks = ''
if helpers:
    checks = '''
  terminal_track(&app, &slots[79])
  terminal_track(&app, &slots[79])
  if app.terminal_state.first != &slots[79] || slots[79].terminal.next != nil { #panic("duplicate terminal tracking") }
'''
if args.expect_bounded:
    bounded = 'if idle != 0 { #panic("file buffers must not enter terminal queries") }'
else:
    bounded = ''
model = '''
struct TerminalState { handle: rawptr, owner: *App, previous, next: *Slot, escape_pending: bool, escape_time: u64 }
struct Slot { terminal: TerminalState }
struct Documents { slots: []*Slot }
struct TerminalUiState { first: *Slot }
struct App { documents: Documents, terminal_state: TerminalUiState }
visits: usize = 0
fn terminal_alive(handle: rawptr) i32 { if handle != nil { return 1 }; return 0 }
fn terminal_needs_poll(handle: rawptr) i32 { if handle != nil { return 1 }; return 0 }
'''.replace(';', '\n')+helpers+'\n'+ '\n'.join(function(name) for name in ('terminals_running','terminals_waiting_for_exit','terminal_escape_due'))
model += '''
fn main() {
  app := App{}
  slots: [80]Slot = []
  pointers: [80]*Slot = []
  for index in 0..80 { pointers[index] = &slots[index] }
  app.documents.slots = pointers[..]
  if terminals_running(&app) || terminals_waiting_for_exit(&app) || terminal_escape_due(&app) != 0 { #panic("empty terminal state") }
  idle := visits
  BOUNDED
  slots[79].terminal.handle = #cast(rawptr, 1)
  slots[79].terminal.escape_pending = true
  slots[79].terminal.escape_time = 100
  @TRACK@
  if !terminals_running(&app) || !terminals_waiting_for_exit(&app) || terminal_escape_due(&app) != 601 { #panic("live terminal state") }
  @UNTRACK@
}
'''.replace('BOUNDED',bounded).replace('@TRACK@',checks).replace('@UNTRACK@', '''
  terminal_untrack(&slots[79])
  if app.terminal_state.first != nil || slots[79].terminal.owner != nil { #panic("terminal detach") }
  terminal_untrack(&slots[79])
''' if helpers else '')
with tempfile.TemporaryDirectory(prefix='dna-terminal-workset-') as temporary:
    stage = Path(temporary)
    (stage/'main.dyn').write_text(model)
    for mode in ('debug', 'release'):
        binary = stage/mode
        subprocess.run([os.environ.get('DYN','dyn'),'build',str(stage),'--'+mode,'--output',str(binary)],check=True)
        subprocess.run([str(binary)],check=True,timeout=5)
print('PASS production terminal workset queries, duplicate ownership and detach')
