#!/usr/bin/env python3
import os, subprocess, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
probe=root/'build/render-cache.so'
subprocess.run(['python3', str(root/'scripts/native_test.py'), 'render_cache', str(probe)], check=True)
with tempfile.TemporaryDirectory() as d:
    fixture=Path(d)/'cache.json';fixture.write_text('[\n'+',\n'.join('"'+('cache text '*30)+'"' for _ in range(40))+'\n]')
    env=dict(os.environ,SDL_VIDEODRIVER='dummy',DNA_REDUCED_MOTION='1',DNA_RECOVERY='0',DNA_CONFIG=d+'/none',DNA_LANGUAGE_DIR=str(root/'build/test-languages'),LD_PRELOAD=str(probe),LD_LIBRARY_PATH=str(root/'build/deps/install/lib'))
    subprocess.run([str(root/'build/dna-debug'),str(fixture)],env=env,timeout=15,check=True)

    for index in range(80):
        (Path(d)/f'file-{index:03}.txt').write_text('picker fixture\n')
    print('file-picker',flush=True)
    subprocess.run([str(root/'build/dna-debug'),str(fixture)],cwd=d,env=dict(env,DNA_PICKER_CACHE='1'),timeout=15,check=True)

    for label,text in [('long-line','x'*1000000),('large-selection',('é中 words\n'*70000))]:
        fixture=Path(d)/(label+'.txt');fixture.write_text(text)
        print(label,flush=True)
        subprocess.run([str(root/'build/dna-debug'),str(fixture)],env=dict(env,DNA_STRESS_RENDER='1'),timeout=20,check=True)
