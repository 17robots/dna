#!/usr/bin/env python3
"""Document and workspace symbol pickers: type to filter, Enter goes there."""
import argparse
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from compare_completion import Terminal

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', type=Path, action='append')
args = parser.parse_args()
binaries = args.binary or [ROOT / 'build/dna-debug', ROOT / 'build/dna-release']

SOURCE = ''.join(['// top\n', 'fn alpha\n', 'method alpha_inner\n', '\n' * 40,
                  'fn bravo\n', '\n' * 40, 'fn charlie_target\n', 'method deep_one\n', 'end\n'])


def line_of(name):
    return SOURCE.split('\n').index(next(l for l in SOURCE.split('\n') if l.endswith(' ' + name))) + 1


for binary in binaries:
    with tempfile.TemporaryDirectory(prefix='dna-lsp-symbols-') as temporary:
        directory = Path(temporary)
        config = directory / 'config.toml'
        config.write_text('reduced_motion = true\nautomatic_completion = false\nreload_config = false\n')
        source = directory / 'symbols.dyn'
        source.write_text(SOURCE)
        env = dict(os.environ, HOME=str(directory), XDG_CONFIG_HOME=str(directory / 'config'),
                   XDG_STATE_HOME=str(directory / 'state'), XDG_CACHE_HOME=str(directory / 'cache'),
                   TERM='xterm-256color', DNA_CONFIG=str(config), DNA_RECOVERY='0',
                   DNA_DEFAULT_SERVERS='0', DNA_LANGUAGE_DIR=str(directory / 'languages'),
                   DNA_DYN_LSP=shlex.join([sys.executable, str(ROOT / 'tests/fake_lsp.py')]),
                   LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'))
        for name in ('LD_PRELOAD', 'DNA_RENDER_TRACE', 'DYN_EDITOR_SMOKE'):
            env.pop(name, None)
        session = Terminal([str(binary.resolve()), '--tui', str(source)], env, directory)

        def screen():
            return '\n'.join(session.rows())

        def wait(predicate, what, limit=15):
            deadline = time.monotonic() + limit
            while not predicate():
                assert time.monotonic() < deadline, (what, session.rows())
                session.pump(.01)

        def cursor_line():
            found = re.search(r' (\d+):\d+ ', session.rows()[-1])
            return int(found.group(1)) if found else 0

        def command(text):
            session.send(b':', .2)
            session.send(text.encode(), .2)
            session.send(b'\r', .3)

        try:
            wait(lambda: '!1' in screen(), 'server ready (diagnostic)')
            # Document symbols: nested, filtered by typing, Enter jumps.
            command('symbols')
            wait(lambda: 'charlie_target' in screen() and 'alpha_inner' in screen(), 'document symbols')
            assert re.search(r'   alpha_inner  method', screen()), ('children are indented', screen())
            session.send(b'chtar', .3)
            wait(lambda: '> chtar_' in screen() and 'bravo  function' not in screen(), 'filtered list')
            session.send(b'\r', .3)
            wait(lambda: cursor_line() == line_of('charlie_target'), 'jump to charlie_target')
            assert 'selected' not in session.rows()[-1] and f' {line_of("charlie_target")}:4 ' in session.rows()[-1], \
                ('a symbol jump lands on the name and selects nothing', session.rows()[-1])
            # Backspace widens the filter again; Space s opens it too.
            session.send(b' ', .3)
            session.send(b's', .3)
            wait(lambda: 'bravo  function' in screen(), 'reopened')
            session.send(b'zz', .2)
            wait(lambda: 'no matching symbols' in screen(), 'nothing matches zz')
            session.send(b'\x7f\x7f', .2)
            session.send(b'bra', .3)
            session.send(b'\r', .3)
            wait(lambda: cursor_line() == line_of('bravo'), 'jump to bravo')
            # Workspace symbols: the query goes to the server.
            session.send(b' ', .3)
            session.send(b'S', .5)
            session.send(b'alp', .5)
            wait(lambda: 'alpha  function' in screen() and 'bravo  function' not in screen(), 'server-filtered workspace symbols')
            session.send(b'\r', .3)
            wait(lambda: cursor_line() == line_of('alpha'), 'jump to alpha')
            print(f'PASS document and workspace symbol pickers: nesting, filter, backspace, jump ({binary.name})', flush=True)
        finally:
            session.close()
