#!/usr/bin/env python3
"""Measure actual bounded document edits before choosing a storage redesign."""
import os, shutil, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]; stage=root/'build/buffer-performance';stage.mkdir(exist_ok=True)
shutil.copytree(root/'src/buffer',stage/'buffer',dirs_exist_ok=True)
shutil.copyfile(root/'tests/buffer_performance/main.dyn',stage/'main.dyn')
for mode in ('debug','release'):
    binary=stage/mode
    subprocess.run(['python3',str(root/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(stage),'--'+mode,'--output',str(binary)],check=True)
    print(mode,flush=True);subprocess.run([str(binary)],check=True,timeout=20)
