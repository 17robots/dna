#!/usr/bin/env python3
"""Drive real completion and key dispatch for one-key Escape to normal mode."""
import os
from pathlib import Path
import shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-completion-escape-',dir=ROOT/'build') as temp:
    work=Path(temp);stage=work/'src';shutil.copytree(ROOT/'src',stage)
    shutil.copyfile(ROOT/'tests/editor/completion_escape_smoke.dyn',stage/'completion_escape_smoke.dyn')
    (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer:rawptr,window:rawptr,input_storage:[]u8){completion_escape_smoke(app,typography)}
fn finish_probe(app:*App){}
''')
    env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary=work/'editor'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([str(binary)],env=env,check=True,timeout=30)
        print(f'PASS completion Escape ({mode}): one key enters normal mode, preserves text and prevents reopen in Helix/Vim',flush=True)
