#!/usr/bin/env python3
"""Buffer close commands delete their views, with save/cancel and GUI last-buffer safety."""
import os
import fcntl
import pty
import select
import struct
import termios
import time
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-buffer-close-',dir=ROOT/'build') as temporary:
    work=Path(temporary);stage=work/'src';shutil.copytree(ROOT/'src',stage)
    shutil.copyfile(ROOT/'tests/editor/buffer_close_smoke.dyn',stage/'buffer_close_smoke.dyn')
    env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        for scenario in os.environ.get('DNA_CLOSE_CASES','0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20').split():
            path=work/f'saved-{mode}-{scenario}.txt'
            if scenario in ('3','7'):path.write_text('first file\n')
            if scenario in ('16','19'):path.write_text('shared file\n')
            if scenario in ('9','20'):path.mkdir()
            (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer:rawptr,window:rawptr,input_storage:[]u8){
 buffer_close_smoke(app,typography,'''+scenario+''',"'''+str(path)+'''")
}
fn finish_probe(app:*App){}
''')
            binary=work/'editor'
            subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
            if scenario in ('5','7','8','12','17','18','19'):
                master,slave=pty.openpty()
                fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',32,120,0,0))
                process=subprocess.Popen([str(binary),'--tui'],stdin=slave,stdout=slave,stderr=slave,env=dict(env,TERM='xterm-256color'),start_new_session=True)
                os.close(slave);output=bytearray();deadline=time.monotonic()+15
                try:
                    while process.poll() is None:
                        assert time.monotonic()<deadline,'TUI last-buffer close timed out'
                        if select.select([master],[],[],.05)[0]:
                            try:output.extend(os.read(master,65536))
                            except OSError:break
                    assert process.wait(timeout=2)==0,output.decode(errors='replace')
                finally:
                    if process.poll() is None:process.kill();process.wait()
                    os.close(master)
            else:
                subprocess.run([str(binary)],env=env,check=True,timeout=90)
            if scenario in ('3','7'):assert path.read_text()=='saved first file\n'
            if scenario in ('16','19'):assert path.read_text()=='saved shared file\n'
            print(f'PASS buffer close ({mode}, case{scenario}): view ownership, save/cancel and frontend last-buffer policy',flush=True)
