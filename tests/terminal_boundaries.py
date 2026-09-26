#!/usr/bin/env python3
"""Exercise private terminal boundaries against the production Dyn implementation."""
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'build/native-tests/terminal_boundaries'
STAGE.mkdir(parents=True, exist_ok=True)
for source in STAGE.glob('*.dyn'):
    source.unlink()
for source in (ROOT / 'src/native/dyn').glob('*.dyn'):
    shutil.copyfile(source, STAGE / source.name)
shutil.copyfile(ROOT / 'tests/native/terminal_boundaries/main.dyn', STAGE / 'main.dyn')
output = STAGE / 'check'
env = dict(os.environ, DYN_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'),
           LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'))
subprocess.run(['python3', str(ROOT / 'scripts/compile.py'), os.environ.get('DYN', 'dyn'),
                'build', str(STAGE), '--release', '--output', str(output)], env=env, check=True)
subprocess.run([str(output)], env=env, check=True, timeout=10)
