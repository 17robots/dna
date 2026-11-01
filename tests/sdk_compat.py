#!/usr/bin/env python3
"""Pinned SDK Windows modules must compose without modifying the installation."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from dyn_path import real_dyn
# This test has the same basename as the helper; load the helper explicitly.
import importlib.util
spec = importlib.util.spec_from_file_location('dna_sdk_compat', ROOT/'scripts/sdk_compat.py')
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)
compiler = real_dyn()
original = compiler.parent.parent/'share/dyn/dynlib/windows.dyn'
before = original.read_bytes() if original.is_file() else None
environment = compat.environment(compiler)
assert compat.environment(compiler, environment) == environment
for target in ('x86_64-windows', 'aarch64-windows'):
    subprocess.run([compiler, 'check', ROOT/'src', '--target', target],
                   env=environment, check=True, timeout=120)
assert before is None or original.read_bytes() == before
print('PASS pinned SDK compatibility: Windows modules compose; installed SDK unchanged')
