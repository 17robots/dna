#!/usr/bin/env python3
"""Verify deterministic packaging, extracted dependencies and isolated startup."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn
archive = ROOT / 'build/packages/dna-preview-linux-x86_64.tar.gz'
subprocess.run([sys.executable, str(ROOT/'tests/desktop_install.py')], check=True)
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
    host_env = dict(os.environ, PATH=os.defpath, HOME=str(directory),
                    DYN_EDITOR_SMOKE='1', DNA_RECOVERY='0',
                    DNA_CONFIG=str(directory/'config.toml'),
                    DNA_LANGUAGE_DIR=str(directory/'languages'))
    for variable in ('LD_LIBRARY_PATH', 'DYN_LIBRARY_PATH', 'LD_PRELOAD', 'DNA_WORKFLOW_TEST', 'DYN_SDK'):
        host_env.pop(variable, None)
    desktop_data = directory/'desktop-data'
    subprocess.run([str(package/'dna-install-desktop')],
                   env=dict(host_env, XDG_DATA_HOME=str(desktop_data)), check=True)
    for name, mode, terminal in (('dna', '--gui', 'false'), ('dna-tui', '--tui', 'true')):
        entry = desktop_data/'applications'/(name+'.desktop')
        subprocess.run(['desktop-file-validate', str(entry)], check=True)
        content = entry.read_text()
        assert str(package/'dna') in content and str(ROOT) not in content, content
        assert mode+' %f' in content and 'Terminal='+terminal in content, content
    print('PASS packaged desktop registration: relocated GUI/TUI entries')
    library_env = dict(host_env, LD_LIBRARY_PATH=str(package / 'lib'))
    for binary in [*(package / 'bin').iterdir(), *(package / 'lib').iterdir()]:
        paths = subprocess.check_output(['ldd', str(binary)], env=library_env, text=True)
        assert 'not found' not in paths, paths
        assert str(ROOT) not in paths, paths
        dynamic = subprocess.check_output(['readelf', '-d', str(binary)], text=True)
        assert str(ROOT) not in dynamic, dynamic
    subprocess.run([str(package/'dna')], cwd=directory, env=host_env, check=True, timeout=30)
    for backend, display in (('wayland', 'WAYLAND_DISPLAY'), ('x11', 'DISPLAY')):
        if host_env.get(display):
            subprocess.run([str(package / 'bin' / ('dna-' + backend))], cwd=directory,
                           env=library_env, check=True, timeout=30)
            print('PASS extracted ' + backend + ' startup/presentation/shutdown')
    subprocess.run(['python3', str(ROOT/'tests/version.py'), '--binary', str(package/'dna'),
                    '--binary', str(package/'bin/dna-wayland'), '--binary', str(package/'bin/dna-x11')],
                   env=host_env, check=True, timeout=30)
    print('PASS relocated launcher and dependencies without checkout library paths')
    isolation = shutil.which('bwrap')
    if isolation:
        probe = subprocess.run([isolation, '--ro-bind', '/', '/', '--', '/usr/bin/true'],
                               capture_output=True, text=True)
        if probe.returncode:
            print('UNAVAILABLE mount isolation: ' + probe.stderr.strip())
            isolation = None
    if isolation:
        sandbox = ['bwrap', '--ro-bind', '/', '/', '--bind', str(directory), str(directory),
                   '--tmpfs', str(ROOT), '--tmpfs', str(real_dyn().parent.parent), '--']
        subprocess.run([*sandbox, str(package / 'dna')], cwd=directory,
                       env=host_env, check=True, timeout=30)
        print('PASS extracted package with checkout and Dyn SDK hidden by mount namespace')
    else:
        print('UNAVAILABLE mount isolation; extracted startup and dependency checks still required')
    print('PASS package contains no SDL dependency')
    assert not any('SDL' in p.name for p in (package/'lib').iterdir())
