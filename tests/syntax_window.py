#!/usr/bin/env python3
"""Large-file highlighting retains distant comment and string openers."""
import ctypes as c
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from benchmark_editors import Session, V, Pos

class Cell(c.Structure):
    _fields_ = [('chars', c.c_uint32 * 6), ('width', c.c_char),
                ('attrs', c.c_uint), ('fg', c.c_uint8 * 4), ('bg', c.c_uint8 * 4)]

V.vterm_screen_get_cell.argtypes = [c.c_void_p, Pos, c.POINTER(Cell)]

def colors(session, word):
    found = set()
    for row, text in enumerate(session.text().splitlines()):
        if word in text:
            cell = Cell()
            assert V.vterm_screen_get_cell(session.screen, Pos(row, text.index(word)), c.byref(cell))
            found.add(tuple(cell.fg))
    return found

languages = ROOT / 'build/test-languages'
assert (languages / 'dyn/parser.so').exists(), 'Install the Dyn test grammar first'
with tempfile.TemporaryDirectory(prefix='dna-syntax-window-') as directory:
    root = Path(directory)
    config = root / 'dna.toml'
    config.write_text('reduced_motion = true\n[modules]\nkeymap = "vim"\n[languages.dyn]\nauto_start = false\n')
    env = dict(os.environ, DNA_CONFIG=str(config), DNA_DEFAULT_SERVERS='0',
               DNA_RECOVERY='0', DNA_DYN_LSP='', DNA_LANGUAGE_DIR=str(languages), HOME=str(root),
               XDG_CONFIG_HOME=str(root / 'config'), XDG_STATE_HOME=str(root / 'state'),
               TERM='xterm-256color', COLORTERM='truecolor',
               LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'))
    line = b'fn example() { value := "reference" } // note\n'
    head = line * ((17 << 20) // len(line))
    inner = b'fn inside() { value := "quoted" }\n'
    for mode in ('debug', 'release'):
        for gap in (600000, 3000000, 12000000):
            body = inner * (gap // len(inner))
            source = root / 'large.dyn'
            source.write_bytes(head + b'/* start\n' + body + b'end */\n' + line * 100)
            target = head.count(b'\n') + 1 + body.count(b'\n') - 5
            session = Session([str(ROOT / f'build/dna-{mode}'), '--tui', str(source)], env, str(root))
            try:
                session.wait(lambda: bool(colors(session, 'note')), timeout=15)
                session.wait(lambda: colors(session, 'note') != colors(session, 'fn'), timeout=15)
                session.settle(1.5)
                comment = colors(session, 'note')
                session.send(b':', lambda: '┌' in session.text(), timeout=10)
                session.settle(.05)
                os.write(session.fd, f'{target}\r'.encode())
                session.wait(lambda: bool(colors(session, 'inside')), timeout=15)
                session.wait(lambda: colors(session, 'inside') == comment, timeout=30)
                # A small scroll preserves the parser's context too.
                session.send(b'j', lambda: str(target + 1) + ':' in session.text(), timeout=15)
                assert colors(session, 'inside') == comment, (mode, gap, session.text())
            finally:
                session.close()
        # Horizontal scrolling can put the view far inside one string too.
        source = root / 'string.dyn'
        source.write_bytes(head + b'value := "' + b'a' * 12000000 + b'TAILMARK"\n')
        target = head.count(b'\n') + 1
        session = Session([str(ROOT / f'build/dna-{mode}'), '--tui', str(source)], env, str(root))
        try:
            session.wait(lambda: bool(colors(session, 'reference')), timeout=15)
            session.wait(lambda: colors(session, 'reference') != colors(session, 'fn'), timeout=15)
            session.settle(1.5)
            string_color = colors(session, 'reference')
            session.send(b':', lambda: '┌' in session.text(), timeout=10)
            session.settle(.05)
            os.write(session.fd, f'{target}\r'.encode())
            session.wait(lambda: 'value :=' in session.text(), timeout=15)
            session.settle(.1)
            os.write(session.fd, b'$')
            session.wait(lambda: bool(colors(session, 'TAILMARK')), timeout=15)
            session.wait(lambda: colors(session, 'TAILMARK') == string_color, timeout=30)
        finally:
            session.close()
print('PASS large-file syntax: distant block comments (600 KB, 3 MB, 12 MB) and strings (12 MB), debug/release')
