#!/usr/bin/env python3
"""Fault-inject pthread_join while exercising the production thread adapter."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'build/thread-join'
STAGE.mkdir(parents=True, exist_ok=True)
source = (ROOT / 'src/native/dyn/sync.dyn').read_text()
# The remainder initializes unrelated native subsystems; keep the full adapter.
source = source.split('// Dyn\'s current executable entry point')[0]
source = source.replace(
    'extern fn sync_thread_join "pthread_join"(thread: usize, result: rawptr) i32',
    '''extern fn actual_join "pthread_join"(thread: usize, result: rawptr) i32
failures: i32 = 0
fn sync_thread_join(thread: usize, result: rawptr) i32 {
  if failures != 0 {
    if failures > 0 { failures -= 1 }
    return 22
  }
  return actual_join(thread, result)
}''')
(STAGE / 'sync.dyn').write_text(source)
(STAGE / 'clock.dyn').write_text((ROOT / 'src/native/dyn/clock.dyn').read_text())
fixture = '\nuse "std/sync"\n#link("c")\nextern fn allocate "malloc"(size: usize) rawptr\nextern fn heap_free "free"(pointer: rawptr)\n \nstruct State { alive: sync.AtomicU32, done: sync.AtomicU32 }\nlive_records: u64 = 0\nfn rec_malloc(size: usize) rawptr {\n  pointer := allocate(size)\n  if pointer != nil { live_records += 1 }\n  return pointer\n}\nfn rec_free(pointer: rawptr) {\n  live_records -= 1\n  heap_free(pointer)\n}\nfn worker(pointer: rawptr) i32 {\n  state := #cast(*State, pointer)\n  _ = time.sleep(20000000)\n  if sync.load_u32(&state.alive) != 1 { #panic("worker state released before completion") }\n  sync.store_u32(&state.done, 1)\n  return 37\n}\npub fn test_join() {\n  for fault in [0, 1, -1] {\n    failures = fault\n    state := State{}\n    sync.store_u32(&state.alive, 1)\n    thread := dna_thread_create(worker, #cast(rawptr, &state))\n    if thread == nil { #panic("create failed") }\n    result: i32 = 0\n    dna_thread_join(thread, &result)\n    sync.store_u32(&state.alive, 0)\n    if result != 37 || sync.load_u32(&state.done) != 1 { #panic("join returned while worker still owns state") }\n    expected: u64 = 0\n    if fault == -1 { expected = 1 }\n    if live_records != expected { #panic("unjoined record lost or successful join leaked") }\n  }\n  // A later create retries persistent failures, reclaiming the original record.\n  failures = 0\n  state := State{}\n  sync.store_u32(&state.alive, 1)\n  thread := dna_thread_create(worker, #cast(rawptr, &state))\n  if thread == nil || live_records != 1 { #panic("retired record was not collected") }\n  dna_thread_join(thread, nil)\n  if live_records != 0 || sync_retired_threads != nil { #panic("thread storage leaked") }\n}\n\nstruct SelfState { thread: rawptr, ready: sync.AtomicU32 }\nfn self_worker(pointer: rawptr) i32 {\n  state := #cast(*SelfState, pointer)\n  for sync.load_u32(&state.ready) == 0 {\n    _ = time.sleep(time.Millisecond)\n  }\n  dna_thread_join(state.thread, nil)\n  #panic("self join returned")\n}\npub fn test_self_join() {\n  state := SelfState{}\n  state.thread = dna_thread_create(self_worker, #cast(rawptr, &state))\n  if state.thread == nil { #panic("create failed") }\n  sync.store_u32(&state.ready, 1)\n  dna_thread_join(state.thread, nil)\n}\n\n'
(STAGE / 'fixture.dyn').write_text(fixture)
for mode in ('debug', 'release'):
    binary = STAGE / mode
    subprocess.run(['python3', str(ROOT / 'scripts/compile.py'), os.environ.get('DYN', 'dyn'),
                    'build', str(STAGE), '--' + mode, '--shared', '--no-cache', '--output', str(binary)], check=True)
    subprocess.run(['python3', '-c', 'import ctypes; ctypes.CDLL(' + repr(str(binary)) + ').test_join()'], check=True, timeout=10)
    invalid = subprocess.run(['python3', '-c', 'import ctypes; ctypes.CDLL(' + repr(str(binary)) + ').test_self_join()'],
                             capture_output=True, timeout=10)
    assert invalid.returncode != 0 and b'cannot join the current native thread' in invalid.stderr, invalid.stderr
print('PASS thread joins: transient recovery, persistent retention, eventual reclamation')
