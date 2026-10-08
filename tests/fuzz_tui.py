#!/usr/bin/env python3
"""Seeded random terminal input for `dna --tui`, through a pty, inside bwrap.

Each run types a random mix of text, control bytes, CSI/SS3/kitty key
sequences (some cut short), SGR mouse reports, bracketed pastes and window
resizes. A run fails when DNA crashes or exits with an error, stops redrawing
after a resize, or leaves the terminal in raw mode when terminated.

Usage: fuzz_tui.py [FIRST_SEED] [RUNS] [CHUNKS]   (DNA_FUZZ_MODE=debug|release)
"""
import fcntl
import os
from pathlib import Path
import pty
import random
import select
import signal
import struct
import sys
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
first = int(sys.argv[1]) if len(sys.argv) > 1 else 1
runs = int(sys.argv[2]) if len(sys.argv) > 2 else 10
chunks = int(sys.argv[3]) if len(sys.argv) > 3 else 600
mode = os.environ.get('DNA_FUZZ_MODE', 'debug')
binary = ROOT / 'build' / f'dna-{mode}'

FINALS = b'ABCDEFHPQRSZ~umMhlsqtJKr'


def random_sequence(rng):
    kind = rng.randrange(14)
    if kind < 4:
        return bytes(rng.choice(b'abcdefghijklmnopqrstuvwxyz0123456789 .,;/-_=()[]{}"\'\n\t') for _ in range(rng.randrange(1, 12)))
    if kind == 4:
        # Control bytes, but rarely Ctrl+C/Ctrl+\ (they only reach DNA as keys).
        return bytes([rng.randrange(0, 32)])
    if kind == 5:
        return b'\x1b'
    if kind == 6:
        params = ';'.join(str(rng.randrange(0, 300)) for _ in range(rng.randrange(0, 4)))
        return b'\x1b[' + params.encode() + bytes([rng.choice(FINALS)])
    if kind == 7:
        return b'\x1bO' + bytes([rng.choice(b'ABCDHFPQRS')])
    if kind == 8:
        # Kitty keyboard protocol: code;modifiers[:event]u
        code = rng.choice([27, 13, 9, 127, 57399, rng.randrange(32, 127), rng.randrange(0x80, 0x2ffff)])
        modifiers = rng.randrange(1, 16)
        event = f':{rng.randrange(1, 4)}' if rng.random() < 0.3 else ''
        return f'\x1b[{code};{modifiers}{event}u'.encode()
    if kind == 9:
        # SGR mouse: press, drag, release, wheel, with modifier bits.
        button = rng.choice([0, 1, 2, 32, 35, 64, 65]) | rng.choice([0, 0, 4, 8, 16])
        column = rng.randrange(1, 140)
        row = rng.randrange(1, 60)
        return f'\x1b[<{button};{column};{row}{rng.choice("Mm")}'.encode()
    if kind == 10:
        inner = bytes(rng.randrange(0, 256) for _ in range(rng.randrange(0, 64)))
        return b'\x1b[200~' + inner + (b'\x1b[201~' if rng.random() < 0.9 else b'')
    if kind == 11:
        # A sequence cut off part way.
        whole = b'\x1b[<0;' + str(rng.randrange(1, 99)).encode() + b';'
        return whole[:rng.randrange(1, len(whole) + 1)]
    if kind == 12:
        return bytes(rng.randrange(0, 256) for _ in range(rng.randrange(1, 8)))
    # Leader and command keys that open panels.
    return rng.choice([b' ', b':', b'\x1b[27u', b'i', b'v', b'g', b' f', b' e', b' t', b' ?', b'\x17v'])


def resize(fd, rows, columns):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, columns, 0, 0))


transcript = bytearray()


def drain(fd, seconds, sink):
    deadline = time.time() + seconds
    alive = True
    while time.time() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.02)
        if not ready:
            continue
        try:
            data = os.read(fd, 65536)
        except OSError:
            data = b''
        if not data:
            alive = False
            break
        sink.append(data)
        transcript.extend(data)
        del transcript[:-262144]
    return alive


failures = 0
# Runs where random keys quit DNA cleanly before the input ran out.
early = 0
for seed in range(first, first + runs):
    rng = random.Random(seed)
    with tempfile.TemporaryDirectory(prefix='dna-fuzz-tui-') as directory:
        work = Path(directory)
        project = work / 'project'
        (project / 'sub').mkdir(parents=True)
        (project / 'notes.txt').write_text('first\nsecond\nthird line with words\n')
        (project / 'main.dyn').write_text('fn main() {\n  value := 1\n}\n')
        (project / 'sub' / 'data.json').write_text('{"key": [1, 2, 3]}\n')
        (work / 'home').mkdir()
        modules = rng.choice(['', '[modules]\nexplorer = "tree"\n', '[modules]\npicker = "dropdown"\n', '[modules]\nkeymap = "vim"\n'])
        (work / 'config.toml').write_text('shell = "/bin/sh"\nreload_config = false\n' + modules)
        environment = {
            'PATH': '/usr/bin:/bin', 'TERM': 'xterm-256color', 'HOME': str(work / 'home'),
            'XDG_CONFIG_HOME': str(work / 'home'), 'XDG_STATE_HOME': str(work / 'home'), 'XDG_DATA_HOME': str(work / 'home'),
            'DNA_CONFIG': str(work / 'config.toml'), 'DNA_RECOVERY': '0', 'DNA_DEFAULT_SERVERS': '0', 'DNA_DYN_LSP': '',
            'LD_LIBRARY_PATH': str(ROOT / 'build/deps/install/lib'),
        }
        command = ['bwrap', '--ro-bind', '/', '/', '--dev', '/dev', '--proc', '/proc', '--tmpfs', '/tmp',
                   '--bind', str(work), str(work), '--unshare-net', '--die-with-parent', '--chdir', str(project),
                   str(binary), '--tui', rng.choice(['notes.txt', 'main.dyn', 'sub/data.json'])]
        pid, fd = pty.fork()
        if pid == 0:
            os.execvpe(command[0], command, environment)
        rows, columns = 30, 100
        resize(fd, rows, columns)
        transcript.clear()
        output = []
        problem = None
        alive = drain(fd, 1.0, output)
        for _ in range(chunks):
            if not alive:
                break
            if rng.random() < 0.01:
                rows, columns = rng.randrange(4, 60), rng.randrange(10, 200)
                resize(fd, rows, columns)
            try:
                os.write(fd, random_sequence(rng))
            except OSError:
                alive = False
                break
            alive = drain(fd, rng.choice([0.0, 0.0, 0.002, 0.01]), output)
            # DNA quit and handed the terminal back: stop typing into a
            # cooked tty, where Ctrl+C bytes would become SIGINT.
            if alive and b'\x1b[?1049l' in b''.join(output[-4:]):
                drain(fd, 3.0, output)
                alive = False
                break
            del output[:-4]
        if not alive:
            early += 1
        if alive:
            # Still responsive: a resize must produce a fresh frame.
            drain(fd, 0.5, output)
            output.clear()
            resize(fd, rows + 1, columns)
            alive = drain(fd, 3.0, output)
            if alive and not b''.join(output):
                problem = 'no redraw after a resize'
            output.clear()
            # Terminated, the terminal is handed back.
            # To DNA itself (the terminal's foreground group), not to bwrap.
            try:
                os.killpg(os.tcgetpgrp(fd), signal.SIGTERM)
            except OSError:
                os.kill(pid, signal.SIGTERM)
            drain(fd, 2.0, output)
            if b'\x1b[?1049l' not in b''.join(output):
                problem = problem or 'terminal not restored after SIGTERM'
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        _, status = os.waitpid(pid, 0)
        os.close(fd)
        if os.WIFSIGNALED(status) and os.WTERMSIG(status) not in (signal.SIGTERM, signal.SIGKILL):
            problem = problem or f'killed by signal {os.WTERMSIG(status)}'
        elif os.WIFEXITED(status) and os.WEXITSTATUS(status) != 0:
            problem = problem or f'exit status {os.WEXITSTATUS(status)}'
        if problem:
            failures += 1
            kept = ROOT / 'build' / f'fuzz-tui-failure-{seed}.txt'
            kept.write_bytes(bytes(transcript))
            # The panic message is the last plain line DNA printed.
            text = bytes(transcript).decode('utf-8', 'replace')
            lines = [line.strip() for line in text.replace('\r', '\n').split('\n') if line.strip() and '\x1b' not in line]
            print(f'FAIL seed {seed}: {problem}: {lines[-3:] if lines else ""}  ({kept})', flush=True)
print(f'fuzz tui: {runs - failures}/{runs} seeds clean, {chunks} chunks each ({mode}); {early} quit early')
sys.exit(1 if failures else 0)
