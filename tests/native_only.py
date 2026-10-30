#!/usr/bin/env python3
"""Reject SDL source dependencies and verify native editor ELF products."""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-only', action='store_true')
parser.add_argument('--binary', action='append', type=Path,
                    help='Check an additional ELF product (repeatable)')
args = parser.parse_args()

failures = []
for directory in ('src', 'modules', 'tests'):
    for path in (ROOT / directory).rglob('*.dyn'):
        text = path.read_text()
        if re.search(r'#link\s*\(\s*"(?:SDL|SDL3|SDL3_ttf|SDL2)[^"]*"', text):
            failures.append(f'{path.relative_to(ROOT)} links SDL')
        if re.search(r'extern fn[^\n]*"(?:SDL_|TTF_)', text):
            failures.append(f'{path.relative_to(ROOT)} imports an SDL/TTF symbol')
for filename in ('scripts/deps.py', 'scripts/build_native.py', 'scripts/profile.py',
                 'scripts/build_smoke.py', 'justfile', 'mise.toml'):
    text = (ROOT / filename).read_text()
    if re.search(r'libSDL(?:[23]|_ttf)|libsdl-org|SDL3_ttf|build-sdl|run-sdl', text):
        failures.append(f'{filename} retains an SDL build path')
if failures:
    raise SystemExit('\n'.join(failures))
print('PASS native-only source dependencies')

if not args.source_only:
    binaries = args.binary or [ROOT / 'build/dna-debug', ROOT / 'build/dna-release']
    for binary in binaries:
        binary = binary.resolve()
        if not binary.is_file():
            raise SystemExit(f'Missing native product: {binary}')
        dynamic = subprocess.check_output(['readelf', '-d', str(binary)], text=True)
        if re.search(r'NEEDED[^\n]*(?:SDL|SDL_ttf)', dynamic):
            raise SystemExit(f'{binary}: direct SDL dependency')
        dependencies = subprocess.run(['ldd', str(binary)], capture_output=True, text=True)
        if dependencies.returncode and 'not a dynamic executable' not in dependencies.stderr:
            raise SystemExit(dependencies.stderr or dependencies.stdout)
        if re.search(r'libSDL', dependencies.stdout):
            raise SystemExit(f'{binary}: transitive SDL dependency')
        if 'not found' in dependencies.stdout:
            raise SystemExit(f'{binary}: unresolved runtime dependency\n{dependencies.stdout}')
        symbols = subprocess.check_output(['nm', str(binary)], text=True)
        if re.search(r'^.*\s(?:SDL_|TTF_)\w*$', symbols, flags=re.M):
            raise SystemExit(f'{binary}: SDL/TTF symbols remain')
        print(f'PASS native-only ELF: {binary.name}')
