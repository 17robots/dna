#!/usr/bin/env python3
"""Real PTY checks for keymap features: :sort, Vim Replace mode, file marks,
gq, Helix insert-mode editing keys, Helix `.` and the yank message."""
import os
from pathlib import Path
import sys
import tempfile
import time
import private_display  # hides the desktop display; see tests/private_display.py

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from benchmark_editors import QUIET, Session


def run(binary, keymap, root, name, text, steps, extra=()):
    """Open name (holding text) plus any extra files, send steps, then save
    and quit with :wa and :qa!. Returns the file's final text and the last
    status line seen before saving."""
    target = root/name
    target.write_text(text)
    for other, content in extra:
        (root/other).write_text(content)
    config = root/f'{keymap}.toml'
    config.write_text(f'reduced_motion = true\n[modules]\nkeymap = "{keymap}"\n')
    env = dict(os.environ, DNA_CONFIG=str(config), DNA_DEFAULT_SERVERS='0', DNA_RECOVERY='0',
               HOME=str(root), XDG_CONFIG_HOME=str(root/'config'), XDG_STATE_HOME=str(root/'state'),
               TERM='xterm-256color', LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'))
    for variable in ('DISPLAY', 'WAYLAND_DISPLAY'):
        env.pop(variable, None)
    session = Session([str(binary), '--tui', str(target)], env, str(root))
    status = ''
    try:
        session.wait(lambda: name in session.text())
        for step in steps:
            os.write(session.fd, step)
            session.settle(.25, QUIET)
        status = session.grid()[-1]
        for step in (b'\x1b', b':wa\r'):
            os.write(session.fd, step)
            session.settle(.3, QUIET)
        # The write report means the save finished. A run with nothing to
        # save shows none and waits the full two seconds.
        deadline = time.monotonic() + 2
        while 'B written' not in session.text() and time.monotonic() < deadline:
            session.read(.05)
    finally:
        session.close()
    return target.read_text(), status


def check(label, actual, expected):
    if actual != expected:
        raise SystemExit(f'FAIL {label}:\nexpected {expected!r}\nactual   {actual!r}')


def main():
    binaries = [ROOT/'build'/name for name in (sys.argv[1:] or ('dna-release',))]
    with tempfile.TemporaryDirectory(prefix='dna-keymap-') as directory:
        root = Path(directory)
        for binary in binaries:
            text = 'pear 10\napple 2\nPear 10\nbanana -3\napple 2\n'
            for command, expected in (
                (b':sort\r', 'Pear 10\napple 2\napple 2\nbanana -3\npear 10\n'),
                (b':sort!\r', 'pear 10\nbanana -3\napple 2\napple 2\nPear 10\n'),
                (b':sort u\r', 'Pear 10\napple 2\nbanana -3\npear 10\n'),
                (b':sort n\r', 'banana -3\napple 2\napple 2\npear 10\nPear 10\n'),
                (b':sort i u\r', 'apple 2\nbanana -3\npear 10\n'),
                (b':2,4sort\r', 'pear 10\nPear 10\napple 2\nbanana -3\napple 2\n'),
            ):
                for keymap in ('vim', 'helix'):
                    result, _ = run(binary, keymap, root, 'sort.txt', text, [command])
                    check(f'{keymap} {command!r}', result, expected)
            # Vim Replace mode: overwrite, Backspace restores, append past the end.
            result, _ = run(binary, 'vim', root, 'r.txt', 'abcdef\nxyz\n',
                            [b'l', b'R', b'X', b'Y', b'Z', b'\x7f', b'\x1b', b'j', b'R', b'p', b'q', b'r', b's', b'\x1b'])
            check('Vim Replace mode', result, 'aXYdef\nxypqrs\n')
            # gq: rewrap to 79 columns, keeping comment leaders; code is untouched.
            words = ' '.join(f'word{n}' for n in range(30))
            source = f'fn x() {{\n    // {words}\n    // tail words here\n\n    let a = 1;\n}}\n'
            result, _ = run(binary, 'vim', root, 'q.rs', source, [b'j', b'g', b'q', b'a', b'p'])
            lines = result.split('\n')
            check('gq keeps the code line', lines[0], 'fn x() {')
            if not all(line.startswith('    // ') and len(line) <= 79 for line in lines[1:5]):
                raise SystemExit('FAIL gq wrapping:\n' + result)
            check('gq keeps the words', ' '.join(' '.join(line[7:] for line in lines[1:5]).split()), words + ' tail words here')
            check('gq keeps what follows', lines[5:], ['', '    let a = 1;', '}', ''])
            # File marks jump between files; an unset mark reports E20.
            result, status = run(binary, 'vim', root, 'm1.txt', 'one\ntwo\nthree line\n',
                                 [b'j', b'j', b'w', b'm', b'A', b':e m2.txt\r', b"'", b'A', b'i', b'!', b'\x1b', b'`', b'b'],
                                 extra=(('m2.txt', 'alpha\nbeta\n'),))
            check('file mark jump', result, 'one\ntwo\n!three line\n')
            if 'E20: Mark not set' not in status:
                raise SystemExit('FAIL unset mark message: ' + status)
            # Helix insert-mode keys.
            for keys, expected in (
                (b'A\x17', 'foo bar \n'),
                (b'A\x1b\x7f', 'foo bar \n'),
                (b'I\x1bd', ' bar baz\n'),
                (b'wwi\x15', 'bar baz\n'),
                (b'i\x04', 'oo bar baz\n'),
            ):
                result, _ = run(binary, 'helix', root, 'k.txt', 'foo bar baz\n', [keys])
                check(f'Helix insert key {keys!r}', result, expected)
            # Helix `.` repeats the last insert, Enter included.
            result, _ = run(binary, 'helix', root, 'd.txt', 'one\ntwo\nthree\n',
                            [b'A', b'X', b'Y', b'\r', b'!', b'\x1b', b'j', b'.'])
            check('Helix repeat insert', result, 'oneXY\n!\ntwoXY\n!\nthree\n')
            # Yanking reports what it copied.
            _, status = run(binary, 'helix', root, 'y.txt', 'one two\n', [b'w', b'y'])
            if 'Yanked 1 selection' not in status:
                raise SystemExit('FAIL yank message: ' + status)
            print('PASS keymap features (:sort, Replace, file marks, gq, Helix insert keys, ., yank):', binary.name, flush=True)


main()
