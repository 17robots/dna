#!/usr/bin/env python3
"""Version requests work without a display, terminal, or readable configuration."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', action='append', type=Path, required=True)
args = parser.parse_args()
version = re.search(r'const DnaVersion: \[\]const u8 = "([^"]+)"', (ROOT/'src/version.dyn').read_text())[1]
with tempfile.TemporaryDirectory(prefix='dna-version-') as directory:
    work = Path(directory)
    config = work/'config.toml'
    config.write_text('this is deliberately invalid TOML = [')
    env = dict(os.environ, HOME=directory, DNA_CONFIG=str(config), DNA_FONT='/no/such/font',
               XDG_CONFIG_HOME=str(work/'config'), XDG_STATE_HOME=str(work/'state'))
    for variable in ('DISPLAY', 'WAYLAND_DISPLAY', 'DYN_EDITOR_SMOKE', 'DNA_WORKFLOW_TEST'):
        env.pop(variable, None)
    for binary in args.binary:
        for command in (['--version'], ['version'], ['--gui', '--version'], ['--tui', '--version']):
            result = subprocess.run([str(binary.resolve()), *command], cwd=work, env=env,
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
            assert result.returncode == 0, result.stderr
            assert result.stdout == f'dna {version}\n', repr(result.stdout)
            assert result.stderr == '', result.stderr
        print('PASS headless version command: '+binary.name)
    assert not (work/'state').exists() and not (work/'config').exists(), 'version touched editor state'
