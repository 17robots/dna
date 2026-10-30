#!/usr/bin/env python3
"""Production native synchronization ABI: predicate handoff, isolation and contention."""
import ctypes as c
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if os.environ.get('DNA_SYNC_CHILD') != '1':
    # Opaque SDK handles must never reach a remaining pthread mutex/condition
    # call, whose native layout would overrun the smaller SDK allocation.
    symbols = subprocess.check_output(
        ['nm', '-D', '--undefined-only', str(ROOT/'build/deps/install/lib/libdna_native.so')],
        text=True)
    names = [line.split()[-1].split('@')[0] for line in symbols.splitlines() if line.split()]
    assert not any(name.startswith(('pthread_mutex_', 'pthread_cond_')) or name == 'pthread_once'
                   for name in names), 'pthread synchronization remains after SDK migration'
    subprocess.run([sys.executable, __file__], check=True, timeout=25,
                   env=dict(os.environ, DNA_SYNC_CHILD='1'))
    raise SystemExit

lib = c.CDLL(str(ROOT/'build/deps/install/lib/libdna_native.so'))
entry = c.CFUNCTYPE(c.c_int, c.c_void_p)
for name in ('dna_mutex_create', 'dna_condition_create'):
    function = getattr(lib, name)
    function.argtypes = []
    function.restype = c.c_void_p
for name in ('dna_mutex_destroy', 'dna_mutex_lock', 'dna_mutex_unlock',
             'dna_condition_destroy', 'dna_condition_signal'):
    function = getattr(lib, name)
    function.argtypes = [c.c_void_p]
    function.restype = None
lib.dna_condition_wait.argtypes = [c.c_void_p, c.c_void_p]
lib.dna_condition_wait.restype = None
lib.dna_thread_create.argtypes = [entry, c.c_void_p]
lib.dna_thread_create.restype = c.c_void_p
lib.dna_thread_join.argtypes = [c.c_void_p, c.POINTER(c.c_int)]
lib.dna_thread_join.restype = None

# Exceptions cannot unwind safely through a ctypes callback. Record them for
# the owner; the outer process timeout also bounds deadlocks and lost wakeups.
failures = []
callbacks = []
def spawn(function, context=None):
    @entry
    def callback(argument):
        try:
            return function(argument)
        except BaseException as error:
            failures.append(repr(error))
            return -999
    callbacks.append(callback)
    thread = lib.dna_thread_create(callback, context)
    assert thread, 'native worker allocation'
    return thread

def join(thread, expected):
    status = c.c_int(-1000)
    lib.dna_thread_join(thread, c.byref(status))
    assert not failures, failures
    assert status.value == expected, (status.value, expected)

# Distinct live objects may be held simultaneously, including by one owner.
first = lib.dna_mutex_create()
second = lib.dna_mutex_create()
assert first and second and first != second
lib.dna_mutex_lock(first)
lib.dna_mutex_lock(second)
lib.dna_mutex_unlock(second)
lib.dna_mutex_unlock(first)
lib.dna_mutex_destroy(second)
lib.dna_mutex_destroy(first)

# Signal before the consumer begins waiting: the predicate, not a remembered
# signal, makes the worker proceed. Exercise a separate condition per lifetime.
for _ in range(12):
    lock = lib.dna_mutex_create()
    condition = lib.dna_condition_create()
    assert lock and condition
    predicate = c.c_int(0)
    lib.dna_mutex_lock(lock)
    def early_worker(unused):
        lib.dna_mutex_lock(lock)
        while not predicate.value:
            lib.dna_condition_wait(condition, lock)
        lib.dna_mutex_unlock(lock)
        return 17
    thread = spawn(early_worker)
    predicate.value = 1
    lib.dna_condition_signal(condition)
    lib.dna_mutex_unlock(lock)
    join(thread, 17)
    lib.dna_condition_destroy(condition)
    lib.dna_mutex_destroy(lock)

# Bidirectional rendezvous. The worker announces readiness while holding the
# lock and atomically releases it in wait; the owner then changes the predicate.
# Repeated handoffs prove that wait reacquires the same mutex on return.
lock = lib.dna_mutex_create()
changed = lib.dna_condition_create()
acknowledged = lib.dna_condition_create()
assert lock and changed and acknowledged
sent = c.c_int(0)
received = c.c_int(0)
rounds = 100
def receiver(unused):
    lib.dna_mutex_lock(lock)
    for expected in range(1, rounds+1):
        while sent.value < expected:
            lib.dna_condition_wait(changed, lock)
        assert sent.value == expected
        received.value = expected
        lib.dna_condition_signal(acknowledged)
    lib.dna_mutex_unlock(lock)
    return 23
thread = spawn(receiver)
lib.dna_mutex_lock(lock)
for expected in range(1, rounds+1):
    sent.value = expected
    lib.dna_condition_signal(changed)
    while received.value < expected:
        lib.dna_condition_wait(acknowledged, lock)
    assert received.value == expected
lib.dna_mutex_unlock(lock)
join(thread, 23)
lib.dna_condition_destroy(acknowledged)
lib.dna_condition_destroy(changed)
lib.dna_mutex_destroy(lock)

# Release the Python GIL between read and write so the Python callback does
# not accidentally serialize this counter test in place of the native mutex.
lock = lib.dna_mutex_create()
assert lock
counter = c.c_int64(0)
workers, iterations = 6, 300
def increment(unused):
    for _ in range(iterations):
        lib.dna_mutex_lock(lock)
        previous = counter.value
        time.sleep(0)
        counter.value = previous+1
        lib.dna_mutex_unlock(lock)
    return 31
threads = [spawn(increment) for _ in range(workers)]
for thread in threads:
    join(thread, 31)
assert counter.value == workers*iterations, counter.value
lib.dna_mutex_destroy(lock)
print('PASS native sync ABI: independent mutexes, predicate before wait, repeated condition handoff, reacquisition and contended counter')
