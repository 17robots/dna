#!/usr/bin/env python3
"""Production TUI storage lifetime: failed entry, reentry, release and fresh cells."""
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
CHECK='''fn storage_check(ok:bool) { if !ok { #panic("TUI screen storage lifecycle") } }
fn main() {
  if !tui_start() {
    storage_check(!state.active && #len(grid)==0 && #len(shown)==0 && #len(output)==0)
    storage_check(screen_storage==nil)
    return
  }
  for cycle in 0..2 {
    if cycle!=0 { storage_check(tui_start()) }
    storage_check(#len(grid)==MaxColumns*MaxRows && #len(shown)==#len(grid) && #len(output)==1048576)
    storage_check(grid[#len(grid)-1].character==0 && shown[#len(shown)-1].character==0)
    address:=#cast(usize,&grid[0])
    storage_check(tui_start() && #cast(usize,&grid[0])==address)
    storage_check(floor_cell(-1.0,CellWidth)== -1 && floor_cell(-8.0,CellWidth)== -1 && floor_cell(-9.0,CellWidth)== -2 && floor_cell(-80.0,CellWidth)== -10)
    text:=tui_text_create()
    storage_check(text!=nil)
    ascii:[]const u8="0123456789TAIL"
    storage_check(tui_text_set(text,&ascii[0],#len(ascii)))
    tui_clear()
    tui_text_draw(text,-80.0,0.0)
    storage_check(grid[0].character=='T' && grid[1].character=='A')
    unicode:[]const u8="é中é🙂TAIL"
    storage_check(tui_text_set(text,&unicode[0],#len(unicode)))
    tui_clear()
    tui_text_draw(text,-48.0,0.0)
    storage_check(grid[0].character=='T' && grid[1].character=='A')
    tui_text_destroy(text)
    tui_clear()
    tui_present()
    grid[#len(grid)-1].character=88
    shown[#len(shown)-1].character=89
    tui_stop()
    storage_check(!state.active && #len(grid)==0 && #len(shown)==0 && #len(output)==0)
    storage_check(screen_storage==nil && output_used==0)
    tui_stop()
  }
}
'''
with tempfile.TemporaryDirectory(prefix='dna-tui-storage-') as directory:
    work=Path(directory)
    stage=work/'probe'
    shutil.copytree(ROOT/'src/platform',stage)
    for module in ('host','cstring','owned_arena'):
        shutil.copytree(ROOT/'src'/module,stage/module)
    tui=stage/'tui.dyn'
    tui.write_text(tui.read_text().replace('use "../host"','use "./host"'))
    (stage/'main.dyn').write_text(CHECK)
    output=work/'check'
    env=dict(os.environ,DYN_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'),LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'))
    subprocess.run(['python3',str(ROOT/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(stage),'--release','--output',str(output)],env=env,check=True,timeout=120)
    subprocess.run([str(output)],input=b'',stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,check=True,timeout=10)
    master,slave=pty.openpty()
    process=subprocess.Popen([str(output)],stdin=slave,stdout=slave,stderr=slave,env=env)
    os.close(slave)
    data=bytearray()
    try:
        deadline=time.monotonic()+10
        while process.poll() is None and time.monotonic()<deadline:
            if select.select([master],[],[],.1)[0]:
                try:data.extend(os.read(master,65536))
                except OSError:break
        assert process.wait(timeout=2)==0,data.decode(errors='replace')
    finally:
        if process.poll() is None:process.kill();process.wait()
        os.close(master)
print('PASS production TUI storage: failed entry allocates nothing, active reentry retains owner, stop clears ownership and restart has fresh cells')
