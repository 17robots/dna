#!/usr/bin/env python3
"""Build a Dyn native test or LD_PRELOAD interposer with shared test support."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
def build(name, output, shared=True):
    stage = ROOT / 'build/native-tests' / name
    stage.mkdir(parents=True, exist_ok=True)
    for old in stage.glob('*.dyn'):
        old.unlink()
    if name not in ('notifications', 'syntax_retire'):
        shutil.copyfile(ROOT/'tests/native/support.dyn', stage/'support.dyn')
    if not (ROOT/'tests/native'/name/'main.dyn').is_file():
        raise SystemExit(f'Unknown native test: {name}')
    for source in (ROOT/'tests/native'/name).glob('*.dyn'):
        shutil.copyfile(source, stage/source.name)
    runtime_map = stage/'hide-runtime.map'
    runtime_map.write_text('{ local: memcpy; memmove; memset; };\n')
    command = ['python3', str(ROOT/'scripts/compile.py'), os.environ.get('DYN', 'dyn'),
               'build', str(stage), '--release', '--output', str(output),
               '--link', '--version-script='+str(runtime_map)]
    if shared:
        command += ['--shared']
    else:
        command += ['--link', str(ROOT/'build/deps/install/lib/libSDL3.so')]
    subprocess.run(command, check=True, env=dict(os.environ, DYN_LIBRARY_PATH=str(ROOT/'build/deps/install/lib')))
    symbols = subprocess.check_output(['nm', '-D', '--defined-only', str(output)], text=True)
    assert not any(line.split()[-1] in ('memcpy', 'memmove', 'memset') for line in symbols.splitlines()), 'runtime memory symbols must stay private'
if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], '--executable' not in sys.argv[3:])
