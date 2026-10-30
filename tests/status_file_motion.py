#!/usr/bin/env python3
"""Native status filename grows with a new buffer; editing and opt-outs stay immediate."""
import os
from pathlib import Path
import shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-status-file-motion-',dir=ROOT/'build') as temporary:
    work=Path(temporary);stage=work/'src';shutil.copytree(ROOT/'src',stage)
    shutil.copyfile(ROOT/'tests/editor/status_file_motion_smoke.dyn',stage/'status_file_motion_smoke.dyn')
    platform=stage/'platform/platform.dyn';source=platform.read_text().replace('pub extern fn ticks "dna_ticks"() u64','pub fn ticks()u64{return status_file_probe_now}')
    source+='\nstatus_file_probe_now:u64=1000\npub fn status_file_probe_time(now:u64){status_file_probe_now=now}\n'
    platform.write_text(source)
    gui=stage/'platform/gui.dyn';source=gui.read_text();start=source.index('fn sdl_present(');end=source.index('\nfn sdl_scale(',start)
    gui.write_text(source[:start]+'fn sdl_present(renderer:rawptr)bool{return true}\n'+source[end:])
    (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer,window:rawptr,input_storage:[]u8){status_file_motion_smoke(app,typography,renderer,window,StatusFileMotionProbe{time:sdl.status_file_probe_time})}
fn finish_probe(app:*App){}
''')
    env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary=work/'editor'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([str(binary)],env=env,check=True,timeout=30)
        print(f'PASS status filename motion ({mode}): spatial width, clipping, startup/settle, immediate editing and opt-outs',flush=True)
