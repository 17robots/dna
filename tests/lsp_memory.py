#!/usr/bin/env python3
"""Small LSP document shadows must use sparse pages, even with huge pages enabled."""
import argparse
import json
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


def process_memory(pid):
    values = {}
    for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
        if line.startswith(('Pss:', 'AnonHugePages:')):
            name, value = line.split(':', 1)
            values[name] = int(value.split()[0])
    return values


with tempfile.TemporaryDirectory(prefix='dna-lsp-memory-') as temporary:
    directory = Path(temporary)
    config = directory / 'config.toml'
    config.write_text('reduced_motion = true\nautomatic_completion = false\nreload_config = false\n')
    sources = []
    for index in range(8):
        source = directory / f'file-{index}.dyn'
        source.write_text(f'// MEMORY_START_{index}\n' + '// padding\n' * 6000 + 'fn main() {}\n')
        sources.append(source)
    env = dict(os.environ, HOME=str(directory), XDG_CONFIG_HOME=str(directory / 'config'),
               XDG_STATE_HOME=str(directory / 'state'), XDG_CACHE_HOME=str(directory / 'cache'),
               TERM='xterm-256color', DNA_CONFIG=str(config), DNA_RECOVERY='0',
               DNA_DEFAULT_SERVERS='0', DNA_LANGUAGE_DIR=str(directory / 'languages'),
               DNA_DYN_LSP=shlex.join([sys.executable, str(ROOT / 'tests/fake_lsp.py')]),
               LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'))
    for name in ('LD_PRELOAD', 'DNA_RENDER_TRACE', 'DYN_EDITOR_SMOKE'):
        env.pop(name, None)
    session = Terminal([str(args.binary.resolve()), '--tui', str(sources[0])], env, directory)
    try:
        initial = None
        for index, source in enumerate(sources):
            if index:
                session.send(b':', .02)
                session.send(('open ' + str(source)).encode(), .02)
                session.send(b'\r', .02)
            deadline = time.monotonic() + 5
            while True:
                text = '\n'.join(session.rows())
                if f'MEMORY_START_{index}' in text and '!1' in text:
                    break
                assert time.monotonic() < deadline, ('LSP initialization/diagnostic timed out', index, session.rows())
                session.pump(.01)
            # The fixture diagnostic acknowledges didOpen. Allow the same UI
            # turn to finish copying the corresponding incremental shadow.
            session.pump(.05)
            if initial is None:
                initial = process_memory(session.pid)
        final = process_memory(session.pid)
        growth = final['Pss'] - initial['Pss']
        huge_growth = final['AnonHugePages'] - initial['AnonHugePages']
        assert huge_growth <= 0, ('small LSP documents add huge pages', huge_growth)
        assert growth < 8 * 1024, ('small LSP documents retain excessive memory', growth)
        print('PASS sparse LSP document growth:', json.dumps({
            'additional_documents': 7, 'pss_growth_kib': growth,
            'anon_huge_growth_kib': huge_growth,
        }))
    finally:
        session.close()
