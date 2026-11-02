#!/usr/bin/env python3
"""Text objects and syntax selection anywhere in medium and large files.

A file with thousands of objects must have them all, not just the first ones;
a file above the large-file threshold (16 MiB) answers from its streamed tree.
"""
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from benchmark_editors import Session

languages = ROOT / 'build/test-languages'
assert (languages / 'dyn/textobjects.scm').exists(), 'Install the Dyn test grammar first'
LINE = b'fn example() { value := "reference" } // note\n'


def selected(session):
    found = re.search(r'selected (\d+)', session.text().splitlines()[-1])
    return int(found.group(1)) if found else 0


with tempfile.TemporaryDirectory(prefix='dna-syntax-objects-') as directory:
    root = Path(directory)
    config = root / 'dna.toml'
    config.write_text('reduced_motion = true\n[languages.dyn]\nauto_start = false\n')
    env = dict(os.environ, DNA_CONFIG=str(config), DNA_DEFAULT_SERVERS='0',
               DNA_RECOVERY='0', DNA_DYN_LSP='', DNA_LANGUAGE_DIR=str(languages), HOME=str(root),
               XDG_CONFIG_HOME=str(root / 'config'), XDG_STATE_HOME=str(root / 'state'),
               TERM='xterm-256color', LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'))
    for mode in ('debug', 'release'):
        # 4,000 objects (four per line), then a 17 MiB file.
        for lines in (1000, (17 << 20) // len(LINE) + 1):
            source = root / 'objects.dyn'
            source.write_bytes(LINE * lines)
            target = lines * 3 // 4
            session = Session([str(ROOT / f'build/dna-{mode}'), '--tui', str(source)], env, str(root))
            try:
                session.wait(lambda: 'reference' in session.text(), timeout=20)
                session.send(b':', lambda: '┌' in session.text(), timeout=10)
                session.settle(.05)
                session.send(f'{target}\r'.encode(), lambda: f'{target}:' in session.text(), timeout=20)
                # Into the body; then maf (around function) once parsed.
                for key in b'lllllllllllllll':
                    os.write(session.fd, bytes([key]))
                    session.settle(.02)
                session.settle(1)
                for attempt in range(40):
                    for key in (b'm', b'a', b'f'):
                        os.write(session.fd, key)
                        session.settle(.05)
                    session.settle(.2)
                    if selected(session) == 37:
                        break
                    os.write(session.fd, b'\x1b')
                    session.settle(.3)
                assert selected(session) == 37, (mode, lines, session.text().splitlines()[-3:])
                # Alt-o grows to the enclosing node: here the whole file.
                session.send(b'\x1bo', lambda: selected(session) > 37, timeout=10)
                assert selected(session) == len(LINE) * lines - 1 or selected(session) == len(LINE) * lines, (mode, lines, selected(session))
            finally:
                session.close()
print('PASS text objects past the first thousand and in a 17 MiB file; syntax selection grows to the file (debug/release)')
