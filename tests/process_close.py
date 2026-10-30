#!/usr/bin/env python3
"""Closing an owned process also kills a leader that changed process groups."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get('DYN', 'dyn')
with tempfile.TemporaryDirectory(prefix='dna-process-close-') as temporary:
    stage = Path(temporary)
    for source in (ROOT/'src/native/dyn').glob('*.dyn'):
        shutil.copyfile(source, stage/source.name)
    child = stage/'changed-group'
    child.write_text('#!/usr/bin/python3\nimport os,time\n'
                     'os.setpgid(0, os.getpgid(os.getppid()))\n'
                     'os.write(1,b"ready")\n'
                     'while True: time.sleep(60)\n')
    child.chmod(0o700)
    (stage/'main.dyn').write_text('''fn main() {
  command: []const u8 = "CHILD\\0"
  directory: []const u8 = "/tmp\\0"
  child := proc_open(&command[0], &directory[0], false)
  if child.pid <= 0 { #panic("child spawn") }
  bytes: [5]u8 = []
  used: usize = 0
  deadline := proc_ticks() + 2000
  for used < 5 && proc_ticks() < deadline {
    read := proc_read(child.output, &bytes[used], 5-used)
    if read > 0 { used += #cast(usize,read) }
    else if read != -11 && read != -4 { break }
  }
  if used != 5 { #panic("changed-group handshake") }
  proc_close(&child)
  proc_close(&child)
  if child.pid != 0 || child.input != -1 { #panic("close invalidates") }
}
'''.replace('CHILD', str(child)))
    for mode in ('debug', 'release'):
        binary = stage/f'probe-{mode}'
        subprocess.run(['python3', str(ROOT/'scripts/compile.py'), DYN, 'build',
                        str(stage), '--'+mode, '--output', str(binary), '--link',
                        str(ROOT/'build/deps/install/lib/libdna_native.so')], check=True)
        process = subprocess.Popen([str(binary)], start_new_session=True)
        try:
            assert process.wait(timeout=5) == 0
        finally:
            # The test owns this session; also clean up the moved child on failure.
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait()
        print('PASS changed-group process close:', mode)
