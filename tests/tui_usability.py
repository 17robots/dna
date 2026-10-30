#!/usr/bin/env python3
"""Real PTY Vim explorer ownership, command history and prefix guides."""
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from benchmark_editors import Session

binaries = [ROOT/'build'/name for name in (sys.argv[1:] or ('dna-debug', 'dna-release'))]
for binary in binaries:
    if not binary.is_file():
        raise SystemExit(f'Missing editor binary: {binary}; run just build debug and just build release first')

with tempfile.TemporaryDirectory(prefix='dna-vim-explorer-') as temporary:
    root = Path(temporary)
    files = root/'files'
    files.mkdir()
    source = files/'input.txt'
    source.write_text('KEEP_ORIGINAL\n')
    target = files/'target.txt'
    target.write_text('TARGET_BUFFER\n')
    config = root/'dna.toml'
    config.write_text('reduced_motion = true\n[modules]\nkeymap = "vim"\n')
    env = dict(os.environ, DNA_CONFIG=str(config), DNA_DEFAULT_SERVERS='0',
               DNA_RECOVERY='0', HOME=str(root), XDG_CONFIG_HOME=str(root/'config'),
               XDG_STATE_HOME=str(root/'state'), TERM='xterm-256color',
               LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'))
    for binary in binaries:
        session = Session([str(binary), '--tui', str(source)], env, str(files))

        def key(data):
            os.write(session.fd, data)
            session.settle(.03)

        try:
            session.wait(lambda: 'KEEP_ORIGINAL' in session.text())
            key(b' ')
            key(b'e')
            session.wait(lambda: 'target.txt' in session.text())
            key(b'/')
            key(b'target')
            key(b'\r')
            key(b'\r')
            session.wait(lambda: 'TARGET_BUFFER' in session.text())
            key(b'i')
            key(b'X')
            key(b'\x1b')
            key(b':')
            key(b'write')
            key(b'\r')
            deadline = time.monotonic()+3
            while target.read_text() != 'XTARGET_BUFFER\n':
                assert time.monotonic() < deadline, session.text()
                session.read(.01)
            assert source.read_text() == 'KEEP_ORIGINAL\n'
            key(b':')
            key(b'draft')
            session.wait(lambda: '> draft' in session.text())
            key(b'\x1b[A')
            session.wait(lambda: '> write' in session.text())
            key(b'\x1b[B')
            session.wait(lambda: '> draft' in session.text())
            key(b'\x1b')
            key(b'g')
            session.wait(lambda: 'Vim g' in session.text())
            key(b'\x1b')
            print('PASS real PTY Vim explorer ownership, history and prefix guide:', binary, flush=True)
        finally:
            session.close()
        target.write_text('TARGET_BUFFER\n')
