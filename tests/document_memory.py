#!/usr/bin/env python3
"""Bound resident baseline/undo storage through saving, sustained dirty edits, and reload."""
import argparse
import json
import os
from pathlib import Path
import select
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--record-only', action='store_true')
parser.add_argument('--output', type=Path, default=ROOT / 'build/document-snapshot-memory.json')
args = parser.parse_args()
stage = ROOT / 'build/document-memory'
stage.mkdir(parents=True, exist_ok=True)
shutil.copytree(ROOT / 'src/buffer', stage / 'buffer', dirs_exist_ok=True)
shutil.copyfile(ROOT / 'tests/document_memory/main.dyn', stage / 'main.dyn')
binary = stage / 'check'
subprocess.run(['python3', str(ROOT / 'scripts/compile.py'), os.environ.get('DYN', 'dyn'),
                'build', str(stage), '--release', '--output', str(binary)], check=True)
process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
measurements = {}
try:
    for expected in ('empty', 'clean', 'first_edit', 'saved', 'resaved', 'unchanged_save',
                     'history_retained', 'tiny_after_history', 'sustained_clean', 'dirty_1000',
                     'dirty_4000', 'dirty_redo', 'tiny_after_dirty', 'many_lines', 'tiny_after_lines'):
        assert select.select([process.stdout], [], [], 15)[0], ('phase timed out', expected)
        label = process.stdout.readline().decode().strip()
        assert label == expected, (label, expected, process.poll())
        fields = dict(line.split(':', 1) for line in Path(f'/proc/{process.pid}/smaps_rollup').read_text().splitlines() if ':' in line)
        measurements[label] = {key: int(fields[key].split()[0]) for key in ('Rss', 'Pss', 'Private_Dirty')}
        process.stdin.write(b'\n')
        process.stdin.flush()
    assert process.wait(timeout=5) == 0
finally:
    if process.poll() is None:
        process.kill()
        process.wait()
    process.stdin.close()
    process.stdout.close()
args.output.write_text(json.dumps(measurements, indent=2) + '\n')
print(json.dumps(measurements), flush=True)
if not args.record_only:
    baseline = measurements['clean']['Pss']
    assert measurements['first_edit']['Pss'] - baseline < 2 * 1024, 'first edit commits full-text baseline copies'
    for label in ('saved', 'resaved', 'unchanged_save'):
        assert measurements[label]['Pss'] - baseline < 8 * 1024, 'saved documents retain unused snapshot pages'
    for label in ('tiny_after_history', 'tiny_after_dirty', 'tiny_after_lines'):
        assert measurements[label]['Pss'] - measurements['empty']['Pss'] < 8 * 1024, 'small reload retains old text, history, or line-index pages'
    for label in ('dirty_1000', 'dirty_4000', 'dirty_redo'):
        assert measurements[label]['Pss'] - measurements['sustained_clean']['Pss'] < 12 * 1024, 'sustained edits retain excessive snapshots or undo storage'
    assert measurements['many_lines']['Pss'] - baseline < 80 * 1024, 'newline-dense line indexes retain full-width storage'
    print('PASS document snapshot sharing, sustained dirty edits, reload reclamation, aliased input, save-in-group, undo/redo')
