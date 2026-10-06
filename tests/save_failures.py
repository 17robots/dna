#!/usr/bin/env python3
import os, resource, shutil, signal, subprocess, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];stage=root/'build/save-failures';stage.mkdir(exist_ok=True)
for module in ('filesystem','files','buffer'):shutil.copytree(root/'src'/module,stage/module,dirs_exist_ok=True)
shutil.copyfile(root/'tests/save_failures/main.dyn',stage/'main.dyn')
for mode in ('debug','release'):
    binary=stage/mode;subprocess.run(['python3',str(root/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(stage),'--'+mode,'--output',str(binary)],check=True)
    for killed in (False,True):
        with tempfile.TemporaryDirectory() as d:
            original=Path(d)/'original.txt';original.write_text('original')
            def limit():
                resource.setrlimit(resource.RLIMIT_FSIZE,(16,16))
                signal.signal(signal.SIGXFSZ,signal.SIG_DFL if killed else signal.SIG_IGN)
            result=subprocess.run([str(binary)],cwd=d,preexec_fn=limit)
            assert result.returncode==(-signal.SIGXFSZ if killed else 0),result.returncode
            assert original.read_text()=='original'
            if not killed:assert not (Path(d)/'original.txt.dna-write').exists()
print('PASS partial-write failure and interrupted saves preserve original files')
