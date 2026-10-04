#!/usr/bin/env python3
"""Benchmark cleanup must stop LSP-like children in separate process groups."""
import os
from pathlib import Path
import select
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from compare_completion import Terminal

with tempfile.TemporaryDirectory(prefix='dna-benchmark-cleanup-') as temporary:
    directory = Path(temporary)
    child_code = '''
import os, signal, time
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_IGN)
Path('child.tmp').write_text(str(os.getpid()))
Path('child.tmp').replace('child.pid')
while True:
    Path('activity').write_text(str(time.monotonic()))
    time.sleep(.01)
'''
    parent_code = 'import subprocess, sys, time; subprocess.Popen([sys.executable, "-c", ' + repr(child_code) + '], start_new_session=True); time.sleep(30)'
    session = Terminal([sys.executable, '-c', parent_code], os.environ.copy(), directory)
    descriptor = None
    try:
        deadline = time.monotonic() + 5
        while not (directory / 'child.pid').exists():
            assert time.monotonic() < deadline, 'child startup timed out'
            time.sleep(.01)
        descriptor = os.pidfd_open(int((directory / 'child.pid').read_text()))
    finally:
        session.close()
    try:
        assert select.select([descriptor], [], [], 0)[0], 'separate-group child survived benchmark cleanup'
    finally:
        if descriptor is not None:
            os.close(descriptor)
print('PASS benchmark cleanup: separate-group child exited before fixture removal')
