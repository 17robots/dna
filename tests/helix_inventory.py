#!/usr/bin/env python3
"""Measure DNA's Helix keymap against Helix's documented defaults.

Each row of tests/helix_reference.txt runs in a fresh terminal-frontend
editor on a small Rust fixture. The harness sends the row's keys through a
real PTY and compares the screen before and after the binding: text, cursor,
selection, mode line, status message and popups all count. A binding whose
screen does not change at all is reported as "no effect".

This is evidence, not proof of identical behavior: a binding that responds
may still differ from Helix in detail. Use it to find gaps and to catch a
binding that stops responding.

Usage: python3 tests/helix_inventory.py [binary] [--markdown docs/helix-compatibility.md]
       [--expect tests/helix_expected.txt]
--expect fails when a row listed there as "responds" stops responding.
"""
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
import private_display  # hides the desktop display; see tests/private_display.py

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from benchmark_editors import Session

FIXTURE = ''.join(f'// leading line {n}\n' for n in range(40)) + '''fn main() {
    let alpha = 1;
    beta(alpha, 22, "text");
}

// a comment
fn beta(x: i32, y: i32, s: &str) -> i32 {
    x + y
}
''' + ''.join(f'// filler line {n}\n' for n in range(80))

NAMED = {
    'Esc': b'\x1b', 'Space': b' ', 'CR': b'\r', 'BS': b'\x7f', 'Del': b'\x1b[3~',
    'Left': b'\x1b[D', 'Right': b'\x1b[C', 'Up': b'\x1b[A', 'Down': b'\x1b[B',
    'Home': b'\x1b[H', 'End': b'\x1b[F', 'PageUp': b'\x1b[5~', 'PageDown': b'\x1b[6~',
}
# Bindings that start a minor mode: the binding is judged from before its prefix.
PREFIX = {'view': 'z', 'goto': 'g', 'match': 'm', 'window': '<C-w>', 'space': '<Space>'}


def encode(token):
    if token.startswith('<') and token.endswith('>') and len(token) > 2:
        inner = token[1:-1]
        if inner.startswith('C-'):
            return bytes([ord(inner[2:].lower()) & 0x1f])
        if inner.startswith('A-'):
            rest = inner[2:]
            rest = {'minus': '-', 'BS': '\x7f'}.get(rest, rest)
            return b'\x1b' + rest.encode()
        return NAMED[inner]
    return token.encode()


def load_reference(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        section, rest = line.split(' | ', 1)
        keys, command = rest.rsplit(' | ', 1)
        rows.append((section.strip(), keys.strip().split(' '), command.strip()))
    return rows


def judge(binary, env, directory, section, tokens):
    source = Path(directory)/'main.rs'
    source.write_text(FIXTURE)
    session = Session([str(binary), '--tui', str(source)], env, str(directory), 30, 100)
    try:
        session.wait(lambda: 'main.rs' in session.text() and 'leading line' in session.text(), timeout=10)
    except (RuntimeError, OSError):
        session.close()
        return 'error: editor did not start'
    try:
        # Start inside the code, on "alpha" (line 43).
        for data in (b'4', b'3', b'G', b'w', b'w'):
            os.write(session.fd, data)
            session.settle(.05)
        session.settle(.2)
        split = len(tokens) - 1
        if section in PREFIX and PREFIX[section] in tokens:
            split = max(index for index, token in enumerate(tokens) if token == PREFIX[section])
        if section == 'unimpaired':
            split = len(tokens) - 2
        for token in tokens[:split]:
            os.write(session.fd, encode(token))
            session.settle(.12)
        session.settle(.25)
        before = session.grid()
        for token in tokens[split:]:
            os.write(session.fd, encode(token))
            session.settle(.12)
        session.settle(.4)
        after = session.grid()
        return 'responds' if before != after else 'no effect'
    except OSError:
        # The binding closed the editor (a quit command): that is a response.
        return 'responds (editor exited)'
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('binary', nargs='?', default=str(ROOT/'build/dna-release'))
    parser.add_argument('--markdown')
    parser.add_argument('--expect')
    parser.add_argument('--only', help='run rows whose section matches')
    arguments = parser.parse_args()
    rows = load_reference(ROOT/'tests/helix_reference.txt')
    if arguments.only:
        rows = [row for row in rows if row[0] == arguments.only]
    results = []
    with tempfile.TemporaryDirectory(prefix='dna-helix-') as temporary:
        root = Path(temporary)
        config = root/'config.toml'
        config.write_text('reduced_motion = true\n[modules]\nkeymap = "helix"\n')
        env = dict(os.environ, DNA_CONFIG=str(config), DNA_DEFAULT_SERVERS='0', DNA_RECOVERY='0',
                   HOME=str(root), XDG_CONFIG_HOME=str(root/'config'), XDG_STATE_HOME=str(root/'state'),
                   TERM='xterm-256color', LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'))
        for name in ('DISPLAY', 'WAYLAND_DISPLAY'):
            env.pop(name, None)
        for section, tokens, command in rows:
            work = root/'work'
            work.mkdir(exist_ok=True)
            outcome = judge(Path(arguments.binary).resolve(), env, work, section, tokens)
            results.append((section, ' '.join(tokens), command, outcome))
            print(f'{outcome:24} {section:12} {" ".join(tokens):24} {command}', flush=True)
    responding = sum(1 for row in results if row[3].startswith('responds'))
    print(f'{responding}/{len(results)} Helix bindings respond')
    if arguments.markdown:
        lines = ['# Helix keymap compatibility', '',
                 'Generated by `python3 tests/helix_inventory.py --markdown docs/helix-compatibility.md`.',
                 'Each Helix default binding runs in a fresh terminal-frontend editor on a Rust',
                 'fixture; "responds" means the screen changed (text, cursor, selection, mode,',
                 'status or a popup). It is evidence of support, not proof of identical behavior.',
                 'Some bindings need a language server or a grammar, which this run does not',
                 'start, so they can respond only with a message.', '',
                 f'{responding} of {len(results)} bindings respond.', '',
                 '| Section | Keys | Helix command | DNA |', '| --- | --- | --- | --- |']
        for section, keys, command, outcome in results:
            shown = keys.replace('|', '\\|').replace('`', '\\`')
            lines.append(f'| {section} | `{shown}` | `{command}` | {outcome} |')
        Path(arguments.markdown).write_text('\n'.join(lines) + '\n')
    if arguments.expect:
        expected = {}
        for line in Path(arguments.expect).read_text().splitlines():
            if line.strip() and not line.startswith('#'):
                expected[line.strip()] = True
        regressions = [f'{section} {keys}' for section, keys, command, outcome in results
                       if f'{section} {keys}' in expected and not outcome.startswith('responds')]
        if regressions:
            raise SystemExit('FAIL bindings stopped responding:\n' + '\n'.join(regressions))


main()
