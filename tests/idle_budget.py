#!/usr/bin/env python3
"""Replay idle pointer motion and bound redraws, process CPU, and final ownership."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('report',ROOT/'scripts/render_report.py')
report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)
# Builds the same event replay used for the zero-unnecessary-redraw regression.
subprocess.run(['python3',str(ROOT/'tests/redraw_idle.py')],check=True)
with tempfile.TemporaryDirectory() as tmp:
    trace=Path(tmp)/'idle.jsonl'
    env=dict(os.environ,DNA_CONFIG=tmp+'/config',DNA_RENDER_TRACE=str(trace),DNA_RECOVERY='0',DNA_REDUCED_MOTION='1',SDL_VIDEODRIVER='dummy',LD_PRELOAD=str(ROOT/'build/redraw-idle.so'))
    env.pop('DYN_EDITOR_SMOKE',None)
    subprocess.run([str(ROOT/'build/dna-release')],env=env,check=True,timeout=8)
    values=report.summarize(trace);summary=values['summary']
    assert values['complete'] and values['frames']==1,values['reasons']
    assert summary['elapsed_us']>1000000
    assert summary['process_cpu_us']<summary['elapsed_us']/5,summary
    assert summary['arena_reserved']==0
    assert all(v['live_objects']==0 for v in values['native_memory'].values())
    print('PASS idle CPU {:.2f}% of one core, one startup frame, no retained tracked allocations'.format(summary['process_cpu_us']/summary['elapsed_us']*100))
