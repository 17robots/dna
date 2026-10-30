#!/usr/bin/env python3
"""Exercise actual pane cache allocation, invalidation and lifetime."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-pane-storage-',dir=ROOT/'build') as directory:
    work=Path(directory);stage=work/'src';shutil.copytree(ROOT/'src',stage)
    shutil.copyfile(ROOT/'tests/editor/pane_storage_smoke.dyn',stage/'pane_storage_smoke.dyn')
    (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer,window:rawptr,input_storage:[]u8){
 pane_storage_smoke(app,typography,renderer,window)
}
fn finish_probe(app:*App){}
''')
    env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary=work/'dna'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([str(binary)],env=env,check=True,timeout=90)
        print(f'PASS lazy pane typography: allocation, split/close, font invalidation and reconstruction ({mode})',flush=True)
