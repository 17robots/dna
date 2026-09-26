#!/usr/bin/env python3
"""Drive `dna --tui` through a pty and check the screen libvterm reconstructs."""
import ctypes
import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import struct
import sys
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / 'build' / ('dna-' + (sys.argv[1] if len(sys.argv) > 1 else 'release'))
ROWS, COLUMNS = 24, 80
# The terminal profile (just build-profile terminal) has no GUI to switch to.
TERMINAL_ONLY = BINARY.name == 'dna-terminal'

vterm = ctypes.CDLL('libvterm.so.0')


class Rect(ctypes.Structure):
    _fields_ = [('start_row', ctypes.c_int), ('end_row', ctypes.c_int), ('start_col', ctypes.c_int), ('end_col', ctypes.c_int)]


vterm.vterm_new.restype = ctypes.c_void_p
vterm.vterm_new.argtypes = [ctypes.c_int, ctypes.c_int]
vterm.vterm_free.argtypes = [ctypes.c_void_p]
vterm.vterm_set_utf8.argtypes = [ctypes.c_void_p, ctypes.c_int]
vterm.vterm_input_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
vterm.vterm_obtain_screen.restype = ctypes.c_void_p
vterm.vterm_obtain_screen.argtypes = [ctypes.c_void_p]
vterm.vterm_screen_reset.argtypes = [ctypes.c_void_p, ctypes.c_int]
vterm.vterm_screen_enable_altscreen.argtypes = [ctypes.c_void_p, ctypes.c_int]
vterm.vterm_screen_get_text.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, Rect]
vterm.vterm_screen_get_text.restype = ctypes.c_size_t
vterm.vterm_set_size.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]


class Session:
    def __init__(self, arguments, environment, program=None):
        program = str(program or BINARY)
        self.rows, self.columns = ROWS, COLUMNS
        self.terminal = vterm.vterm_new(ROWS, COLUMNS)
        vterm.vterm_set_utf8(self.terminal, 1)
        self.screen = vterm.vterm_obtain_screen(self.terminal)
        vterm.vterm_screen_enable_altscreen(self.screen, 1)
        vterm.vterm_screen_reset(self.screen, 1)
        self.raw = bytearray()
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            # Keep stderr off the screen being checked; failures print it.
            if 'DNA_ERRLOG' in environment:
                os.dup2(os.open(environment['DNA_ERRLOG'], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 2)
            os.execve(program, [program, *arguments], environment)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack('HHHH', ROWS, COLUMNS, 0, 0))
        self.open = True

    def pump(self, seconds):
        deadline = time.time() + seconds
        while self.open and time.time() < deadline:
            ready, _, _ = select.select([self.fd], [], [], 0.05)
            if not ready:
                continue
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                data = b''
            if not data:
                self.open = False
                break
            self.raw += data
            vterm.vterm_input_write(self.terminal, data, len(data))

    def resize(self, rows, columns, settle=0.8):
        self.rows, self.columns = rows, columns
        vterm.vterm_set_size(self.terminal, rows, columns)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, columns, 0, 0))
        self.pump(settle)

    def text(self):
        rows = []
        for row in range(self.rows):
            buffer = ctypes.create_string_buffer(self.columns * 4 + 1)
            length = vterm.vterm_screen_get_text(self.screen, buffer, self.columns * 4, Rect(row, row + 1, 0, self.columns))
            rows.append(buffer.raw[:length].decode('utf-8', 'replace').rstrip())
        return rows

    def wait_for(self, needle, seconds=5.0):
        deadline = time.time() + seconds
        while time.time() < deadline:
            self.pump(0.1)
            if any(needle in row for row in self.text()):
                return self.text()
        fail(f'screen never showed {needle!r}', self.text())

    def send(self, data, settle=0.3):
        os.write(self.fd, data)
        self.pump(settle)

    def close(self):
        if self.open:
            os.kill(self.pid, signal.SIGKILL)
        os.waitpid(self.pid, 0)
        vterm.vterm_free(self.terminal)


def fail(message, rows):
    print('FAIL tui:', message, file=sys.stderr)
    print('\n'.join(rows), file=sys.stderr)
    sys.exit(1)


def check_handoff(root, sample, environment):
    """With a display the editor quits cleanly and re-executes as --gui,
    consuming the handoff session (SDL's dummy driver stands in for it)."""
    session = Session(['--tui', str(sample)], dict(environment, WAYLAND_DISPLAY='dna-test', SDL_VIDEODRIVER='dummy'))
    try:
        session.wait_for('first line')
        session.send(b'i')
        session.send(b'moved ')
        session.send(b'\x1b[27u')
        session.send(b':', 0.4)
        session.send(b'theme nord\r', 0.5)
        session.send(b':', 0.4)
        session.send(b'keymap vim\r', 0.5)
        session.send(b'\x1b[27u', 0.3)
        session.send(b':', 0.4)
        session.send(b'place picker top-right 0.5\r', 0.5)
        session.send(b'\x1b[27u', 0.3)
        session.send(b':', 0.4)
        session.send(b'set relative_numbers true\r', 0.5)
        session.send(b':', 0.4)
        session.send(b'frontend gui\r', 0.5)
        deadline = time.time() + 5
        command_line = b''
        while time.time() < deadline and b'--gui' not in command_line:
            session.pump(0.1)
            try:
                command_line = Path(f'/proc/{session.pid}/cmdline').read_bytes()
            except OSError:
                break
        if command_line.split(b'\0')[1:2] != [b'--gui']:
            fail(f'handoff did not re-execute as --gui: {command_line!r}', session.text())
        # Session values travel with the session.
        handed = Path(f'/proc/{session.pid}/environ').read_bytes().split(b'\0')
        for wanted in (b'DNA_HANDOFF_SET=theme = "nord"\nrelative_numbers = true\n',
                       b'DNA_HANDOFF_MODULES=keymap = "vim"\n',
                       b'DNA_HANDOFF_PLACES=[place.picker]\nmode = "default"\nanchor = "top-right"\nwidth = 0.5\n'):
            if wanted not in handed:
                fail(f'handoff did not carry {wanted!r}: {[v for v in handed if v.startswith(b"DNA_HANDOFF")]!r}', session.text())
        if b'\x1b[?1049l' not in bytes(session.raw):
            fail('terminal not restored before the handoff', session.text())
        deadline = time.time() + 5
        while time.time() < deadline and list((root / 'state' / 'dna').glob('handoff-*')):
            time.sleep(0.1)
        if list((root / 'state' / 'dna').glob('handoff-*')):
            fail('handoff session was not consumed', session.text())
    finally:
        session.close()



def check_failed_handoff(root, environment):
    """A failed restore keeps the only copy of unsaved text for a later retry."""
    project = root / 'handoff-project'
    project.mkdir()
    sample = project / 'sample.txt'
    sample.write_text('original handoff text\n')
    handoff = root / 'retry.session'
    previous = Path.cwd()
    os.chdir(project)
    sender = Session(['--tui', str(sample)], environment)
    try:
        sender.wait_for('original handoff text')
        sender.send(b'i')
        sender.send(b'UNSAVED ')
        sender.wait_for('UNSAVED original handoff text')
        sender.send(b'\x1b[27u')
        sender.send(b':')
        sender.send(f'session-save {handoff}\r'.encode(), 0.6)
        if not handoff.exists() or b'UNSAVED' not in handoff.read_bytes():
            fail('handoff fixture must contain unsaved text', sender.text())
        snapshot = handoff.read_bytes()
    finally:
        sender.close()
        os.chdir(previous)
    moved = root / 'moved-handoff-project'
    project.rename(moved)
    receiver = Session(['--tui'], dict(environment, DNA_HANDOFF=str(handoff)))
    try:
        receiver.wait_for('Session project directory is unavailable')
        if not handoff.exists() or handoff.read_bytes() != snapshot:
            fail('failed restore must retain handoff unchanged', receiver.text())
        if not any('Handoff preserved' in row for row in receiver.text()):
            fail('failed restore must explain how to retry', receiver.text())
    finally:
        receiver.close()
        moved.rename(project)
    receiver = Session(['--tui'], dict(environment, DNA_HANDOFF=str(handoff)))
    try:
        receiver.wait_for('UNSAVED original handoff text')
        if handoff.exists():
            fail('successful retry must consume handoff', receiver.text())
    finally:
        receiver.close()

def check_suspend(root, sample, environment):
    """:suspend stops DNA as a shell job and `fg` resumes it in raw mode."""
    shell_environment = dict(environment, PS1='SHELL$ ')
    session = Session(['--norc', '--noprofile', '-i'], shell_environment, program='/bin/bash')
    try:
        session.pump(0.8)
        session.send(f'{BINARY} --tui {sample}\r'.encode(), 1.0)
        session.wait_for('first line')
        session.send(b':', 0.4)
        session.send(b'suspend\r', 0.8)
        rows = session.wait_for('Stopped')
        session.send(b'fg\r', 1.0)
        session.wait_for('first line')
        session.send(b'i')
        session.send(b'back ', 0.4)
        session.wait_for('back first line')
    finally:
        session.close()


def report_text(session):
    """Every line of a scrolling report popup: arrows scroll long hovers."""
    seen = list(session.text())
    for _ in range(8):
        session.send(b'\x1b[B', 0.15)
        seen += session.text()
    return '\n'.join(seen)


def check_file_config(root, environment):
    """Per-file settings: .editorconfig and a [project."PATH"] theme for the
    project, and another repository's dna.toml for a file opened from it."""
    project = root / 'proj'
    other = root / 'other'
    (project / 'pkg').mkdir(parents=True)
    other.mkdir()
    (project / '.editorconfig').write_text('root = true\n[*]\ninsert_final_newline = true\n[*.py]\nindent_size = 2\n')
    (project / 'pkg' / 'a.py').write_text('x = 1\n')
    (other / 'dna.toml').write_text('indent_width = 8\ninsert_tabs = true\ntheme = "dracula"\n')
    (other / 'b.txt').write_text('other file\n')
    config = root / 'config' / 'dna' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(f'[project."{project}"]\ntheme = "nord"\n')
    previous = Path.cwd()
    os.chdir(project)
    session = Session(['--tui', str(project / 'pkg' / 'a.py')], dict(environment, COLORTERM='truecolor'))
    try:
        session.wait_for('x = 1')
        session.pump(0.5)
        if b'48;2;46;52;64' not in bytes(session.raw):
            fail('[project] section theme not applied', session.text())
        session.send(b':', 0.4)
        session.send(b'config-sources\r', 0.8)
        text = report_text(session)
        for wanted in ('sections matching: 1', 'indent_width = 2 (.editorconfig)', 'final_newline = true (.editorconfig)', '.editorconfig files: 1'):
            if wanted not in text:
                fail(f'config-sources for a.py must show {wanted!r}', session.text())
        session.send(b'\x1b[27u', 0.3)
        # > indents by the .editorconfig width.
        before = next(row.index('x = 1') for row in session.text() if 'x = 1' in row)
        session.send(b'>', 0.4)
        rows = session.wait_for('x = 1')
        if not any(row.index('x = 1') == before + 2 for row in rows if 'x = 1' in row):
            fail('> must indent a.py by 2 spaces', rows)
        session.send(b'u', 0.4)
        session.send(b':', 0.4)
        session.send(f'open {other / "b.txt"}\r'.encode(), 0.8)
        session.wait_for('other file')
        session.send(b':', 0.4)
        session.send(b'config-sources\r', 0.8)
        text = report_text(session)
        for wanted in ('indent_width = 8 (dna.toml)', 'insert_tabs = true (dna.toml)', str(other / 'dna.toml'), 'final_newline = false (global)'):
            if wanted not in text:
                fail(f'config-sources for b.txt must show {wanted!r}', session.text())
        session.send(b'\x1b[27u', 0.3)
        # Its theme stays the project's: dna.toml never sets personal keys.
        mark = len(session.raw)
        session.send(b':', 0.4)
        session.send(b'set line_numbers false\r', 0.8)
        if b'48;2;40;42;54' in bytes(session.raw[mark:]):
            fail('a dna.toml theme must not apply', session.text())
    finally:
        session.close()
        os.chdir(previous)
        config.unlink()


with tempfile.TemporaryDirectory(prefix='dna-tui-') as directory:
    root = Path(directory)
    # The project directory is the working directory; keep it to the fixture.
    os.chdir(root)
    (root / 'config').mkdir()
    sample = root / 'sample.txt'
    sample.write_text('first line\nsecond line\n')
    environment = {key: value for key, value in os.environ.items() if not key.startswith('DNA_')}
    environment.pop('COLORTERM', None)
    environment.update(TERM='xterm-256color', XDG_CONFIG_HOME=str(root / 'config'), XDG_STATE_HOME=str(root / 'state'), DNA_DEFAULT_SERVERS='0', SHELL='/bin/sh', ENV='', PS1='$ ')
    environment.pop('DISPLAY', None)
    environment.pop('WAYLAND_DISPLAY', None)
    with tempfile.TemporaryDirectory(prefix='dna-handoff-') as handoff_directory:
        check_failed_handoff(Path(handoff_directory), dict(environment, DNA_RECOVERY='0'))
    session = Session(['--tui', str(sample)], environment)
    try:
        rows = session.wait_for('first line')
        if not any('NORMAL' in row and 'sample.txt' in row for row in rows):
            fail('status line', rows)
        if not session.raw.startswith(b'\x1b[?1049h') and b'\x1b[?1049h' not in session.raw[:64]:
            fail('alternate screen not entered first', rows)
        # Insert mode text lands in the document row, not on a stray line.
        session.send(b'i')
        session.send(b'typed ')
        rows = session.wait_for('typed first line')
        session.send(b'\x1b[27u')
        session.send(b'u')
        session.wait_for(' first line')
        # Shift held during a click (SGR button bit 4) extends the selection.
        session.send(b'\x1b[<0;9;1M\x1b[<0;9;1m')
        session.send(b'\x1b[<4;14;2M\x1b[<4;14;2m', 0.4)
        session.wait_for('SELECT')
        session.send(b'\x1b[27u', 0.3)
        # The palette is framed in box-drawing characters, with its prompt
        # and last entry inside the frame rather than on the border rows.
        session.send(b':', 0.6)
        rows = session.text()
        top = next((index for index, row in enumerate(rows) if '┌' in row), None)
        if top is None or '└' not in ''.join(rows[top + 1:]):
            fail('command palette frame', rows)
        if not any('>' in row for row in rows[top + 1:top + 3]):
            fail('palette prompt must sit inside the frame', rows)
        session.send(b'vsplit\r', 0.6)
        rows = session.text()
        if '─' in rows[0]:
            fail('pane border drawn over text', rows)
        if not all('│' in row for row in rows[:-1]):
            fail('vertical split divider', rows)
        # Terminal pane round trip through a real shell.
        session.send(b' ')
        session.send(b't', 1.5)
        session.send(b'printf "\\033[1mtui-%s\\033[0m\\n" ok\r')
        session.wait_for('tui-ok')
        session.send(b'\x1b[200~echo pasted-%s\x1b[201~', 0.4)
        session.send(b'\r')
        session.wait_for('pasted-%s')
        # The shell's bold reaches the terminal as bold.
        if b'\x1b[1m' not in bytes(session.raw):
            fail('bold from a terminal pane', session.text())
        session.send(b'exit\r', 1.0)
        # Terminal teardown changes the active pane asynchronously. Wait for
        # the file-only frame before opening its command palette.
        session.wait_for('1 buffer')
        session.send(b':', 0.4)
        session.wait_for('┌')
        session.send(b'quit-all\r', 1.0)
        session.pump(1.0)
        if session.open:
            fail('quit-all left the editor running', session.text())
    finally:
        raw = bytes(session.raw)
        session.close()
    # The terminal is handed back: main screen, cursor shown, kitty keys popped.
    if not raw.endswith(b'\x1b[?1049l') or b'\x1b[<u' not in raw[-200:] or b'\x1b[?25h' not in raw[-200:]:
        print('FAIL tui: terminal not restored on exit', file=sys.stderr)
        sys.exit(1)

    # :frontend. Without a display the switch is refused and nothing is lost;
    # the session saved here later stands in for a handoff from the GUI.
    saved = root / 'saved.session'
    session = Session(['--tui', str(sample)], environment)
    try:
        session.wait_for('first line')
        session.send(b'i')
        session.send(b'unsaved ')
        session.send(b'\x1b[27u')
        session.send(b':', 0.4)
        session.send(b'frontend gui\r', 0.6)
        session.wait_for('not in this build' if TERMINAL_ONLY else 'No display')
        if not session.open:
            fail('refused switch must keep running', session.text())
        session.send(b'\x1b[27u', 0.3)
        session.send(b':', 0.4)
        session.send(b'session-save ' + str(saved).encode() + b'\r', 0.6)
        deadline = time.time() + 5
        while time.time() < deadline and not saved.exists():
            session.pump(0.1)
        if not saved.exists():
            fail('session-save', session.text())
    finally:
        session.close()
    if not TERMINAL_ONLY:
        check_handoff(root, sample, environment)
    if Path('/bin/bash').exists():
        check_suspend(root, sample, environment)
    # The receiving side restores unsaved text from DNA_HANDOFF and deletes it.
    session = Session(['--tui'], dict(environment, DNA_HANDOFF=str(saved), COLORTERM='truecolor',
                                      DNA_HANDOFF_SET='theme = "nord"\n', DNA_HANDOFF_MODULES='keymap = "vim"\n'))
    try:
        rows = session.wait_for('unsaved first line')
        if not any('[+]' in row for row in rows):
            fail('restored text must stay unsaved', rows)
        # It also applies the theme handed over: nord's #2E3440 background.
        session.pump(0.5)
        if b'48;2;46;52;64' not in bytes(session.raw):
            fail('handed-over theme not applied', rows)
        # Vim keys from the handed-over [modules]: x deletes a character
        # (Helix would select the line).
        session.send(b'x', 0.4)
        session.wait_for('unsavedfirst line')
        session.send(b'u', 0.4)
        session.wait_for('unsaved first line')
        # A later :set reloads the config and keeps the session's theme.
        mark = len(session.raw)
        session.send(b':', 0.4)
        session.send(b'set line_numbers false\r', 0.8)
        after = bytes(session.raw[mark:])
        if b'48;2;24;24;24' in after or b'48;2;46;52;64' not in after:
            fail(':set reverted the session theme', session.text())
        if saved.exists():
            fail('handoff session file left behind', rows)
        # A burst longer than the event queue arrives whole.
        session.send(b'i')
        session.send(b'z' * 100, 0.8)
        session.wait_for('1:108')
    finally:
        session.close()
    # Pastes from the outer terminal arrive whole and as text: no auto-pairs
    # in insert mode, no commands from a big paste in normal mode.
    pasted = root / 'pasted.txt'
    pasted.write_text('end\n')
    session = Session(['--tui', str(pasted)], environment)
    try:
        session.wait_for('end')
        session.send(b'i')
        session.send(b'\x1b[200~call(one, [two])\n  indented\n\x1b[201~', 0.6)
        session.wait_for('call(one, [two])')
        rows = session.text()
        if not any(row.rstrip().endswith('call(one, [two])') for row in rows) or not any(row.rstrip().endswith('  indented') for row in rows):
            fail('insert-mode paste must arrive unchanged', rows)
        session.send(b'\x1b[27u', 0.3)
        big = b'xyz:q\n' * 1000
        session.send(b'\x1b[200~' + big + b'\x1b[201~', 1.5)
        rows = session.wait_for('xyz:q')
        if not session.open or any('┌' in row for row in rows):
            fail('a normal-mode paste must not run commands', rows)
        session.send(b':', 0.4)
        session.send(b'write\r', 0.8)
        deadline = time.time() + 5
        while time.time() < deadline and pasted.read_text().count('xyz:q') < 1000:
            session.pump(0.1)
        if pasted.read_text().count('xyz:q') != 1000 or 'call(one, [two])\n  indented\n' not in pasted.read_text():
            fail(f'pasted text on disk: {pasted.read_text()[:200]!r}', session.text())
        # A paste whose end marker never arrives ends after a quiet second,
        # and keys work again.
        session.send(b'\x1b[27u', 0.3)
        session.send(b'i')
        session.send(b'\x1b[200~dangling', 1.8)
        session.wait_for('dangling')
        session.send(b'\x1b[27u', 0.3)
        session.send(b':', 0.6)
        if not any('┌' in row for row in session.text()):
            fail('keys must work after an unterminated paste', session.text())
    finally:
        session.close()
    # Resizing the terminal keeps the caret's line on screen.
    long_file = root / 'long.txt'
    long_file.write_text(''.join(f'line {number}\n' for number in range(1, 201)) + 'last line')
    session = Session(['--tui', str(long_file)], environment)
    try:
        session.wait_for('line 1')
        session.send(b'g')
        session.send(b'e', 0.6)
        session.wait_for('last line')
        for rows, columns in ((8, 50), (40, 120), (12, 30), (24, 80)):
            session.resize(rows, columns)
            if not any('last line' in row for row in session.text()):
                fail(f'caret line lost after resizing to {columns}x{rows}', session.text())
    finally:
        session.close()
    # Color depth: 24-bit SGR when the terminal advertises it, else xterm-256.
    for colorterm, wanted, unwanted in (('truecolor', b'\x1b[38;2;', b'\x1b[38;5;'), ('', b'\x1b[38;5;', b'\x1b[38;2;')):
        depth_environment = dict(environment, COLORTERM=colorterm)
        session = Session(['--tui', str(sample)], depth_environment)
        try:
            session.wait_for('first line')
            raw = bytes(session.raw)
            if wanted not in raw or unwanted in raw:
                fail(f'COLORTERM={colorterm!r} must draw with {wanted!r}', session.text())
        finally:
            session.close()
    # Styles: comments in italics, a diagnostic as a colored undercurl.
    (root / 'config' / 'dna').mkdir(parents=True, exist_ok=True)
    (root / 'config' / 'dna' / 'config.toml').write_text(
        f'[languages.dyn]\nserver = "python3 {ROOT / "tests/fake_lsp.py"}"\nauto_start = true\n')
    styled = root / 'styled.dyn'
    styled.write_text('fn main() {\n  // a comment\n}\n')
    for undercurl, wanted in (('1', b'\x1b[4:3m'), ('0', b'\x1b[4m')):
        session = Session(['--tui', str(styled)], dict(environment, DNA_UNDERCURL=undercurl))
        try:
            session.wait_for('a comment')
            deadline = time.time() + 8
            while time.time() < deadline and wanted not in bytes(session.raw):
                session.pump(0.2)
            raw = bytes(session.raw)
            if wanted not in raw:
                fail(f'DNA_UNDERCURL={undercurl}: diagnostic underline {wanted!r} missing', session.text())
            if undercurl == '1' and b'\x1b[58:' not in raw:
                fail('undercurl must carry the diagnostic color', session.text())
            if undercurl == '0' and b'\x1b[4:3m' in raw:
                fail('DNA_UNDERCURL=0 must not curl', session.text())
            if b'\x1b[3m' not in raw:
                fail('comments must be italic', session.text())
        finally:
            session.close()
    (root / 'config' / 'dna' / 'config.toml').unlink()
    # Module variants: the tree explorer docks on the left and keeps the
    # editor usable beside it; the dropdown picker hangs from the top edge.
    (root / 'config' / 'dna').mkdir(parents=True, exist_ok=True)
    (root / 'config' / 'dna' / 'config.toml').write_text('[modules]\nexplorer = "tree"\npicker = "dropdown"\n')
    (root / 'pkg').mkdir()
    (root / 'pkg' / 'inner.txt').write_text('inner\n')
    session = Session(['--tui', str(sample)], environment)
    try:
        session.wait_for('first line')
        session.send(b' ')
        session.send(b'e', 0.6)
        rows = session.wait_for('pkg/')
        if not rows[0].startswith('┌') or 'first line' not in ''.join(rows):
            fail('tree must dock left beside the document', rows)
        tree_rows = [row for row in rows if 'pkg/' in row]
        if '▸' not in tree_rows[0]:
            fail('collapsed folder marker', rows)
        # Files created and removed outside DNA show up without a reload.
        (root / 'fresh.txt').write_text('new\n')
        session.wait_for('fresh.txt')
        (root / 'fresh.txt').unlink()
        deadline = time.time() + 5
        while time.time() < deadline and any('fresh.txt' in row for row in session.text()):
            session.pump(0.1)
        if any('fresh.txt' in row for row in session.text()):
            fail('a deleted file must leave the tree', session.text())
        # Dragging the dock's edge (SGR mouse: press, drag, release) widens it.
        edge = rows[0].index('┐') + 1
        session.send(f'\x1b[<0;{edge};6M'.encode())
        session.send(b'\x1b[<32;40;6M')
        session.send(b'\x1b[<0;40;6m', 0.5)
        rows = session.text()
        if rows[0].index('┐') + 1 < 36:
            fail('dragging the tree edge must resize the dock', rows)
        # Folders first, sorted: config/, pkg/, state/. Open pkg/, then its file.
        session.send(b'g')
        session.send(b'j')
        session.send(b'l', 0.4)
        session.wait_for('inner.txt')
        session.send(b'j')
        session.send(b'\r', 0.6)
        rows = session.wait_for('inner.txt  [text]')
        session.send(b'i')
        session.send(b'Q', 0.4)
        session.wait_for('Qinner')
        session.send(b'\x1b[27u')
        session.send(b' ')
        session.send(b'f', 0.6)
        rows = session.text()
        # Row 0 holds both the tree's corner and the picker's.
        if rows[0].count('┌') < 2 or '_' not in rows[1]:
            fail('dropdown picker must hang from the top edge', rows)
    finally:
        session.close()
    check_file_config(root, environment)
print('PASS TUI frontend: per-file config, document, status, insert, palette frame, splits, terminal pane, :frontend handoff, suspend, tree explorer, dock drag, dropdown picker, italics, undercurl, pastes, resize')
