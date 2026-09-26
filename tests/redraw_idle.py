#!/usr/bin/env python3
"""Moving over a document without diagnostics must not redraw or arm hover work."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
probe = ROOT / 'build/redraw-idle.so'
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'redraw_idle', str(probe)], check=True)
with tempfile.TemporaryDirectory() as directory:
    env = dict(os.environ, DNA_CONFIG=directory+'/config', DNA_RECOVERY='0', DNA_REDUCED_MOTION='1', SDL_VIDEODRIVER='dummy', LD_PRELOAD=str(probe), LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'))
    env.pop('DYN_EDITOR_SMOKE', None)
    subprocess.run([str(ROOT/'build/dna-debug')], env=env, timeout=8, check=True)
