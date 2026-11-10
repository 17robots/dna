#!/usr/bin/env python3
"""Windows on ARM builds and runs native ARM64 test programs, not emulated x64.

The x64 compiler runs under emulation and an x64 program would still pass every
test there, so check the machine type of what the tests actually build and of
the Python that loads their DLLs.
"""
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn
from windows_target import TARGET

ARM64 = 0xAA64


def machine(path):
    data = path.read_bytes()
    offset = struct.unpack_from('<I', data, 0x3C)[0]
    assert data[offset:offset + 4] == b'PE\0\0', path
    return struct.unpack_from('<H', data, offset + 4)[0]


assert os.name == 'nt' and TARGET == 'aarch64-windows', 'Run on Windows on ARM with DNA_WINDOWS_TARGET=aarch64-windows'
assert platform.machine().upper() == 'ARM64', ('Python must be native ARM64', platform.machine())
compiler = real_dyn()
assert compiler, 'Install the pinned Dyn SDK first.'
with tempfile.TemporaryDirectory(prefix='dna-arm64-') as temporary:
    stage = Path(temporary) / 'app'
    stage.mkdir()
    (stage / 'main.dyn').write_text('use "std/io"\nfn main() { io.println("arm64 ok") }\n')
    for mode, shared in (('debug', False), ('release', False), ('release', True)):
        output = Path(temporary) / (mode + ('.dll' if shared else '.exe'))
        command = [sys.executable, str(ROOT / 'scripts/compile.py'), str(compiler), 'build', str(stage),
                   '--' + mode, '--output', str(output)] + (['--shared'] if shared else [])
        subprocess.run(command, check=True, timeout=300)
        assert machine(output) == ARM64, (output, hex(machine(output)))
        if not shared:
            result = subprocess.run([str(output)], check=True, capture_output=True, text=True, timeout=30)
            assert result.stdout.strip() == 'arm64 ok', result.stdout
print('PASS Windows on ARM: emulated x64 compiler builds native ARM64 programs and DLLs; Python is ARM64')
