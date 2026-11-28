#!/usr/bin/env python3
"""Run the Linux package in clean Ubuntu 24.04, Debian 13 and Fedora 40.

Each container gets only Python and a monospace font: no compiler, SDK,
checkout or display. Needs podman and network access for the images.
Usage: python3 tests/package_distros.py [archive]
On btrfs set DNA_PODMAN='podman --storage-driver vfs' (with its own --root).
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import private_display  # hides the desktop display; see tests/private_display.py

ROOT = Path(__file__).resolve().parents[1]
archive = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT/'build/packages/dna-preview-linux-x86_64.tar.gz'
podman = shlex.split(os.environ.get('DNA_PODMAN', 'podman'))
IMAGES = {
    'docker.io/library/ubuntu:24.04': 'apt-get update -qq && apt-get install -y -qq python3 fonts-dejavu-core',
    'docker.io/library/debian:trixie': 'apt-get update -qq && apt-get install -y -qq python3 fonts-dejavu-core',
    'registry.fedoraproject.org/fedora:40': 'dnf -y -q install python3 dejavu-sans-mono-fonts',
}
with tempfile.TemporaryDirectory(prefix='dna-distros-') as directory:
    shutil.copyfile(archive, Path(directory)/archive.name)
    shutil.copyfile(ROOT/'tests/package_distros/check.py', Path(directory)/'check.py')
    for image, install in IMAGES.items():
        print('==', image, flush=True)
        subprocess.run([*podman, 'run', '--rm', '--network=host', '-v', f'{directory}:/t:Z', image, 'sh', '-c',
                        f'{install} >/dev/null 2>&1; python3 /t/check.py'], check=True, timeout=900)
