#!/usr/bin/env python3
"""An unchanged local watched directory must not cause periodic file stat calls."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
subprocess.run(['python3',str(ROOT/'scripts/native_test.py'),'disk_idle',str(ROOT/'build/disk-idle'),'--executable'],check=True)
with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'file';path.write_text('idle')
    subprocess.run([str(ROOT/'build/disk-idle'),str(path)],check=True,timeout=5)

# Failure to establish filesystem notifications must retain polling correctness.
with tempfile.TemporaryDirectory() as tmp:
    probe=Path(tmp)/'fallback.so'
    subprocess.run(['python3',str(ROOT/'scripts/native_test.py'),'disk_fallback',str(probe)],check=True)
    subprocess.run(['python3',str(ROOT/'tests/disk.py')],env=dict(os.environ,LD_PRELOAD=str(probe)),check=True,timeout=15)
    print('PASS disk polling fallback when inotify is unavailable')
