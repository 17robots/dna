#!/usr/bin/env python3
"""Type into saved Dyn files and wait for completion without polling the UI."""
import os
import json
from pathlib import Path
import subprocess
import tempfile
import sys as _sys
_sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'scripts'))
from dyn_path import with_real_dyn
ROOT = Path(__file__).resolve().parents[1]
probe = ROOT / 'build/language-popups.so'
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'language_popups', str(probe)], check=True)
with tempfile.TemporaryDirectory(prefix='dna-language-popups-') as temporary:
    directory = Path(temporary)
    source = directory/'example.dyn'
    source.write_text(('fn helper(value: int) {}' if os.environ.get('DNA_POPUP_SNIPPET') else 'fn helper() {}') + '\nfn main() {\n  \n}')
    if os.environ.get('DNA_POPUP_PLATFORM'):
        source.unlink()
        source = directory/'platform.dyn'
        source.write_bytes((ROOT/'src/platform/platform.dyn').read_bytes())
    if os.environ.get('DNA_POPUP_SOURCE'):
        source = Path(os.environ['DNA_POPUP_SOURCE'])
    config = directory/'config.toml'
    config.write_text((ROOT/'config.example.toml').read_text() if os.environ.get('DNA_POPUP_EXAMPLE_CONFIG') else 'reduced_motion = true\n')
    if os.environ.get('DNA_POPUP_LSP'):
        with config.open('a') as output:
            output.write('\n[languages.dyn]\nserver = ' + json.dumps(os.environ['DNA_POPUP_LSP']) + '\nauto_start = true\n')
    env = with_real_dyn(dict(os.environ, SDL_VIDEODRIVER=os.environ.get('SDL_VIDEODRIVER', 'dummy'), DNA_CONFIG=str(config),
               DNA_RECOVERY='0', LD_PRELOAD=str(probe), LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'),
               XDG_CONFIG_HOME=str(directory/'config')))
    env.pop('DYN_EDITOR_SMOKE', None)
    command = [str(ROOT/'build/dna-debug'), str(source)]
    cwd = directory
    if os.environ.get('DNA_POPUP_RUN'):
        command = ['python3', str(ROOT/'scripts/compile.py'), 'dyn', 'run', 'src']
        cwd = ROOT
        env['DNA_POPUP_OPENFILE'] = str(source)
    subprocess.run(command, cwd=cwd, env=env, check=True,
                   timeout=60 if os.environ.get('DNA_POPUP_RUN') else 12)
