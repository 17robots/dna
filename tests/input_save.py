#!/usr/bin/env python3
"""Type, Escape, and :write through SDL; assert the bytes saved to disk."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
probe = ROOT / 'build/input-save.so'
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'input_events', str(probe)], check=True)
for mode in ('debug', 'release'):
    with tempfile.TemporaryDirectory(prefix='dna-input-save-') as temporary:
        directory = Path(temporary)
        target = directory / 'document.txt'
        target.write_text('')
        env = dict(os.environ, DNA_RECOVERY='0', SDL_VIDEODRIVER='dummy',
                   DNA_CONFIG=str(directory / 'config.toml'), DNA_INPUT_SAVE_TEST='1',
                   LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'), LD_PRELOAD=str(probe))
        env.pop('DYN_EDITOR_SMOKE', None)
        subprocess.run([str(ROOT / f'build/dna-{mode}'), str(target)], env=env, check=True, timeout=5)
        assert target.read_text() == 'a ' * 200, 'Escape/:write failed to save typed text'
        print(f'PASS SDL typing, Escape, :write and quit ({mode})', flush=True)
