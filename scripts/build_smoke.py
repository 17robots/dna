#!/usr/bin/env python3
"""Build the native editor with test-only startup adapters."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
backend = os.environ.get('DNA_NATIVE_BACKEND', 'auto')
if backend not in ('auto', 'x11', 'wayland'):
    raise SystemExit('DNA_NATIVE_BACKEND must be auto, x11 or wayland')
for mode in os.environ.get('DNA_SMOKE_MODES', 'debug release').split():
    if mode not in ('debug', 'release'):
        raise SystemExit('DNA_SMOKE_MODES must contain debug and/or release')
    subprocess.run([sys.executable, str(ROOT / 'scripts/build_native.py'),
                    '--backend', backend, '--smoke', '--mode', mode,
                    '--output', str(ROOT / f'build/dna-smoke-{mode}')], check=True)
