#!/usr/bin/env python3
"""Measure the complete launch path to first frame, then quit normally.

Default: built editor. To include compilation: ... startup_latency.py dyn run src/ --timings
Dummy rendering isolates CPU startup; it does not measure desktop GPU/display latency.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
probe = ROOT / 'build/startup-latency.so'
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'startup_latency', str(probe)], check=True)
command = sys.argv[1:] or [str(ROOT / 'build/dna-debug')]
for trial in range(3):
    env = dict(os.environ, SDL_VIDEODRIVER=os.environ.get('SDL_VIDEODRIVER', 'dummy'), LD_PRELOAD=str(probe),
               LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'),
               DNA_STARTUP_BEGIN=str(time.monotonic()))
    env.pop('DYN_EDITOR_SMOKE', None)
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    match = re.search(r'DNA first frame ([\d.]+) ms', result.stderr)
    assert match, result.stderr
    print(f'Trial {trial + 1}: {result.stderr.strip()}', flush=True)
