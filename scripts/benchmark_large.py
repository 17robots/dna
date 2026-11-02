#!/usr/bin/env python3
"""Large-file comparison of DNA, Neovim and Helix in a real terminal.

Each editor opens one multi-line text file of the requested size, jumps to its
end, inserts one character there, saves, and quits. Times are measured from the
PTY key write to the screen (or file) acknowledging the action, as in
benchmark_editors.py. Memory is the PSS of the editor and its children after
opening and after saving. Files live on disk (not tmpfs) with a warm cache.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from benchmark_editors import Session, memory

ROW = b'0123456789 abcdefghijklmnopqrstuvwxyz line of a large benchmark file.\n'


def fixture(path, size):
    block = ROW * (1 << 14)
    with path.open('wb') as stream:
        stream.write(b'LARGE_START marker line\n')
        written = 0
        while written < size:
            stream.write(block)
            written += len(block)
        stream.write(b'LARGE_END marker line\n')
    # Warm the page cache so every editor reads from memory.
    with path.open('rb') as stream:
        while stream.read(1 << 24):
            pass


def command(editor, directory, path, binary):
    env = dict(os.environ, HOME=str(directory / 'home'), XDG_CONFIG_HOME=str(directory / 'config'),
               XDG_CACHE_HOME=str(directory / 'cache'), XDG_STATE_HOME=str(directory / 'state'),
               TERM='xterm-256color', COLORTERM='truecolor')
    for key in ('LD_PRELOAD', 'DYN_EDITOR_SMOKE', 'DNA_RENDER_TRACE'):
        env.pop(key, None)
    for name in ('home', 'config'):
        (directory / name).mkdir(exist_ok=True)
    if editor == 'dna':
        settings = directory / 'dna.toml'
        settings.write_text('reduced_motion = true\nautomatic_completion = false\nreload_config = false\n'
                            '[modules]\nkeymap = "vim"\n')
        env.update(DNA_CONFIG=str(settings), DNA_DEFAULT_SERVERS='0', DNA_RECOVERY='0',
                   LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'))
        return [str(binary), '--tui', str(path)], env
    if editor == 'nvim':
        return [shutil.which('nvim'), '--clean', '-n', '-i', 'NONE', '--cmd',
                'set noswapfile notermguicolors ttimeoutlen=10', str(path)], env
    settings = directory / 'helix.toml'
    settings.write_text('[editor]\nauto-completion = false\n[editor.lsp]\nenable = false\n')
    return [shutil.which('hx'), '-c', str(settings), str(path)], env


def run(editor, directory, path, binary, timeout):
    arguments, env = command(editor, directory, path, binary)
    size = path.stat().st_size
    result = {'editor': editor, 'bytes': size}
    session = Session(arguments, env, str(directory))
    try:
        result['open_ms'] = session.wait(lambda: 'LARGE_START' in session.text(), session.started, timeout)
        session.settle(.5)
        result['pss_open_kib'] = memory(session.pid)['pss_kib']
        end = b'G' if editor != 'helix' else b'ge'
        result['end_ms'] = session.send(end, lambda: 'LARGE_END' in session.text(), timeout)
        session.settle(.2)
        insert = b'A' if editor != 'helix' else b'A'
        os.write(session.fd, insert)
        session.settle(.3)
        result['keystroke_ms'] = session.send(b'Q', lambda: 'lineQ' in session.text(), timeout)
        os.write(session.fd, b'\x1b')
        session.settle(.3)
        before = path.stat().st_mtime_ns
        os.write(session.fd, b':')
        session.settle(.2)
        started = time.perf_counter_ns()
        os.write(session.fd, b'w\r')
        session.wait(lambda: path.stat().st_mtime_ns != before and path.stat().st_size == size + 1, started, timeout)
        result['save_ms'] = (time.perf_counter_ns() - started) / 1e6
        session.settle(.5)
        result['pss_saved_kib'] = memory(session.pid)['pss_kib']
        return result
    except Exception as error:
        result['error'] = str(error).splitlines()[0]
        return result
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mib', type=int, nargs='+', default=[100, 1024])
    parser.add_argument('--editors', nargs='+', choices=['dna', 'nvim', 'helix'], default=['dna', 'nvim', 'helix'])
    parser.add_argument('--dna', type=Path, default=ROOT / 'build/dna-release')
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--directory', type=Path, default=Path('/var/tmp'))
    parser.add_argument('--output', type=Path, default=ROOT / 'build/large-benchmark.json')
    args = parser.parse_args()
    report = []
    with tempfile.TemporaryDirectory(prefix='dna-large-benchmark-', dir=args.directory) as temporary:
        for mib in args.mib:
            for editor in args.editors:
                directory = Path(temporary) / f'{editor}-{mib}'
                directory.mkdir()
                path = directory / 'large.txt'
                fixture(path, mib << 20)
                result = run(editor, directory, path, args.dna.resolve(), args.timeout)
                result['mib'] = mib
                report.append(result)
                print(json.dumps(result), flush=True)
                path.unlink()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
