#!/usr/bin/env python3
"""Exercise native archive initialization without a shared-library constructor."""
import os
from pathlib import Path
import subprocess
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
binary = ROOT / 'build/static-native-lifecycle'
environment = dict(os.environ,
                   DYN_LIBRARY_PATH=str(ROOT / 'build/deps/tui-static'),
                   LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'),
                   DNA_RENDER_TRACE='1')
for archive_name in ('libdna_native.a', 'libdna_native_tui.a'):
    archive = ROOT/'build/deps/install/lib'/archive_name
    symbols = subprocess.check_output(['nm','--defined-only','-g','--format=posix',str(archive)],text=True)
    exports = {line.split()[0] for line in symbols.splitlines() if line.split()}
    assert not any(symbol.startswith('dyn_m') for symbol in exports), (archive_name,'generated SDK symbol escaped')
    for symbol in ('dna_mutex_create','dna_condition_wait','dna_thread_create','dna_terminal_open'):
        assert symbol in exports, (archive_name,symbol)
with tempfile.TemporaryDirectory(prefix='dna-static-sdk-') as directory:
    stage = Path(directory)/'consumer'
    shutil.copytree(ROOT/'tests/native/static_lifecycle',stage)
    entry = stage/'main.dyn'
    # Import the same SDK modules the archive uses. Before symbol isolation,
    # this consumer reproduced a duplicate std/errors.linux definition.
    text = entry.read_text()
    text = 'use "std/errors"\nuse "std/sync"\n'+text
    text = text.replace('fn main() {', 'fn main() {\n  sdk_lock:=sync.mutex()\n  sync.lock(&sdk_lock)\n  check(errors.linux(-22)==errors.Kind.InvalidInput,"SDK error classification")\n  sync.unlock(&sdk_lock)',1)
    entry.write_text(text)
    subprocess.run([
        'python3', str(ROOT / 'scripts/compile.py'), os.environ.get('DYN', 'dyn'),
        'build', str(stage), '--release', '--no-cache',
        '--output', str(binary),
    ], env=environment, check=True)
dynamic = subprocess.check_output(['readelf', '-d', str(binary)], text=True)
needed = [line for line in dynamic.splitlines() if '(NEEDED)' in line]
assert not any('libdna_native' in line for line in needed), 'must link native archive'
assert not any('SDL' in line for line in needed), 'terminal archive must not need SDL'
subprocess.run([str(binary)], env=environment, check=True, timeout=10)
