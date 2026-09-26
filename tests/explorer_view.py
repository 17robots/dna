#!/usr/bin/env python3
"""Render actual explorer columns/icons with an ordinary monospace font."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
probe = ROOT / 'build/explorer-view.so'
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'explorer_view', str(probe)], check=True)
font = subprocess.check_output(['fc-match', '-f', '%{file}', 'DejaVu Sans Mono'], text=True).strip()
with tempfile.TemporaryDirectory(prefix='dna-explorer-') as temporary:
    parent = Path(temporary)
    project = parent/'project'; project.mkdir()
    (parent/'neighbor').mkdir()
    (project/'assets').mkdir(); (project/'src').mkdir()
    (project/'README.md').write_text('# Example project\n\nSmall, native and keyboard driven.\n\nEnter opens an entry.\nBackspace returns to its parent.\n')
    (project/'config.toml').write_text('font_size = 16\n')
    (project/'main.dyn').write_text('fn main() {}\n')
    (project/'notes.txt').write_text('notes\n')
    captures = []
    for label, icons, narrow in [('wide', True, False), ('no-icons', False, False), ('narrow', True, True)]:
        config = parent/'config.toml'
        config.write_text(f'font_size = 16\nline_height = 1.25\nreduced_motion = true\nexplorer_icons = {str(icons).lower()}\n')
        # Captures live in the temporary folder, so nothing collects in build/.
        capture = parent/f'explorer-{label}.bmp'
        env = dict(os.environ, SDL_VIDEODRIVER='dummy', DNA_CONFIG=str(config), DNA_FONT=font, DNA_RECOVERY='0', LD_PRELOAD=str(probe), LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'), DNA_EXPLORER_CAPTURE=str(capture))
        if narrow: env['DNA_EXPLORER_NARROW'] = '1'
        subprocess.run([str(ROOT/f"build/dna-{os.environ.get('DNA_EXPLORER_MODE', 'debug')}")], cwd=project, env=env, check=True, timeout=15)
        captures.append(capture.read_bytes())
    assert captures[0] != captures[1], 'icon toggle did not change the rendered explorer'
print('PASS explorer wide/narrow layouts and font-independent icon toggle')
