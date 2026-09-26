#!/usr/bin/env python3
"""Bounded background command transport: real pipes, cancellation and failures."""
import ctypes as c
import os
from pathlib import Path
import time

root = Path(__file__).resolve().parents[1]
lib = c.CDLL(str(root / 'build/deps/install/lib/libdna_native.so'))
lib.dna_job_open.argtypes = [c.c_char_p, c.c_char_p, c.c_void_p, c.c_size_t, c.c_uint]
lib.dna_job_open.restype = c.c_void_p
lib.dna_job_status.argtypes = [c.c_void_p]
for name in ('dna_job_output', 'dna_job_error'):
    fn = getattr(lib, name)
    fn.argtypes = [c.c_void_p, c.c_void_p, c.c_size_t]
    fn.restype = c.c_size_t
lib.dna_job_close.argtypes = [c.c_void_p]

def run(command, data=b'', timeout=2000):
    job = lib.dna_job_open(command, b'/tmp', data, len(data), timeout)
    assert job
    try:
        deadline = time.monotonic() + 4
        while lib.dna_job_status(job) == 1:
            assert time.monotonic() < deadline
            time.sleep(.002)
        output = c.create_string_buffer(268435456)
        error = c.create_string_buffer(4096)
        n = lib.dna_job_output(job, output, len(output))
        e = lib.dna_job_error(job, error, len(error))
        return lib.dna_job_status(job), output.raw[:n], error.raw[:e]
    finally:
        lib.dna_job_close(job)

assert run(b'cat', b'ab\n' * 300000) == (2, b'ab\n' * 300000, b'')
assert run(b'tr a-z A-Z', b'hello') == (2, b'HELLO', b'')
assert run(b'printf failure >&2; exit 7') == (3, b'', b'failure')
# Output past buffer.Capacity (256 MiB) is an overflow.
assert run(b'head -c 268435456 /dev/zero')[0] == 4
assert run(b'sleep 10', timeout=50)[0] == 5
# A child keeping pipes open must still be bounded after its shell exits.
assert run(b'sleep 10 & exit 0', timeout=50)[0] == 5
before = len(os.listdir('/proc/self/fd'))
for _ in range(20):
    started = time.monotonic()
    job = lib.dna_job_open(b'sleep 10', b'/tmp', b'', 0, 10000)
    assert job
    lib.dna_job_close(job)
    assert time.monotonic() - started < .5
assert len(os.listdir('/proc/self/fd')) == before
print('PASS background jobs: large pipes, failure, limits, timeout, descendants, cancellation, descriptor cleanup')
