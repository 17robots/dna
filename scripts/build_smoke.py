#!/usr/bin/env python3
"""Compile production sources with the test-only startup adapter, under the build cap."""
import os
from pathlib import Path
import shutil
import subprocess
ROOT = Path(__file__).resolve().parents[1]
stage = ROOT / 'build/editor-smoke'
stage.mkdir(parents=True, exist_ok=True)
# Remove obsolete staged sources; never delete user source or build outputs.
for item in stage.iterdir():
    if item.is_dir(): shutil.rmtree(item)
    else: item.unlink()
shutil.copytree(ROOT/'src', stage, dirs_exist_ok=True)
shutil.copytree(ROOT/'tests/editor', stage, dirs_exist_ok=True)
for mode in os.environ.get('DNA_SMOKE_MODES', 'debug release').split():
    subprocess.run(['python3', str(ROOT/'scripts/compile.py'), os.environ.get('DYN','dyn'),
                    'build', str(stage), '--'+mode, '--output', str(ROOT/f'build/dna-smoke-{mode}'),
                    '--link', str(ROOT/'build/deps/install/lib/libSDL3_ttf.so')], check=True)
