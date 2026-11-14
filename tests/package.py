#!/usr/bin/env python3
"""Verify deterministic packaging, extracted dependencies and isolated startup."""
import hashlib
import json
import os
import shlex
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
    image = os.environ.get('DNA_PACKAGE_IMAGE')
    if image:
        # A clean image with only the extracted package and one font: no SDK,
        # checkout, network or writable root. No display, so the GUI cannot
        # start there; --version and a TUI smoke under a pseudo-terminal can.
        # DNA_PODMAN overrides the command, e.g. 'podman --storage-driver vfs'.
        podman = shlex.split(os.environ.get('DNA_PODMAN', 'podman'))
        identity = subprocess.check_output([*podman, 'image', 'inspect', '--format', '{{.Id}}', image], text=True).strip()
        font = subprocess.check_output(['fc-match', '-f', '%{file}', 'monospace'], text=True).strip()
        container = [*podman, 'run', '--rm', '--pull=never', '--network=none', '--read-only', '--tmpfs', '/tmp',
                     '-v', f'{package}:/preview:ro', '-v', f'{font}:/font.ttf:ro',
                     '-e', 'HOME=/tmp', '-e', 'DNA_FONT=/font.ttf', '-e', 'TERM=xterm-256color',
                     '-e', 'DYN_EDITOR_SMOKE=1', '-e', 'DNA_RECOVERY=0', '-e', 'DNA_CONFIG=/tmp/config.toml',
                     '-e', 'DNA_LANGUAGE_DIR=/tmp/languages']
        version = subprocess.run([*container, identity, '/preview/dna', '--version'],
                                 capture_output=True, text=True, timeout=60)
        assert version.returncode == 0 and version.stdout.startswith('dna '), (version.stdout, version.stderr)
        tui = subprocess.run(['script', '-qec', shlex.join([*container, '-t', identity, 'timeout', '30',
                                                            '/preview/dna', '--tui']) + '; echo "exit=$?"',
                              '/dev/null'], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        assert tui.stdout.rstrip().endswith('exit=0'), (tui.stdout[-400:], tui.stderr)
        report = {'image': identity, 'archive_sha256': first,
                  'mode': 'clean image: --version and a TUI smoke under a pseudo-terminal; no SDK, repository, network or display'}
        (ROOT / 'build/packages/container-check.json').write_text(json.dumps(report, indent=2) + '\n')
        print('PASS clean-image version and TUI startup:', identity)
    else:
        print('Container check not requested; set DNA_PACKAGE_IMAGE to a local image')
