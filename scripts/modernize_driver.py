#!/usr/bin/env python3
"""Convert loops in src/*.dyn, then revert any loop the compiler rejects."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / 'src').glob(os.environ.get('LOOP_GLOB', '*.dyn')))
backup = Path('/tmp/loop-originals')
if backup.exists():
    shutil.rmtree(backup)
backup.mkdir()
for name in files:
    (backup / name).parent.mkdir(parents=True, exist_ok=True); shutil.copy(ROOT / name, backup / name)
skip = []
for attempt in range(12):
    for name in files:
        shutil.copy(backup / name, ROOT / name)
    result = subprocess.run(['python3', 'scripts/modernize_loops.py', '--skip', ','.join(skip), *files], cwd=ROOT, capture_output=True, text=True)
    print(result.stdout.strip().splitlines()[-1])
    mapping = json.load(open('/tmp/loop-map.json'))
    check = subprocess.run(['dyn', 'check', 'src'], cwd=ROOT, capture_output=True, text=True)
    errors = re.findall(r'(src/[\w/]+\.dyn):(\d+):\d+: error', check.stdout + check.stderr)
    if not errors:
        print(f'clean after {attempt + 1} passes; {len(skip)} loops left as they were')
        break
    added = 0
    for path, line in errors:
        line = int(line)
        owners = [entry for entry in mapping if entry['file'] == path and entry['first'] <= line <= entry['last']]
        if owners:
            owner = max(owners, key=lambda entry: entry['first'])
            key = f"{path}:{owner['original']}"
            if key not in skip:
                skip.append(key)
                added += 1
    if not added:
        print('errors outside converted loops:')
        print((check.stdout + check.stderr)[:2000])
        break
