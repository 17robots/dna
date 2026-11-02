#!/usr/bin/env python3
"""Run Darwin vnode policy against deterministic native-call substitutes."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-darwin-disk-') as temporary:
    work=Path(temporary)
    source=(ROOT/'src/native/dyn/disk_macos.dyn').read_text()
    (work/'disk.dyn').write_text(source.replace('#target(kernel: darwin)', '#target(kernel: linux)'))
    (work/'main.dyn').write_text((ROOT/'tests/fixtures/disk_macos_mock.dyn').read_text())
    for mode in ('debug','release'):
        output=work/mode
        subprocess.run([sys.executable,ROOT/'scripts/compile.py',os.environ.get('DYN','dyn'),'build',work,'--'+mode,'--output',output],check=True,timeout=120)
        subprocess.run([output],check=True,timeout=10)
        print('PASS Darwin vnode '+mode+' (mocked OS calls; not native qualification)',flush=True)
