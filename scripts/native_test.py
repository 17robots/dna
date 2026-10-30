#!/usr/bin/env python3
"""Build native ABI probes and non-GUI fault interposers; SDL probes are retired."""
import os
import re
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
    if not (ROOT/'tests/native'/name/'main.dyn').is_file():
        raise SystemExit(f'Unknown native test: {name}')
    sources = list((ROOT/'tests/native'/name).glob('*.dyn'))
    for source in sources:
        if re.search(r'\b(?:SDL_|TTF_|probe_key\b|probe_push\b|probe_delay\b)', source.read_text()):
            raise SystemExit(f'{name} is a retired SDL GUI probe; use native platform or editor startup tests')
        shutil.copyfile(source, stage/source.name)
    if name != 'syntax_retire':
        shutil.copyfile(ROOT/'tests/native/support.dyn', stage/'support.dyn')
    runtime_map = stage/'hide-runtime.map'
    runtime_map.write_text('{ local: memcpy; memmove; memset; };\n')
    command = ['python3', str(ROOT/'scripts/compile.py'), os.environ.get('DYN', 'dyn'),
               'build', str(stage), '--release', '--output', str(output),
               '--link', '--version-script='+str(runtime_map)]
    if shared:
        command += ['--shared']
    else:
        command += ['--link', str(ROOT/'build/deps/install/lib/libdna_native.so')]
    subprocess.run(command, check=True, env=dict(os.environ, DYN_LIBRARY_PATH=str(ROOT/'build/deps/install/lib')))
    symbols = subprocess.check_output(['nm', '-D', '--defined-only', str(output)], text=True)
    assert not any(line.split()[-1] in ('memcpy', 'memmove', 'memset') for line in symbols.splitlines()), 'runtime memory symbols must stay private'
if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], '--executable' not in sys.argv[3:])
