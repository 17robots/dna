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
fixture = r'''
use "std/sync" native_atomic
#link("c")
extern fn allocate "malloc"(size: usize) rawptr
extern fn heap_free "free"(pointer: rawptr)
 
struct State { alive: native_atomic.AtomicU32, done: native_atomic.AtomicU32 }
live_records: u64 = 0
fn rec_malloc(size: usize) rawptr {
  pointer := allocate(size)
  if pointer != nil { live_records += 1 }
  return pointer
}
fn rec_free(pointer: rawptr) {
  live_records -= 1
  heap_free(pointer)
}
fn worker(pointer: rawptr) i32 {
  state := #cast(*State) pointer
  delay := NativeTimespec{nanoseconds: 20000000}
  _ = #syscall(35, &delay, 0)
  if native_atomic.load_u32(&state.alive) != 1 { #panic("worker state released before completion") }
  native_atomic.store_u32(&state.done, 1)
  return 37
}
pub fn test_join() {
  for fault in [0, 1, -1] {
    failures = fault
    state := State{}
    native_atomic.store_u32(&state.alive, 1)
    thread := dna_thread_create(&worker, #cast(rawptr) &state)
    if thread == nil { #panic("create failed") }
    result: i32 = 0
    dna_thread_join(thread, &result)
    native_atomic.store_u32(&state.alive, 0)
    if result != 37 || native_atomic.load_u32(&state.done) != 1 { #panic("join returned while worker still owns state") }
    expected: u64 = 0
    if fault == -1 { expected = 1 }
    if live_records != expected { #panic("unjoined record lost or successful join leaked") }
  }
  // A later create retries persistent failures, reclaiming the original record.
  failures = 0
  state := State{}
  native_atomic.store_u32(&state.alive, 1)
  thread := dna_thread_create(&worker, #cast(rawptr) &state)
  if thread == nil || live_records != 1 { #panic("retired record was not collected") }
  dna_thread_join(thread, nil)
  if live_records != 0 || sync_retired_threads != nil { #panic("thread storage leaked") }
}

struct SelfState { thread: rawptr, ready: native_atomic.AtomicU32 }
fn self_worker(pointer: rawptr) i32 {
  state := #cast(*SelfState) pointer
  for native_atomic.load_u32(&state.ready) == 0 {
    delay := NativeTimespec{nanoseconds: 1000000}
    _ = #syscall(35, &delay, 0)
  }
  dna_thread_join(state.thread, nil)
  #panic("self join returned")
}
pub fn test_self_join() {
  state := SelfState{}
  state.thread = dna_thread_create(&self_worker, #cast(rawptr) &state)
  if state.thread == nil { #panic("create failed") }
  native_atomic.store_u32(&state.ready, 1)
  dna_thread_join(state.thread, nil)
}

'''
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
