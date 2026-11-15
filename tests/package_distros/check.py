"""Runs inside a clean distribution container: unpack the package, print the
version, then open a file in the terminal frontend, type, save and quit."""
import os
import pty
import select
import subprocess
import tarfile
import time

tarfile.open('/t/dna-preview-linux-x86_64.tar.gz').extractall('/opt', filter='data')
dna = '/opt/dna-preview-linux-x86_64/dna'
version = subprocess.run([dna, '--version'], capture_output=True, text=True)
assert version.returncode == 0 and version.stdout.startswith('dna '), version
os.makedirs('/w', exist_ok=True)
with open('/w/a.txt', 'w') as handle:
    handle.write('hello from container\n')
pid, fd = pty.fork()
if pid == 0:
    os.environ.update(TERM='xterm-256color', HOME='/w', DNA_RECOVERY='0')
    os.environ.pop('WAYLAND_DISPLAY', None)
    os.environ.pop('DISPLAY', None)
    os.execv(dna, [dna, '--tui', '/w/a.txt'])
seen = b''
deadline = time.time() + 10
# Document cells carry color codes; the status line names the file whole.
while time.time() < deadline and b'a.txt  [text]' not in seen:
    if select.select([fd], [], [], .2)[0]:
        seen += os.read(fd, 65536)
assert b'a.txt  [text]' in seen, seen[-400:]
for keys in (b'i', b'X', b'\x1b', b':w\r', b':qa!\r'):
    os.write(fd, keys)
    time.sleep(.4)
_, status = os.waitpid(pid, 0)
with open('/w/a.txt') as handle:
    saved = handle.read()
assert saved == 'Xhello from container\n', repr(saved)
print('PASS', version.stdout.strip(), 'edits and saves in the terminal frontend')
