#!/usr/bin/env python3
"""Locate the real Dyn executable behind version-manager shims.

mise links its shims to the mise binary and resolves versions from the user's
configuration. Tests isolate XDG_CONFIG_HOME, which hides that configuration,
so they put the real executable's directory first on PATH instead.
"""
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def real_dyn():
    """Absolute path of the dyn executable that owns its runtime, or None."""
    name = os.environ.get('DYN', 'dyn')
    candidates = []
    found = shutil.which(name)
    if found:
        candidates.append(Path(found).resolve())
    if shutil.which('mise'):
        located = subprocess.run(['mise', 'which', Path(name).name], capture_output=True, text=True, cwd=ROOT)
        if located.returncode == 0 and located.stdout.strip():
            candidates.append(Path(located.stdout.strip()).resolve())
    for compiler in candidates:
        if compiler.name.startswith('dyn'):
            return compiler
    return None


def with_real_dyn(env):
    """Copy of env whose PATH starts with the real dyn's directory."""
    compiler = real_dyn()
    result = dict(env)
    if compiler:
        result['PATH'] = str(compiler.parent) + os.pathsep + result.get('PATH', '')
    return result


if __name__ == '__main__':
    print(real_dyn() or '')
