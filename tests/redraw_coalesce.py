#!/usr/bin/env python3
"""Deliver a worker invalidation and real SDL key together; require one present."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
probe = ROOT/'build/redraw-coalesce.so'
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'redraw_coalesce', str(probe)], check=True)
with tempfile.TemporaryDirectory() as temporary:
    folder = Path(temporary)
    target = folder/'document.txt'; target.write_text('abc\n')
    trace = folder/'trace.jsonl'
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', DNA_RECOVERY='0', DNA_REDUCED_MOTION='1', DNA_CONFIG=str(folder/'config'), DNA_RENDER_TRACE=str(trace), LD_PRELOAD=str(probe), LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'))
    env.pop('DYN_EDITOR_SMOKE', None)
    binary = os.environ.get('DNA_TEST_BINARY', str(ROOT/'build/dna-debug'))
    subprocess.run([binary, str(target)], env=env, check=True, timeout=8)
    frames = [json.loads(line) for line in trace.read_text().splitlines() if json.loads(line)['type'] == 'frame']
    assert any(frame['reasons'] & 1024 and frame['reasons'] & 2 for frame in frames)
    print('PASS coalesced disk + keyboard frame has both causes')
