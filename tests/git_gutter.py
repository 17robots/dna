#!/usr/bin/env python3
"""Gutter markers for lines added, modified and deleted since the committed
file, updated as you edit and after saving; none outside a repository."""
import argparse
import os
from pathlib import Path
import subprocess
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
ORIGINAL = ''.join(f'line {number:02}\n' for number in range(1, 21))


def markers(rows, count):
    """Marker per file line (1-based) from the gutter: the glyph right before
    the text column."""
    found = {}
    for row in rows[:-1]:
        text = row.rstrip()
        if 'line ' not in text and 'NEW' not in text and 'CHANGED' not in text:
            continue
        number = text[:6].strip().split(' ')[0] if text[:6].strip() else ''
        if not number.isdigit():
            continue
        sign = text[6:7]
        if sign in ('▎', '▔'):
            found[text[7:].strip() or number] = sign
    return found


for binary in binaries:
    with tempfile.TemporaryDirectory(prefix='dna-git-gutter-') as temporary:
        directory = Path(temporary)
        repository = directory / 'repo'
        repository.mkdir()
        source = repository / 'notes.txt'
        source.write_text(ORIGINAL)
        git = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@e', GIT_COMMITTER_NAME='t',
                   GIT_COMMITTER_EMAIL='t@e', HOME=str(directory))
        for command in (['init', '-q'], ['add', 'notes.txt'], ['commit', '-qm', 'first']):
            subprocess.run(['git', *command], cwd=repository, env=git, check=True)
        outside = directory / 'loose.txt'
        outside.write_text('loose\n')
        config = directory / 'config.toml'
        # Absolute numbers keep the gutter text predictable.
        config.write_text('reduced_motion = true\nreload_config = false\nrelative_numbers = false\n[modules]\nkeymap = "vim"\n')
        env = dict(git, XDG_CONFIG_HOME=str(directory / 'config'), XDG_STATE_HOME=str(directory / 'state'),
                   TERM='xterm-256color', DNA_CONFIG=str(config), DNA_RECOVERY='0', DNA_DEFAULT_SERVERS='0',
                   LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'))
        for name in ('LD_PRELOAD', 'DNA_RENDER_TRACE', 'DYN_EDITOR_SMOKE'):
            env.pop(name, None)
        session = Terminal([str(binary.resolve()), '--tui', str(source)], env, repository)

        def rows():
            return session.rows()

        def wait(predicate, what, limit=10):
            deadline = time.monotonic() + limit
            while not predicate():
                assert time.monotonic() < deadline, (what, rows())
                session.pump(.01)

        def gutter_sign(text):
            for row in rows()[:-1]:
                if row.rstrip().endswith(text):
                    return row[row.index(text) - 2]
            return None

        try:
            wait(lambda: any('line 01' in row for row in rows()), 'file shown')
            session.pump(.5)
            assert gutter_sign('line 05') == ' ', ('clean file has no markers', rows())
            # Modify line 3, add a line after 6, delete line 10.
            session.send(b'3G', .1)
            session.send(b'ccCHANGED\x1b', .2)
            session.send(b'6G', .1)
            session.send(b'oNEW\x1b', .2)
            session.send(b'11Gdd', .3)
            wait(lambda: gutter_sign('CHANGED') == '▎' and gutter_sign('NEW') == '▎', 'modified and added markers')
            wait(lambda: gutter_sign('line 11') == '▔', 'deletion marker on the following line')
            assert gutter_sign('line 05') == ' ' and gutter_sign('line 12') == ' ', ('unchanged lines unmarked', rows())
            # Saving keeps the markers: the comparison is with the commit.
            session.send(b':w\r', .5)
            session.pump(1)
            assert gutter_sign('CHANGED') == '▎', ('markers survive saving', rows())
            # Undoing everything clears them.
            session.send(b'uuu', .5)
            wait(lambda: gutter_sign('line 03') == ' ' and gutter_sign('line 10') == ' ', 'undo clears markers')
            # A file outside any repository has none.
            session.send(b':e ' + str(outside).encode() + b'\r', .5)
            wait(lambda: any(row.rstrip().endswith('loose') for row in rows()), 'loose file shown')
            session.send(b'ggOEXTRA\x1b', .5)
            session.pump(.5)
            assert gutter_sign('EXTRA') == ' ', ('no markers outside a repository', rows())
            print(f'PASS git gutter: added, modified, deleted, after save, undo, outside a repository ({binary.name})', flush=True)
        finally:
            session.close()
