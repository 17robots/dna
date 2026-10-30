#!/usr/bin/env python3
"""Exercise production tree search navigation through the native editor."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-tree-search-', dir=ROOT/'build') as temporary:
    work = Path(temporary)
    stage = work/'src'
    shutil.copytree(ROOT/'src', stage)
    shutil.copyfile(ROOT/'tests/editor/tree_usability_smoke.dyn', stage/'tree_usability_smoke.dyn')
    (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer:rawptr,window:rawptr,input_storage:[]u8){
 tree_usability_smoke(app,typography)
 app.running=false
}
fn finish_probe(app:*App){}
''')
    env = dict(os.environ, DYN_EDITOR_SMOKE='1', DNA_DEFAULT_SERVERS='0', DNA_RECOVERY='0', DNA_CONFIG=str(work/'missing.toml'), XDG_CONFIG_HOME=str(work/'config'), XDG_STATE_HOME=str(work/'state'))
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary = work/'editor'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([str(binary)], env=env, check=True, timeout=90)
        print(f'PASS tree search navigation ({mode}): arrows, Ctrl-N/P/J/K, incremental query, Unicode backspace, cancel, Vim counts and configured movement',flush=True)
