#!/usr/bin/env python3
"""Compare production Dyn event layouts with the installed SDL headers."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'build/test-platform-abi'
STAGE.mkdir(parents=True, exist_ok=True)
for source_file in (ROOT / 'src/platform').glob('*.dyn'):
    shutil.copyfile(source_file, STAGE / source_file.name)
# C field name -> Dyn field name, in ABI order (not grouped by type).
EVENTS = {
    'KeyEvent': ('SDL_KeyboardEvent', 'type:kind reserved timestamp windowID:window which:device scancode key mod:modifiers raw down repeat:repeated'),
    'TextEvent': ('SDL_TextInputEvent', 'type:kind reserved timestamp windowID:window text'),
    'EditingEvent': ('SDL_TextEditingEvent', 'type:kind reserved timestamp windowID:window text start length'),
    'MouseButton': ('SDL_MouseButtonEvent', 'type:kind reserved timestamp windowID:window which:device button down clicks padding x y'),
    'MouseMotion': ('SDL_MouseMotionEvent', 'type:kind reserved timestamp windowID:window which:device state x y xrel yrel'),
}
c = ['#include <SDL3/SDL.h>', '#include <stddef.h>', '#include <stdio.h>', 'int main(void) {']
checks = []
for dyn, (native, fields) in EVENTS.items():
    c.append(f'printf("%zu %zu ", sizeof({native}), _Alignof({native}));')
    checks.extend([(f'#sizeof({dyn})', f'{dyn} size'), (f'#alignof({dyn})', f'{dyn} alignment')])
    for field in fields.split():
        native_field, _, dyn_field = field.partition(':')
        dyn_field = dyn_field or native_field
        c.append(f'printf("%zu ", offsetof({native}, {native_field}));')
        checks.append((f'#cast(usize) &v{dyn}.{dyn_field} - #cast(usize) &v{dyn}', f'{dyn}.{dyn_field} offset'))
c.append('return 0; }')
(STAGE / 'probe.c').write_text('\n'.join(c))
flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'sdl3'], text=True))
subprocess.run(['cc', *flags, str(STAGE / 'probe.c'), '-o', str(STAGE / 'headers')], check=True)
values = subprocess.check_output([str(STAGE / 'headers')], text=True).split()
assert len(values) == len(checks)
source = ['fn main() {'] + [f'  v{name} := {name}{{}}' for name in EVENTS]
for (expression, label), expected in zip(checks, values):
    source.append(f'  if {expression} != {expected} {{ #panic("{label}") }}')
source.append('}')
(STAGE / 'main.dyn').write_text('\n'.join(source))
subprocess.run(['python3', str(ROOT / 'scripts/compile.py'), os.environ.get('DYN', 'dyn'), 'build', str(STAGE), '--debug', '--output', str(STAGE / 'check')], check=True)
subprocess.run([str(STAGE / 'check')], check=True, timeout=5)
print('PASS production Dyn keyboard, text, IME, and mouse layouts match SDL')
