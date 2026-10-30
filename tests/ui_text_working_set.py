#!/usr/bin/env python3
"""Exercise real native UI text layouts across a pane/picker-sized working set."""
import os
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
production = [ROOT / 'build' / (name + '-' + mode)
              for name in ('dna-native', 'dna-native-wayland') for mode in ('debug', 'release')]
before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in production if path.exists()}
with tempfile.TemporaryDirectory(prefix='dna-ui-text-set-',dir=ROOT/'build') as temporary:
    work=Path(temporary)
    stage=work/'src';shutil.copytree(ROOT/'src',stage)
    shutil.copyfile(ROOT/'tests/editor/ui_text_working_set_smoke.dyn',stage/'ui_text_working_set_smoke.dyn')
    probe=stage/'startup_probe.dyn'
    probe.write_text(probe.read_text().replace('  app.view.reduced_motion = true','  ui_text_working_set_smoke(typography)\n  app.view.reduced_motion = true',1))
    environment=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    for mode in ('debug','release'):
        binary=work/'editor'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([str(binary)],env=environment,check=True,timeout=30)
print('PASS native UI text: 137 stable labels plus changing status, font invalidation, bounded eviction and repeated newest-label hits (debug/release)')

for path, digest in before.items():
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'staged test overwrote {path}'
