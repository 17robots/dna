#!/usr/bin/env python3
"""A real config write wakes the blocked UI and reloads without a one-second poll."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
probe=ROOT/'build/config-notify.so'
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'config_notify', str(probe)], check=True)
for mode in ('debug','release'):
    with tempfile.TemporaryDirectory() as tmp:
        config=Path(tmp)/'config.toml';config.write_text('font_size = 16\nreduced_motion = true\n')
        trace=Path(tmp)/'trace.jsonl'
        env=dict(os.environ,DNA_CONFIG=str(config),DNA_RECOVERY='0',DNA_RENDER_TRACE=str(trace),SDL_VIDEODRIVER='dummy',LD_PRELOAD=str(probe))
        env.pop('DYN_EDITOR_SMOKE',None)
        subprocess.run([str(ROOT/f'build/dna-{mode}')],env=env,check=True,timeout=5)
        records=[json.loads(line) for line in trace.read_text().splitlines()]
        assert any(row['type']=='frame' and row['reasons'] & 128 for row in records)
        native=[r for r in records if r['type']=='native_memory' and r['name']=='disk_native'][0]
        assert native['allocations']>0 and native['live_objects']==0
