#!/usr/bin/env python3
"""The build guard must contain a child before it can exhaust host memory."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
guard = root / 'scripts/compile.py'
env = dict(os.environ, DNA_BUILD_MEMORY_MB='64')
small = subprocess.run([sys.executable, guard, sys.executable, '-c',
                        'x=bytearray(1024*1024); print("small allocation succeeded")'],
                       env=env, capture_output=True, text=True, timeout=10)
assert small.returncode == 0 and 'small allocation succeeded' in small.stdout, small.stderr
large = subprocess.run([sys.executable, guard, sys.executable, '-c',
                        'x=bytearray(160*1024*1024); print("escaped memory cap")'],
                       env=env, capture_output=True, text=True, timeout=10)
assert large.returncode != 0 and 'escaped memory cap' not in large.stdout, large
# Two builds must not run their payloads concurrently.
with tempfile.TemporaryDirectory() as directory:
    probe = Path(directory) / 'active'
    script = 'import os,time; p=' + repr(str(probe)) + '; f=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY); time.sleep(.1); os.close(f); os.unlink(p)'
    commands = [subprocess.Popen([sys.executable, guard, sys.executable, '-c', script], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
    for command in commands:
        out, err = command.communicate(timeout=10)
        assert command.returncode == 0, err
print('PASS build memory containment and serialization')
