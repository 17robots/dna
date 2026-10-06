#!/usr/bin/env python3
"""Exercise the real Dyn installer with a deterministic package-manager fixture."""
import os
import shutil
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
helper = ROOT / 'build/deps/install/bin/dna-language'
with tempfile.TemporaryDirectory(prefix='dna-servers-') as directory:
    base = Path(directory)
    tools = base / 'bin'
    tools.mkdir()
    # Only fixture commands and required system utilities are on PATH.
    for utility in ('mkdir', 'chmod', 'timeout', 'rm'):
        executable = shutil.which(utility)
        assert executable, f'missing test utility: {utility}'
        (tools / utility).symlink_to(executable)
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
    env = dict(os.environ, PATH=str(tools), DNA_LANGUAGE_DIR=str(languages), XDG_CONFIG_HOME=str(base / 'config'))
    def run(*args, success=True):
        result = subprocess.run([helper, *args], env=env, capture_output=True, text=True, timeout=15)
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return result.stdout
    listing = run('list')
    assert 'Language servers available to install:' in listing and 'python: pyright@' in listing
    # The installer checks for Node, but our shell-only npm/server fixtures
    # never execute it. Also retain proof that a missing runtime is rejected.
    run('server-install', 'python', success=False)
    node = tools / 'node'
    node.write_text('#!/bin/sh\nexit 99\n')
    node.chmod(0o755)
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
    assert 'server\tpython\tinstalled\n' in run('catalog')
    env.pop('DNA_FAIL_INSTALL')
    run('server-uninstall', 'python')
    assert not active.is_symlink() and not second.exists()
    assert first.is_dir(), 'uninstall must not delete retained versions'
    assert 'server\tpython\tavailable\n' in run('catalog')
    run('server-run', 'python', success=False)
    # Do not follow a replacement symlink outside the managed package root.
    outside = base / 'outside'
    outside.mkdir()
    active.symlink_to(outside)
    run('server-uninstall', 'python', success=False)
    assert active.is_symlink() and outside.is_dir()
    active.unlink()
    # Grammar removal follows the same ownership rule, including spaces.
    grammar = languages / '.json-Ab123x'
    grammar.mkdir()
    for leaf in ('parser.so', 'highlights.scm', 'extensions'):
        (grammar / leaf).write_text('fixture')
    (languages / 'json').symlink_to(grammar)
    assert 'grammar\tjson\tinstalled\n' in run('catalog')
    run('uninstall', 'json')
    assert not grammar.exists() and not (languages / 'json').is_symlink()
    run('uninstall', '../outside', success=False)
    # Both HOME defaults and XDG overrides install inside DNA's config folder.
    env.pop('DNA_LANGUAGE_DIR')
    env['HOME'] = str(base / 'home')
    run('server-install', 'python')
    assert (base / 'config/dna/languages/.servers/python').is_symlink()
    env.pop('XDG_CONFIG_HOME')
    run('server-install', 'python')
    assert (base / 'home/.config/dna/languages/.servers/python').is_symlink()
    assert not (base / 'home/.local/share/dna').exists()
print('PASS managed servers: listing, install, launch, retained update, failed-update preservation, invalid names')
