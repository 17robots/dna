#!/usr/bin/env python3
"""Check real native picker geometry and unchanged-selection visibility on resize."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-picker-viewport-', dir=ROOT/'build') as temporary:
    work = Path(temporary)
    stage = work/'src'
    shutil.copytree(ROOT/'src', stage)
    shutil.copyfile(ROOT/'tests/editor/picker_viewport_smoke.dyn', stage/'picker_viewport_smoke.dyn')
    env = dict(os.environ, DYN_EDITOR_SMOKE='1', DNA_DEFAULT_SERVERS='0', DNA_RECOVERY='0', DNA_CONFIG=str(work/'missing.toml'), XDG_CONFIG_HOME=str(work/'config'), XDG_STATE_HOME=str(work/'state'))
    for case in os.environ.get('DNA_PICKER_CASES', 'resize slim_viewport').split():
        (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer:rawptr,window:rawptr,input_storage:[]u8){
 picker_'''+case+'''_smoke(app,typography,renderer)
 app.running=false
}
fn finish_probe(app:*App){}
''')
        for mode in os.environ.get('DNA_SMOKE_MODES', 'debug release').split():
            binary = work/'editor'
            subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
            subprocess.run([str(binary)], env=env, check=True, timeout=90)
            print(f'PASS picker {case} ({mode}): visible selection and placed viewport rows',flush=True)
