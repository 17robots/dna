#!/usr/bin/env python3
"""Compare real Dyn LSP completion in isolated DNA, Neovim, and Helix TUIs.

The endpoint is a completion label reconstructed from PTY output, not physical
presentation. DNA uses its default timeout unless --dna-delay-ms is supplied.
Helix uses its default timeout unless --helix-delay-ms is supplied.
Neovim uses built-in LSP autotrigger (no plugin). Trigger-character requests
may bypass editor debounce. The common typed prefix is h.
The proxy records monotonic receipt times without changing protocol messages.
"""
import argparse
import ctypes
import fcntl
import json
import math
import statistics
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def proxy(log, command):
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    lock = threading.Lock()
    def copy(source, target, direction):
        while True:
            headers = bytearray()
            while not headers.endswith(b'\r\n\r\n'):
                byte = source.read(1)
                if not byte:
                    if direction == 'request':
                        child.terminate()
                    return
                headers.extend(byte)
            size = next(int(line.split(b':', 1)[1]) for line in headers.split(b'\r\n') if line.lower().startswith(b'content-length:'))
            payload = source.read(size)
            if len(payload) != size:
                return
            message = json.loads(payload)
            record = dict(time_ns=time.monotonic_ns(), direction=direction, message=message)
            with lock, open(log, 'a') as output:
                output.write(json.dumps(record) + '\n')
            target.write(headers + payload)
            target.flush()
    outgoing = threading.Thread(target=copy, args=(sys.stdin.buffer, child.stdin, 'request'), daemon=True)
    outgoing.start()
    try:
        copy(child.stdout, sys.stdout.buffer, 'response')
    finally:
        child.terminate()
        child.wait()


class Rect(ctypes.Structure):
    _fields_ = [('start_row', ctypes.c_int), ('end_row', ctypes.c_int), ('start_col', ctypes.c_int), ('end_col', ctypes.c_int)]


class Terminal:
    def __init__(self, command, env, cwd):
        self.lib = v = ctypes.CDLL('libvterm.so.0')
        v.vterm_new.restype = ctypes.c_void_p
        v.vterm_new.argtypes = [ctypes.c_int, ctypes.c_int]
        v.vterm_set_utf8.argtypes = [ctypes.c_void_p, ctypes.c_int]
        v.vterm_input_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
        v.vterm_obtain_screen.restype = ctypes.c_void_p
        v.vterm_obtain_screen.argtypes = [ctypes.c_void_p]
        v.vterm_screen_reset.argtypes = [ctypes.c_void_p, ctypes.c_int]
        v.vterm_screen_enable_altscreen.argtypes = [ctypes.c_void_p, ctypes.c_int]
        v.vterm_screen_get_text.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, Rect]
        v.vterm_screen_get_text.restype = ctypes.c_size_t
        v.vterm_free.argtypes = [ctypes.c_void_p]
        self.terminal = v.vterm_new(32, 120)
        v.vterm_set_utf8(self.terminal, 1)
        self.screen = v.vterm_obtain_screen(self.terminal)
        v.vterm_screen_enable_altscreen(self.screen, 1)
        v.vterm_screen_reset(self.screen, 1)
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(cwd)
            os.execvpe(command[0], command, env)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack('HHHH', 32, 120, 0, 0))

    def pump(self, duration):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            if not select.select([self.fd], [], [], min(.001, max(0, deadline-time.monotonic())))[0]:
                continue
            data = os.read(self.fd, 65536)
            if not data:
                raise RuntimeError('editor exited')
            self.lib.vterm_input_write(self.terminal, data, len(data))

    def rows(self):
        result = []
        for row in range(32):
            buffer = ctypes.create_string_buffer(481)
            length = self.lib.vterm_screen_get_text(self.screen, buffer, 480, Rect(row, row+1, 0, 120))
            result.append(buffer.raw[:length].decode(errors='replace'))
        return result

    def send(self, keys, settle=.15):
        os.write(self.fd, keys)
        self.pump(settle)

    def close(self):
        try:
            os.killpg(self.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        os.waitpid(self.pid, 0)
        os.close(self.fd)
        self.lib.vterm_free(self.terminal)


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def run(editor, directory, args):
    directory.mkdir(parents=True, exist_ok=True)
    fixture = directory/'example.dyn'
    fixture.write_text('fn main() {\n  \n}\nfn helper_unique() {}\n')
    log = directory/'lsp.jsonl'
    proxy_command = [sys.executable, str(Path(__file__).resolve()), '--proxy', str(log), args.dyn, 'lsp']
    env = dict(os.environ, TERM='xterm-256color', XDG_CONFIG_HOME=str(directory/'config'), XDG_STATE_HOME=str(directory/'state'), XDG_CACHE_HOME=str(directory/'cache'))
    if editor == 'dna':
        config = directory/'dna.toml'
        config.write_text('reduced_motion = true\n' + ('[lsp]\ncompletion_delay_ms = '+str(args.dna_delay_ms)+'\n' if args.dna_delay_ms is not None else ''))
        env.update(DNA_CONFIG=str(config), DNA_RECOVERY='0', DNA_DEFAULT_SERVERS='0', DNA_DYN_LSP=__import__('shlex').join(proxy_command))
        command = [args.dna, '--tui', str(fixture)]
    elif editor == 'nvim':
        config = directory/'init.lua'
        config.write_text('''vim.opt.swapfile = false
vim.opt.shadafile = 'NONE'
vim.opt.completeopt = {'menuone', 'noselect'}
vim.api.nvim_create_autocmd('BufReadPost', {callback = function()
 vim.bo.filetype = 'dyn'
 vim.lsp.start({name='dyn', cmd=COMMAND, root_dir=ROOT, on_attach=function(client, bufnr)
  vim.lsp.completion.enable(true, client.id, bufnr, {autotrigger=true})
 end})
end})
'''.replace('COMMAND', '{'+','.join(json.dumps(p) for p in proxy_command)+'}').replace('ROOT', json.dumps(str(directory))))
        command = [shutil.which('nvim'), '-u', str(config), '-i', 'NONE', str(fixture)]
    else:
        helix = directory/'config/helix'
        helix.mkdir(parents=True)
        (helix/'config.toml').write_text('[editor]\n' + ('completion-timeout = '+str(args.helix_delay_ms)+'\n' if args.helix_delay_ms is not None else ''))
        (helix/'languages.toml').write_text('[language-server.dyn]\ncommand = '+json.dumps(proxy_command[0])+'\nargs = '+json.dumps(proxy_command[1:])+'\n[[language]]\nname = "dyn"\nscope = "source.dyn"\nfile-types = ["dyn"]\nroots = []\nlanguage-servers = ["dyn"]\n')
        command = [shutil.which('hx'), str(fixture)]
    terminal = Terminal(command, env, directory)
    results = []
    try:
        deadline = time.monotonic()+15
        while time.monotonic()<deadline:
            terminal.pump(.05)
            if any(r['message'].get('method') == 'textDocument/didOpen' for r in records(log)):
                break
        else:
            raise RuntimeError('LSP didOpen timeout: '+str(terminal.rows()))
        terminal.pump(.5)
        terminal.send(b'gg' if editor != 'helix' else b'gg')
        terminal.send(b'j')
        terminal.send(b'A' if editor == 'nvim' else b'a')
        for sample in range(args.samples):
            before = time.monotonic_ns()
            terminal.send(b'h', settle=0)
            deadline = time.monotonic()+10
            visible = None
            while time.monotonic()<deadline:
                terminal.pump(.001)
                rows=terminal.rows()
                if any('helper_unique' in row and 'fn helper_unique() {}' not in row for row in rows):
                    visible=time.monotonic_ns()
                    break
            current=records(log)
            requests=[r for r in current if r['time_ns']>=before and r['direction']=='request' and r['message'].get('method')=='textDocument/completion']
            if visible is None or not requests:
                raise RuntimeError(f'{editor} completion failed: requests={len(requests)}\n'+ '\n'.join(terminal.rows()))
            request=requests[-1]
            response=next(r for r in current if r['direction']=='response' and r['message'].get('id')==request['message']['id'] and 'method' not in r['message'])
            results.append(dict(editor=editor, trigger_context=request['message']['params'].get('context'), sample=sample, phase='first' if sample==0 else 'warm', input_ns=before, request_ns=request['time_ns'], response_ns=response['time_ns'], popup_ns=visible, request_ms=(request['time_ns']-before)/1e6, server_ms=(response['time_ns']-request['time_ns'])/1e6, popup_ms=(visible-before)/1e6, response_to_popup_ms=(visible-response['time_ns'])/1e6))
            if editor == 'dna':
                terminal.send(b'\x1b[27u')
                terminal.send(b'\x1b[27u')
                terminal.send(b'u')
                terminal.send(b'gg')
                terminal.send(b'j')
                terminal.send(b'a')
            else:
                terminal.send(b'\x05' if editor=='nvim' else b'\x1b')
                if editor != 'nvim':
                    terminal.send(b'a')
                terminal.send(b'\x7f', .3)
                terminal.send(b'\x05' if editor=='nvim' else b'\x1b')
                if editor != 'nvim':
                    terminal.send(b'a')
        return results
    finally:
        terminal.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editors', choices=['dna','nvim','helix'], nargs='+', default=['dna','nvim','helix'])
    parser.add_argument('--dna-delay-ms', type=int)
    parser.add_argument('--helix-delay-ms', type=int)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--samples', type=int, default=11)
    parser.add_argument('--dyn', default=shutil.which('dyn'))
    parser.add_argument('--dna', default=str(ROOT/'dna'))
    parser.add_argument('--output', type=Path, default=ROOT/'build/comparison-completion')
    args=parser.parse_args()
    args.output=args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.samples < 1 or args.rounds < 1:
        parser.error('--samples and --rounds must be positive')
    metadata={'endpoint':'completion label reconstructed from PTY output', 'clock':'monotonic_ns', 'fixture':'fn main() {\n  \n}\nfn helper_unique() {}\n', 'prefix':'h', 'first_sample':'first completion in fresh editor/server; filesystem/compiler caches are not cleared', 'dna_delay_ms':args.dna_delay_ms, 'helix_delay_ms':args.helix_delay_ms, 'neovim':'built-in LSP completion autotrigger; no plugin', 'dna_binary':args.dna, 'dyn_binary':args.dyn}
    metadata['versions']={}
    for name, program in [('dyn',args.dyn),('nvim',shutil.which('nvim')),('helix',shutil.which('hx'))]:
        if program:
            version=subprocess.run([program,'--version'],capture_output=True,text=True,check=True).stdout.splitlines()
            metadata['versions'][name]=version[0] if version else ''
    metadata['rounds']=args.rounds
    metadata['samples_per_round']=args.samples
    (args.output/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    result=[]
    summaries=[]
    for editor in args.editors:
        recent=[]
        for round_number in range(args.rounds):
            with tempfile.TemporaryDirectory(prefix=editor+'-',dir=args.output) as temporary:
                directory=Path(temporary)
                try:
                    trial=run(editor,directory,args)
                    for row in trial:
                        row['round']=round_number
                    recent.extend(trial)
                    result.extend(trial)
                finally:
                    if (directory/'lsp.jsonl').exists():
                        shutil.copyfile(directory/'lsp.jsonl',args.output/(editor+'-'+str(round_number)+'-lsp.jsonl'))
        summary={'editor':editor}
        for phase in ('first','warm'):
            values=[row for row in recent if row['phase']==phase]
            if not values:
                continue
            summary[phase]={'samples':len(values)}
            for metric in ('request_ms','server_ms','response_to_popup_ms','popup_ms'):
                numbers=sorted(row[metric] for row in values)
                summary[phase][metric]={'median':statistics.median(numbers), 'p95':numbers[math.ceil(len(numbers)*.95)-1], 'max':max(numbers)}
        summaries.append(summary)
        print(json.dumps(summary),flush=True)
    (args.output/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--proxy':
        proxy(sys.argv[2],sys.argv[3:])
    else:
        main()
