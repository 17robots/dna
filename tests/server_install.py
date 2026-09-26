#!/usr/bin/env python3
"""Exercise the real Dyn installer with a deterministic package-manager fixture."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
helper = ROOT / 'build/deps/install/bin/dna-language'
with tempfile.TemporaryDirectory(prefix='dna-servers-') as directory:
    base = Path(directory)
    tools = base / 'bin'
    tools.mkdir()
    npm = tools / 'npm'
    npm.write_text('''#!/bin/sh
set -eu
while test "$1" != --prefix; do shift; done
shift
prefix=$1
if test "${DNA_FAIL_INSTALL:-0}" = 1; then exit 7; fi
mkdir -p "$prefix/node_modules/.bin"
printf '#!/bin/sh\\nprintf server-ok\\n' > "$prefix/node_modules/.bin/pyright-langserver"
chmod +x "$prefix/node_modules/.bin/pyright-langserver"
printf '{}' > "$prefix/package-lock.json"
''')
    npm.chmod(0o755)
    languages = base / 'languages with spaces'
    env = dict(os.environ, PATH=f'{tools}:{os.environ["PATH"]}', DNA_LANGUAGE_DIR=str(languages), XDG_CONFIG_HOME=str(base / 'config'))
    def run(*args, success=True):
        result = subprocess.run([helper, *args], env=env, capture_output=True, text=True, timeout=15)
        assert (result.returncode == 0) == success, result.stderr
        return result.stdout
    listing = run('list')
    assert 'Language servers available to install:' in listing and 'python: pyright@' in listing
    run('server-install', 'python')
    active = languages / '.servers/python'
    first = active.resolve()
    assert first.is_dir() and (first / 'package-lock.json').is_file()
    assert run('server-run', 'python') == 'server-ok'
    run('server-update', 'python')
    second = active.resolve()
    assert first != second and first.is_dir()
    env['DNA_FAIL_INSTALL'] = '1'
    run('server-update', 'python', success=False)
    assert active.resolve() == second
    run('server-install', '../invalid', success=False)
    assert '  python\n' in run('list')
print('PASS managed servers: listing, install, launch, retained update, failed-update preservation, invalid names')
