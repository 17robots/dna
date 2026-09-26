#!/usr/bin/env python3
"""Build pinned SDL_ttf locally; never install system packages."""
import hashlib
from pathlib import Path
import subprocess
import tarfile
import urllib.request
ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / 'build/deps'
VERSION = '3.2.2'
SHA256 = '63547d58d0185c833213885b635a2c0548201cc8f301e6587c0be1a67e1e045d'
if (DEPS/'install/lib/libSDL3_ttf.so').exists():
    raise SystemExit(0)
DEPS.mkdir(parents=True, exist_ok=True)
archive = DEPS/f'SDL3_ttf-{VERSION}.tar.gz'
if not archive.exists():
    urllib.request.urlretrieve(f'https://github.com/libsdl-org/SDL_ttf/releases/download/release-{VERSION}/{archive.name}', archive)
if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
    raise SystemExit('SDL_ttf archive checksum mismatch')
with tarfile.open(archive) as source:
    source.extractall(DEPS, filter='data')
subprocess.run(['cmake','-S',str(DEPS/f'SDL3_ttf-{VERSION}'),'-B',str(DEPS/'ttf-build'),'-DCMAKE_BUILD_TYPE=Release','-DBUILD_SHARED_LIBS=ON','-DSDLTTF_SAMPLES=OFF','-DSDLTTF_VENDORED=OFF','-DSDLTTF_PLUTOSVG=OFF',f'-DCMAKE_INSTALL_PREFIX={DEPS}/install'],check=True)
subprocess.run(['cmake','--build',str(DEPS/'ttf-build'),'-j','4'],check=True)
subprocess.run(['cmake','--install',str(DEPS/'ttf-build')],check=True)
