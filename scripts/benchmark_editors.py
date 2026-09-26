#!/usr/bin/env python3
"""Compare terminal editors at one endpoint: PTY input to reconstructed screen.

This excludes a desktop terminal renderer and physical display. Each sample is
acknowledged by actual changed content, not an API return or a fixed sleep.
Configurations, files and writable state live in a temporary directory.
"""
import argparse
import ctypes as c
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import statistics
import subprocess
import struct
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
V = c.CDLL('libvterm.so.0')
class Rect(c.Structure):
    _fields_ = [(name, c.c_int) for name in ('start_row','end_row','start_col','end_col')]
class Pos(c.Structure):
    _fields_ = [('row',c.c_int),('col',c.c_int)]
for name, result, args in (
    ('new',c.c_void_p,[c.c_int,c.c_int]),('free',None,[c.c_void_p]),
    ('set_utf8',None,[c.c_void_p,c.c_int]),('obtain_screen',c.c_void_p,[c.c_void_p]),
    ('obtain_state',c.c_void_p,[c.c_void_p]),
    ('screen_reset',None,[c.c_void_p,c.c_int]),
    ('screen_enable_altscreen',None,[c.c_void_p,c.c_int]),
    ('input_write',c.c_size_t,[c.c_void_p,c.c_char_p,c.c_size_t]),
    ('screen_get_text',c.c_size_t,[c.c_void_p,c.c_void_p,c.c_size_t,Rect]),
    ('output_get_buffer_current',c.c_size_t,[c.c_void_p]),
    ('output_read',c.c_size_t,[c.c_void_p,c.c_void_p,c.c_size_t]),
    ('state_get_cursorpos',None,[c.c_void_p,c.POINTER(Pos)]),
):
    fn=getattr(V,'vterm_'+name);fn.restype=result;fn.argtypes=args

class Session:
    def __init__(self, command, env, cwd):
        self.rows,self.columns=32,120
        self.vt=V.vterm_new(self.rows,self.columns)
        V.vterm_set_utf8(self.vt,1)
        self.screen=V.vterm_obtain_screen(self.vt)
        self.state=V.vterm_obtain_state(self.vt)
        V.vterm_screen_enable_altscreen(self.screen,1)
        V.vterm_screen_reset(self.screen,1)
        master,slave=pty.openpty()
        fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',self.rows,self.columns,0,0))
        self.started=time.perf_counter_ns()
        self.pid=os.fork()
        if not self.pid:
            os.setsid();fcntl.ioctl(slave,termios.TIOCSCTTY,0)
            for fd in (0,1,2):os.dup2(slave,fd)
            os.close(master);os.close(slave);os.chdir(cwd)
            os.execve(command[0],command,env)
        os.close(slave);self.fd=master;self.raw=bytearray()
    def read(self, timeout):
        if not select.select([self.fd],[],[],max(0,timeout))[0]:return False
        data=os.read(self.fd,262144)
        if not data:raise RuntimeError('editor closed its PTY')
        self.raw.extend(data)
        V.vterm_input_write(self.vt,data,len(data))
        count=V.vterm_output_get_buffer_current(self.vt)
        if count:
            reply=c.create_string_buffer(count)
            count=V.vterm_output_read(self.vt,reply,count)
            os.write(self.fd,reply.raw[:count])
        return True
    def text(self):
        out=c.create_string_buffer(self.rows*self.columns*4+64)
        size=V.vterm_screen_get_text(self.screen,out,len(out),Rect(0,self.rows,0,self.columns))
        return out.raw[:size].decode('utf-8','replace')
    def cursor(self):
        pos=Pos();V.vterm_state_get_cursorpos(self.state,c.byref(pos));return pos.row,pos.col
    def wait(self, predicate, started=None, timeout=8):
        started=started or time.perf_counter_ns();deadline=time.monotonic()+timeout
        while True:
            if predicate():return (time.perf_counter_ns()-started)/1e6
            if time.monotonic()>=deadline:
                raise RuntimeError('screen acknowledgment timed out:\n'+self.text())
            self.read(deadline-time.monotonic())
    def settle(self, seconds=.025):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:self.read(deadline-time.monotonic())
    def send(self, keys, predicate, timeout=8):
        started=time.perf_counter_ns();os.write(self.fd,keys)
        return self.wait(predicate,started,timeout)
    def close(self):
        try:os.killpg(self.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        os.waitpid(self.pid,0);os.close(self.fd);V.vterm_free(self.vt)

def memory(pid):
    """RSS and PSS of editor plus descendants; shared pages counted fairly by PSS."""
    queue=[pid];rss=pss=0;seen=set()
    while queue:
        current=queue.pop()
        if current in seen:continue
        seen.add(current)
        try:
            fields={line.split(':')[0]:line.split(':')[1].strip() for line in Path(f'/proc/{current}/smaps_rollup').read_text().splitlines() if ':' in line}
            rss+=int(fields['Rss'].split()[0]);pss+=int(fields['Pss'].split()[0])
            for task in Path(f'/proc/{current}/task').iterdir():
                queue.extend(map(int,(task/'children').read_text().split()))
        except (FileNotFoundError,ProcessLookupError):pass
    return {'rss_kib':rss,'pss_kib':pss,'processes':len(seen)}

def summary(values):
    ordered=sorted(values)
    return {'samples':len(values),'median_ms':statistics.median(values),
            'p95_ms':ordered[max(0,math.ceil(.95*len(values))-1)],'max_ms':max(values)}

def run(editor, root, size, count, binary):
    directory=root/editor;directory.mkdir()
    home=directory/'home';home.mkdir();config=directory/'config';config.mkdir()
    files=directory/'files';files.mkdir()
    paths=[]
    for number in range(12):
        path=files/f'file-{number:02}.txt'
        first=f'BENCH_START_{number:02} text for editing\n'
        row='0123456789 abcdefghijklmnopqrstuvwxyz line for editing.\n'
        path.write_text(first+row*max(1,(size-len(first)-20)//len(row))+f'BENCH_END_{number:02}\n')
        paths.append(path)
    env=dict(os.environ,HOME=str(home),XDG_CONFIG_HOME=str(config),XDG_CACHE_HOME=str(directory/'cache'),XDG_STATE_HOME=str(directory/'state'),TERM='xterm-256color',COLORTERM='truecolor')
    for key in ('LD_PRELOAD','DYN_EDITOR_SMOKE','DNA_RENDER_TRACE'):env.pop(key,None)
    if editor=='dna':
        settings=directory/'dna.toml';settings.write_text('reduced_motion = true\nrelative_numbers = false\nautomatic_completion = false\nreload_config = false\n')
        env.update(DNA_CONFIG=str(settings),DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_LANGUAGE_DIR=str(ROOT/'build/test-languages'))
        command=[str(binary),'--tui',str(paths[0])]
    elif editor=='nvim':
        command=[shutil.which('nvim'),'--clean','-n','-i','NONE','--cmd','set noswapfile hidden notermguicolors ttimeoutlen=10',str(paths[0])]
    else:
        settings=directory/'helix.toml';settings.write_text('[editor]\nauto-completion = false\n[editor.lsp]\nenable = false\n')
        command=[shutil.which('hx'),'-c',str(settings),'--log',str(directory/'helix.log'),str(paths[0])]
    startup=[]
    for _ in range(5):
        session=Session(command,env,files)
        try:startup.append(session.wait(lambda:'BENCH_START_00' in session.text(),session.started))
        finally:session.close()
    session=Session(command,env,files)
    try:
        session.wait(lambda:'BENCH_START_00' in session.text(),session.started)
        session.settle(.2)
        initial=memory(session.pid)
        os.write(session.fd,b'i');session.settle(.15)
        insert=[];erase=[]
        for _ in range(count):
            insert.append(session.send(b'x',lambda:'xBENCH_START_00' in session.text()))
            session.settle(.01)
            erase.append(session.send(b'\x7f',lambda:'BENCH_START_00' in session.text() and 'xBENCH_START_00' not in session.text()))
            session.settle(.01)
        os.write(session.fd,b'\x1b');session.settle(.2)
        jumps=[]
        for _ in range(20):
            jumps.append(session.send(b'G' if editor=='nvim' else b'ge',lambda:'BENCH_END_00' in session.text()))
            session.settle(.01)
            jumps.append(session.send(b'gg',lambda:'BENCH_START_00' in session.text()))
            session.settle(.01)
        switching=[];round_memory=[]
        for round_index in range(3):
            for number,path in enumerate(paths):
                if round_index==0 and number==0:continue
                os.write(session.fd,b':');session.settle(.02)
                command=('edit ' if editor=='nvim' else 'open ')+str(path)
                os.write(session.fd,command.encode());session.settle(.02)
                marker=f'BENCH_START_{number:02}'
                switching.append(session.send(b'\r',lambda marker=marker:marker in session.text()))
                session.settle(.03)
            round_memory.append(memory(session.pid))
        return {'editor':editor,'fixture_bytes':paths[0].stat().st_size,'startup':summary(startup),
                'insert':summary(insert),'backspace':summary(erase),'jump':summary(jumps),
                'switch':summary(switching),'memory_initial':initial,'memory_rounds':round_memory,
                'raw_ms':{'startup':startup,'insert':insert,'backspace':erase,'jump':jumps,'switch':switching}}
    except Exception:
        (ROOT/'build'/f'benchmark-{editor}-failed-screen.txt').write_text(session.text())
        raise
    finally:session.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editors',nargs='+',choices=['dna','nvim','helix'],default=['dna','nvim','helix'])
    parser.add_argument('--bytes',type=int,default=50000)
    parser.add_argument('--samples',type=int,default=60)
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--max-dna-pss-kib',type=int,
                        help='optional regression budget after repeated switching')
    parser.add_argument('--dna',type=Path,default=ROOT/'dna')
    parser.add_argument('--output',type=Path,default=ROOT/'build/editor-benchmark.json')
    args=parser.parse_args()
    if args.samples < 1 or args.repeats < 1 or args.bytes < 4096:
        parser.error('samples/repeats must be positive and fixture size at least 4096 bytes')
    report={'endpoint':'PTY key write to content reconstructed by libvterm; excludes desktop and physical display',
            'workload':'plain text, no LSP; warm filesystem cache; 120 columns x 32 rows; three passes over twelve files',
            'dna_binary':str(args.dna.resolve()),'dna_sha256':hashlib.sha256(args.dna.read_bytes()).hexdigest(),
            'editor_order':'rotated between repeats',
            'versions':{},'results':[]}
    for editor,command in [('nvim',['nvim','--version']),('helix',['hx','--version'])]:
        if editor in args.editors:
            report['versions'][editor]=subprocess.check_output(command,text=True).splitlines()[0]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dna-editor-benchmark-') as temporary:
        for repeat in range(args.repeats):
            directory=Path(temporary)/str(repeat);directory.mkdir()
            offset=repeat%len(args.editors)
            for editor in args.editors[offset:]+args.editors[:offset]:
                result=run(editor,directory,args.bytes,args.samples,args.dna.resolve())
                result['repeat']=repeat
                report['results'].append(result)
                args.output.write_text(json.dumps(report,indent=2)+'\n')
                print(json.dumps({key:value for key,value in result.items() if key!='raw_ms'}),flush=True)
                if editor == 'dna' and args.max_dna_pss_kib is not None:
                    assert result['memory_rounds'][-1]['pss_kib'] <= args.max_dna_pss_kib, 'DNA retained-memory budget exceeded'
if __name__=='__main__':main()
