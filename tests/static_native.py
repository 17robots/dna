#!/usr/bin/env python3
"""Exercise native archive initialization without a shared-library constructor."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
binary = ROOT / 'build/static-native-lifecycle'
environment = dict(os.environ,
                   DYN_LIBRARY_PATH=str(ROOT / 'build/deps/tui-static'),
                   LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'),
                   DNA_RENDER_TRACE='1')
subprocess.run([
    'python3', str(ROOT / 'scripts/compile.py'), os.environ.get('DYN', 'dyn'),
    'build', str(ROOT / 'tests/native/static_lifecycle'), '--release', '--no-cache',
    '--output', str(binary),
], env=environment, check=True)
dynamic = subprocess.check_output(['readelf', '-d', str(binary)], text=True)
needed = [line for line in dynamic.splitlines() if '(NEEDED)' in line]
assert not any('libdna_native' in line for line in needed), 'must link native archive'
assert not any('SDL' in line for line in needed), 'terminal archive must not need SDL'
subprocess.run([str(binary)], env=environment, check=True, timeout=10)
