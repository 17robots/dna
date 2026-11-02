#!/usr/bin/env python3
"""Exercise the desktop CRT dispatch with a real dynamic library on Linux."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if not sys.platform.startswith('linux'):
    raise SystemExit('Run test_host.py bulk_memory for native desktop qualification')
with tempfile.TemporaryDirectory(prefix='dna-bulk-memory-') as temporary:
    work = Path(temporary)
    (work/'main.dyn').write_text((ROOT/'tests/bulk_memory/main.dyn').read_text())
    for source in (ROOT/'src/buffer/memory_windows.dyn', ROOT/'tests/bulk_memory/fill_windows.dyn'):
        (work/source.name).write_text(source.read_text().replace('#target(kernel: windows)', '#target(kernel: linux)').replace('ucrtbase.dll', 'libc.so.6'))
    libc = subprocess.check_output(['cc', '-print-file-name=libc.so.6'], text=True).strip()
    for mode in ('debug', 'release'):
        output = work/mode
        subprocess.run([sys.executable, ROOT/'scripts/compile.py', os.environ.get('DYN', 'dyn'),
                        'build', work, '--'+mode, '--output', output, '--link', libc], check=True, timeout=120)
        subprocess.run([output], check=True, timeout=10)
        print('PASS desktop CRT dispatch '+mode+' (Linux library substitution)', flush=True)
