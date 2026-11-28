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
import private_display
ROOT=Path(__file__).resolve().parents[1]
# One editor build per mode; DNA_CLOSE_CASE and DNA_CLOSE_PATH pick the case at run time.
PROBE='''fn startup_probe(app:*App,typography:*Typography,renderer:rawptr,window:rawptr,input_storage:[]u8){
 case_storage:[8]u8
 digits:=host.environment("DNA_CLOSE_CASE",case_storage[..]) catch {
  #panic("DNA_CLOSE_CASE is not set")
 }
 scenario:usize=0
 for digit in digits {
  scenario=scenario*10+(digit-'0')
 }
 path_storage:[4096]u8
 path:=host.environment("DNA_CLOSE_PATH",path_storage[..]) catch {
  #panic("DNA_CLOSE_PATH is not set")
 }
 buffer_close_smoke(app,typography,scenario,path)
}
fn finish_probe(app:*App){}
'''
TUI_CASES=('5','7','8','12','17','18','19')
display=private_display.available()
if not display:
    print('SKIP buffer close window cases: no private display (see tests/private_display.py); terminal cases still run',flush=True)
with tempfile.TemporaryDirectory(prefix='dna-buffer-close-',dir=ROOT/'build') as temporary:
    work=Path(temporary);stage=work/'src';shutil.copytree(ROOT/'src',stage)
    shutil.copyfile(ROOT/'tests/editor/buffer_close_smoke.dyn',stage/'buffer_close_smoke.dyn')
    (stage/'startup_probe.dyn').write_text(PROBE)
    env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary=work/f'editor-{mode}'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        for scenario in os.environ.get('DNA_CLOSE_CASES','0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20').split():
            if scenario not in TUI_CASES and not display:continue
            path=work/f'saved-{mode}-{scenario}.txt'
            if scenario in ('3','7'):path.write_text('first file\n')
            if scenario in ('16','19'):path.write_text('shared file\n')
            if scenario in ('9','20'):path.mkdir()
            case_env=dict(env,DNA_CLOSE_CASE=scenario,DNA_CLOSE_PATH=str(path))
            if scenario in TUI_CASES:
                master,slave=pty.openpty()
                fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',32,120,0,0))
                process=subprocess.Popen([str(binary),'--tui'],stdin=slave,stdout=slave,stderr=slave,env=dict(case_env,TERM='xterm-256color'),start_new_session=True)
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
                subprocess.run([str(binary)],env=case_env,check=True,timeout=90)
            if scenario in ('3','7'):assert path.read_text()=='saved first file\n'
            if scenario in ('16','19'):assert path.read_text()=='saved shared file\n'
            print(f'PASS buffer close ({mode}, case{scenario}): view ownership, save/cancel and frontend last-buffer policy',flush=True)
