#!/usr/bin/env python3
"""Every box the terminal frontend draws is closed and intact.

Text written over a border, a button drawn past its dialog, or a scrollbar
drawn as a box line all leave a frame whose edges are broken. This drives the
real TUI through its popups at two terminal sizes and checks each frame on
screen: the top and bottom edges run from corner to corner, and the left and
right edges are unbroken vertical lines (a thickened ┃ is the scrollbar thumb).
"""
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from benchmark_editors import Session

HORIZONTAL = set('─┬┴┼')
LEFT = set('│┃├┼')
RIGHT = set('│┃┤┼')
SIZES = ((32, 120), (24, 80))


def frames(grid):
    """Yield (top, left, bottom, right) for every ┌ that opens a closed box,
    and the problems found while tracing the ones that do not close."""
    problems = []
    found = []
    rows, columns = len(grid), len(grid[0])
    for top in range(rows):
        for left in range(columns):
            if grid[top][left] != '┌':
                continue
            right = left + 1
            while right < columns and grid[top][right] in HORIZONTAL:
                right += 1
            if right >= columns or grid[top][right] != '┐':
                problems.append(f'top edge from row {top} column {left} does not reach a ┐')
                continue
            bottom = top + 1
            while bottom < rows and grid[bottom][left] in LEFT:
                bottom += 1
            if bottom >= rows or grid[bottom][left] != '└':
                problems.append(f'left edge from row {top} column {left} is broken at row {bottom}: {grid[bottom][left]!r}' if bottom < rows else f'box at row {top} column {left} has no bottom')
                continue
            for column in range(left + 1, right):
                if grid[bottom][column] not in HORIZONTAL:
                    problems.append(f'bottom edge of box at row {top} column {left} is broken at column {column}: {grid[bottom][column]!r}')
                    break
            else:
                if grid[bottom][right] != '┘':
                    problems.append(f'box at row {top} column {left} has no ┘ at row {bottom} column {right}')
            for row in range(top + 1, bottom):
                if grid[row][right] not in RIGHT:
                    problems.append(f'right edge of box at row {top} column {left} is broken at row {row}: {grid[row][right]!r}')
                    break
            found.append((top, left, bottom, right))
    return found, problems


def check(session, label):
    grid = session.grid()
    found, problems = frames(grid)
    if problems:
        raise SystemExit(f'FAIL {label} at {session.rows}x{session.columns}:\n' + '\n'.join(problems) + '\n' + '\n'.join(grid))
    return len(found)


def main():
    binaries = [ROOT/'build'/name for name in (sys.argv[1:] or ('dna-release',))]
    for binary in binaries:
        if not binary.is_file():
            raise SystemExit(f'Missing editor binary: {binary}; run just build release first')
    with tempfile.TemporaryDirectory(prefix='dna-frames-') as temporary:
        root = Path(temporary)
        project = root/'a-project-directory-with-a-long-name-for-wrapping-checks'/'files'
        project.mkdir(parents=True)
        (project/'notes.txt').write_text('hello world\nsecond line\n')
        (project/'other.txt').write_text(''.join(f'line {n}\n' for n in range(400)))
        config = root/'config.toml'
        config.write_text('reduced_motion = true\n')
        env = dict(os.environ, DNA_CONFIG=str(config), DNA_DEFAULT_SERVERS='0', DNA_RECOVERY='0',
                   HOME=str(root), XDG_CONFIG_HOME=str(root/'config'), XDG_STATE_HOME=str(root/'state'),
                   TERM='xterm-256color', LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'))
        for name in ('DISPLAY', 'WAYLAND_DISPLAY'):
            env.pop(name, None)
        for binary in binaries:
            for rows, columns in SIZES:
                session = Session([str(binary), '--tui', str(project)], env, str(project), rows, columns)

                def keys(data, settle=.25):
                    for byte in data:
                        os.write(session.fd, bytes([byte]))
                        session.settle(.02)
                    session.settle(settle)

                try:
                    session.wait(lambda: 'notes.txt' in session.text())
                    session.settle(.3)
                    checked = check(session, 'startup explorer')
                    keys(b'\x1b')
                    keys(b':e other.txt\r')
                    session.wait(lambda: 'line 399' in session.text() or 'line 1' in session.text())
                    keys(b':')
                    checked += check(session, 'empty palette')
                    # The palette lists more commands than fit, so it shows a
                    # thumb, drawn on its border rather than over the hints.
                    grid = session.grid()
                    found, _ = frames(grid)
                    if not any(grid[row][right] == '┃' for top, left, bottom, right in found for row in range(top + 1, bottom)):
                        raise SystemExit('FAIL palette scrollbar is not on its border:\n' + '\n'.join(grid))
                    if any('│' in line[left + 1:right - 1] for top, left, bottom, right in found for line in grid[top + 1:bottom]):
                        raise SystemExit('FAIL a vertical line is drawn inside a box (stray scrollbar?):\n' + '\n'.join(grid))
                    keys(b'theme')
                    checked += check(session, 'typed palette')
                    keys(b'\x1b')
                    keys(b':theme\r')
                    checked += check(session, 'current theme dialog')
                    keys(b'\x1b')
                    keys(b':themes\r')
                    checked += check(session, 'theme picker')
                    keys(b'\x1b')
                    keys(b' ')
                    checked += check(session, 'space menu')
                    keys(b'\x1b')
                    keys(b' f')
                    checked += check(session, 'file picker')
                    keys(b'\x1b')
                    keys(b':e notes.txt\r')
                    keys(b'iX\x1b')
                    keys(b':q\r')
                    session.wait(lambda: 'Unsaved changes' in session.text())
                    checked += check(session, 'unsaved changes dialog')
                    keys(b'\x1b')
                    keys(b'/missing-pattern\r')
                    keys(b':messages\r')
                    checked += check(session, 'messages dialog')
                    keys(b'\x1b')
                    if checked < 8:
                        raise SystemExit(f'FAIL only {checked} frames found at {rows}x{columns}; the walk did not open its popups')
                finally:
                    session.close()
                print(f'PASS TUI frames intact at {rows}x{columns}: {binary.name}', flush=True)


main()
