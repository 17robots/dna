#!/usr/bin/env python3
"""Commands report what happened, and typos never run another command.

Real PTY checks, for both keymaps: an unknown : command reports itself
instead of running the nearest fuzzy match; arrows still pick a palette row;
searches that find nothing, writes and :messages report in the status line;
:q! and :qa! discard; :help and :keys open generated references. Also checks
the command line: --help, and an unknown option exits 2 without opening.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import private_display  # hides the desktop display; see tests/private_display.py

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from benchmark_editors import QUIET, Session


def fail(message, session=None):
    raise SystemExit('FAIL ' + message + ('\n' + session.text() if session else ''))


def status(session):
    return session.grid()[-1]


def main():
    binaries = [ROOT/'build'/name for name in (sys.argv[1:] or ('dna-release',))]
    for binary in binaries:
        if not binary.is_file():
            raise SystemExit(f'Missing editor binary: {binary}; run just build release first')
    with tempfile.TemporaryDirectory(prefix='dna-feedback-') as temporary:
        root = Path(temporary)
        project = root/'project'
        project.mkdir()
        notes = project/'notes.txt'
        base_env = dict(os.environ, DNA_DEFAULT_SERVERS='0', DNA_RECOVERY='0', HOME=str(root),
                        XDG_CONFIG_HOME=str(root/'config'), XDG_STATE_HOME=str(root/'state'),
                        TERM='xterm-256color', LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'))
        for name in ('DISPLAY', 'WAYLAND_DISPLAY'):
            base_env.pop(name, None)
        for binary in binaries:
            usage = subprocess.run([str(binary), '--help'], env=base_env, capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
            if usage.returncode != 0 or not usage.stdout.startswith('Usage: dna') or usage.stderr:
                fail(f'--help: {usage.returncode} {usage.stdout!r} {usage.stderr!r}')
            unknown = subprocess.run([str(binary), '--bogus'], env=base_env, capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
            if unknown.returncode != 2 or "unknown option '--bogus'" not in unknown.stderr:
                fail(f'unknown option: {unknown.returncode} {unknown.stderr!r}')
            no_terminal = subprocess.run([str(binary), '--tui'], env=base_env, capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
            if no_terminal.returncode != 1 or 'needs a terminal' not in no_terminal.stderr:
                fail(f'--tui without a terminal: {no_terminal.returncode} {no_terminal.stderr!r}')
            print('PASS command line help and errors:', binary.name, flush=True)
            for keymap in ('helix', 'vim'):
                config = root/f'{keymap}.toml'
                config.write_text(f'reduced_motion = true\n[modules]\nkeymap = "{keymap}"\n')
                env = dict(base_env, DNA_CONFIG=str(config))
                notes.write_text('hello world\nsecond line\n')
                session = Session([str(binary), '--tui', str(notes)], env, str(project))

                def keys(data, settle=.2):
                    for byte in data:
                        os.write(session.fd, bytes([byte]))
                        session.settle(.02)
                    session.settle(settle, QUIET)

                def expect_status(text, label):
                    deadline = time.monotonic() + 3
                    while text not in status(session):
                        if time.monotonic() > deadline:
                            fail(f'{keymap} {label}: status line lacks {text!r}', session)
                        session.read(.05)

                try:
                    session.wait(lambda: 'hello world' in session.text())
                    # A typo reports itself and runs nothing.
                    keys(b':wrtie\r')
                    expect_status('Not an editor command: wrtie', 'typo')
                    if 'NORMAL' not in status(session) or 'proj' in status(session).split('Not')[0][-5:]:
                        fail(f'{keymap} typo changed the view', session)
                    keys(b':keys-are-not-a-command\r')
                    expect_status('Not an editor command', 'unknown command')
                    # The message lasts until the next key.
                    keys(b'l')
                    if 'Not an editor command' in status(session):
                        fail(f'{keymap} message outlived the next key', session)
                    # Words that start a command's title still run it on Enter:
                    # "Switch theme" asks for its argument in the palette.
                    keys(b':sw th\r')
                    session.wait(lambda: '> theme' in session.text())
                    keys(b'\x1b')
                    # An explicitly picked row runs even when the query is fuzzy.
                    keys(b':wrt')
                    os.write(session.fd, b'\x1b[B')
                    session.settle(.2, QUIET)
                    os.write(session.fd, b'\x1b[A')
                    session.settle(.2, QUIET)
                    keys(b'\r')
                    if 'Not an editor command' in status(session):
                        fail(f'{keymap} picked row did not run', session)
                    keys(b'\x1b')
                    # Searches and writes report in the status line.
                    keys(b'/no-such-text\r')
                    expect_status('Pattern not found: no-such-text', 'search miss')
                    keys(b':w\r')
                    expect_status('"notes.txt" 2L, 24B written', 'write')
                    keys(b':messages\r')
                    session.wait(lambda: 'Pattern not found: no-such-text' in session.text() and 'written' in session.text())
                    keys(b'\x1b')
                    # :help and :keys open generated references; :q closes them.
                    keys(b':help\r', .5)
                    session.wait(lambda: '# DNA help' in session.text())
                    keys(b':q\r')
                    session.wait(lambda: 'hello world' in session.text())
                    keys(b':keys\r', .5)
                    session.wait(lambda: '# Key reference' in session.text() and 'Space f' in session.text())
                    keys(b':q\r')
                    # :q! discards without asking; closing the last buffer
                    # quits the terminal frontend.
                    keys(b'ggiDISCARDED\x1b')
                    try:
                        keys(b':q!\r', .5)
                    except (RuntimeError, OSError):
                        pass
                    else:
                        if 'Unsaved changes' in session.text():
                            fail(f'{keymap} :q! asked to save', session)
                    if 'DISCARDED' in notes.read_text():
                        fail(f'{keymap} :q! wrote the file')
                    print(f'PASS command feedback ({keymap} keymap):', binary.name, flush=True)
                finally:
                    session.close()
            # :qa! exits with unsaved changes and leaves the file alone.
            config = root/'helix.toml'
            env = dict(base_env, DNA_CONFIG=str(config))
            notes.write_text('hello world\nsecond line\n')
            session = Session([str(binary), '--tui', str(notes)], env, str(project))
            try:
                session.wait(lambda: 'hello world' in session.text())
                exited = False
                try:
                    for data in (b'i', b'X', b'\x1b', b':', b'q', b'a', b'!', b'\r'):
                        os.write(session.fd, data)
                        session.settle(.05)
                except (RuntimeError, OSError):
                    exited = True
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not exited:
                    try:
                        session.read(.1)
                    except (RuntimeError, OSError):
                        exited = True
                if not exited:
                    fail(':qa! did not exit', session)
                if notes.read_text() != 'hello world\nsecond line\n':
                    fail(':qa! changed the file')
            finally:
                session.close()
            print('PASS :qa! discards and exits:', binary.name, flush=True)


main()
