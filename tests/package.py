#!/usr/bin/env python3
"""Verify deterministic packaging and run only extracted files in a clean image."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
archive = ROOT / 'build/packages/dna-preview-linux-x86_64.tar.gz'
subprocess.run(['python3', str(ROOT / 'scripts/package.py')], check=True)
first = hashlib.sha256(archive.read_bytes()).hexdigest()
subprocess.run(['python3', str(ROOT / 'scripts/package.py')], check=True)
assert hashlib.sha256(archive.read_bytes()).hexdigest() == first, 'archive is not deterministic'
with tempfile.TemporaryDirectory(prefix='dna-clean-package-') as temporary:
    directory = Path(temporary)
    with tarfile.open(archive) as bundle:
        assert not any('.dyncache' in p.name or '__pycache__' in p.name for p in bundle.getmembers())
        bundle.extractall(directory, filter='data')
    package = directory / 'dna-preview-linux-x86_64'
    assert (package / 'LICENSE').read_bytes() == (ROOT / 'LICENSE').read_bytes()
    for entry in (package / 'SHA256SUMS').read_text().splitlines():
        digest, filename = entry.split('  ', 1)
        assert hashlib.sha256((package / filename).read_bytes()).hexdigest() == digest
    # Load the extracted Dyn/C adapter without repository library search paths.
    host_env = dict(PATH=os.defpath, HOME=str(directory), SDL_VIDEODRIVER='dummy',
                    DYN_EDITOR_SMOKE='1', DNA_RECOVERY='0',
                    DNA_CONFIG=str(directory/'config.toml'),
                    DNA_LANGUAGE_DIR=str(directory/'languages'))
    subprocess.run([str(package/'dna')], cwd=directory, env=host_env, check=True, timeout=30)
    print('PASS relocated package startup/presentation/shutdown on current host')
    image = os.environ.get('DNA_PACKAGE_IMAGE')
    if image:
        # Pin the locally selected image for this invocation; no image pull or network.
        identity = subprocess.check_output(['podman', 'image', 'inspect', '--format', '{{.Id}}', image], text=True).strip()
        font = subprocess.check_output(['fc-match', '-f', '%{file}', 'monospace'], text=True).strip()
        subprocess.run([
            'podman', 'run', '--rm', '--pull=never', '--network=none', '--read-only', '--tmpfs', '/tmp',
            '-v', f'{package}:/preview:ro', '-v', f'{font}:/font.ttf:ro',
            '-e', 'HOME=/tmp', '-e', 'SDL_VIDEODRIVER=dummy', '-e', 'DNA_FONT=/font.ttf',
            '-e', 'DYN_EDITOR_SMOKE=1', '-e', 'DNA_RECOVERY=0', '-e', 'DNA_CONFIG=/tmp/config.toml',
            '-e', 'DNA_LANGUAGE_DIR=/tmp/languages', identity, '/preview/dna',
        ], check=True, timeout=30)
        report = {'image': identity, 'archive_sha256': first, 'mode': 'headless extracted-package smoke; no SDK/repository mount or network'}
        (ROOT / 'build/packages/container-check.json').write_text(json.dumps(report, indent=2)+'\n')
        print('PASS isolated package startup:', identity)
    else:
        print('Container check not requested; set DNA_PACKAGE_IMAGE to a local compatible image.')
print('PASS repeated archive SHA-256 and extracted checksums:', first)
