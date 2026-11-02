#!/usr/bin/env python3
"""Large didOpen/didChange bodies are escaped in the background, in order.

Opens a 40 MiB file with the fixture server, deletes everything and undoes it
twice (two 40 MiB incremental changes, the second arriving while the first is
being encoded), types meanwhile, then saves.
The fixture compares the saved text with the text it rebuilt from every
message, so a lost, reordered or corrupt body fails the test.
"""
import argparse
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from compare_completion import Terminal

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', type=Path, default=ROOT / 'build/dna-release')
args = parser.parse_args()

with tempfile.TemporaryDirectory(prefix='dna-lsp-large-') as temporary:
    directory = Path(temporary)
    config = directory / 'config.toml'
    config.write_text('reduced_motion = true\nautomatic_completion = false\nreload_config = false\n'
                      '[modules]\nkeymap = "vim"\n')
    source = directory / 'large.dyn'
    row = '// "quoted" \\ back\tslash é😀 line of a large language-server document\n'
    body = row * ((40 << 20) // len(row.encode()))
    source.write_text('// LARGE_START\n' + body + 'fn main() {}\n')
    saves = directory / 'saves.log'
    env = dict(os.environ, HOME=str(directory), XDG_CONFIG_HOME=str(directory / 'config'),
               XDG_STATE_HOME=str(directory / 'state'), XDG_CACHE_HOME=str(directory / 'cache'),
               TERM='xterm-256color', DNA_CONFIG=str(config), DNA_RECOVERY='0',
               DNA_DEFAULT_SERVERS='0', DNA_LANGUAGE_DIR=str(directory / 'languages'),
               DNA_DYN_LSP=shlex.join([sys.executable, str(ROOT / 'tests/fake_lsp.py')]),
               FAKE_LSP_SAVES=str(saves), LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'))
    for name in ('LD_PRELOAD', 'DNA_RENDER_TRACE', 'DYN_EDITOR_SMOKE'):
        env.pop(name, None)
    session = Terminal([str(args.binary.resolve()), '--tui', str(source)], env, directory)

    def wait(predicate, what, limit=60):
        deadline = time.monotonic() + limit
        while not predicate():
            assert time.monotonic() < deadline, (what, session.rows())
            session.pump(.01)

    try:
        wait(lambda: 'LARGE_START' in '\n'.join(session.rows()) and '!1' in '\n'.join(session.rows()), 'didOpen')
        # Delete everything, then undo: the undo reinserts 40 MiB in one change.
        session.send(b'ggdG', .3)
        # Undo, redo, undo in one burst: the second 40 MiB change arrives
        # while the first is still being encoded, and must wait its turn.
        session.send(b'u\x12u', .05)
        # The editor keeps answering while the change is encoded.
        started = time.monotonic()
        # One burst: text after O must type even though it was read while
        # text input was still off.
        session.send(b'ggOTYPED_WHILE_ENCODING', 0)
        wait(lambda: "TYPED_WHILE_ENCODING" in "\n".join(session.rows()), "typing during encode", 60)
        typed = time.monotonic() - started
        session.send(b'\x1b', .5)
        session.send(b':w\r', .05)
        wait(lambda: saves.exists() and saves.read_text().strip(), 'didSave', 120)
        result = saves.read_text().split()
        assert result[0] == 'match', result
        assert int(result[1]) > 40 << 20 >> 1, result
        print(f'PASS large LSP bodies encode in the background, in order (typed in {typed * 1000:.0f} ms)')
    finally:
        session.close()
