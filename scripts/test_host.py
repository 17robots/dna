#!/usr/bin/env python3
"""Execute production host adapters on the current OS, in Unicode paths."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from dyn_path import real_dyn

suite = sys.argv[1] if len(sys.argv) > 1 else 'host'
if suite not in ('host', 'filesystem'):
    raise SystemExit('usage: test_host.py [host|filesystem]')
compiler = real_dyn()
if not compiler:
    raise SystemExit('Install the pinned Dyn SDK first.')
stage = ROOT / ('build/test-' + suite)
stage.mkdir(parents=True, exist_ok=True)
for module in ('host', 'filesystem'):
    shutil.copytree(ROOT / 'src' / module, stage / module, dirs_exist_ok=True)
(stage / 'main.dyn').write_text((ROOT / 'tests' / suite / 'main.dyn').read_text().replace('../../src/', './'))
# mise merges parent configuration. Do not leak Linux library paths into a
# native-host test, even when the SDK was installed through a staged config.
environment = dict(os.environ, DNA_HOST_TEST="value café 日本語", DNA_HOST_EMPTY="")
environment.pop("DNA_HOST_MISSING_7ab218", None)
for key in ('DYN_LIBRARY_PATH', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH'):
    environment.pop(key, None)
links = []
if sys.platform == 'darwin':
    sdk = Path(subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip())
    # Dyn bundles a minimal libSystem stub, not every API DNA uses.
    links = ['--link', str(sdk / 'usr/lib/libSystem.tbd'), '--link', '-syslibroot', '--link', str(sdk)]
elif os.name == 'nt':
    # Use the installed Windows SDK import library. Dyn's #link lookup expects
    # a GNU-style filename, but lld accepts the original COFF archive content.
    kits = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits/10/Lib'
    libraries = stage / 'lib'
    libraries.mkdir(exist_ok=True)
    for name in ('kernel32', 'advapi32'):
        candidates = sorted(kits.glob('*/um/x64/' + name + '.lib'))
        if not candidates:
            raise SystemExit('Windows SDK x64 ' + name + '.lib is required for native tests.')
        shutil.copyfile(candidates[-1], libraries / ('lib' + name + '.dll.a'))
    environment['DYN_LIBRARY_PATH'] = str(libraries)
for mode in ('debug', 'release'):
    binary = stage / (suite + '-' + mode + ('.exe' if os.name == 'nt' else ''))
    subprocess.run([sys.executable, str(ROOT / "scripts/compile.py"), str(compiler), 'build', str(stage), '--' + mode, '--no-cache', '--jobs', '1', '--output', str(binary), *links], env=environment, check=True, timeout=120)
    with tempfile.TemporaryDirectory(prefix='dna-host-') as temporary:
        directory = Path(temporary) / 'spaces café 日本語'
        directory.mkdir()
        if suite == 'filesystem':
            (directory / 'protected-directory').mkdir()
            try:
                (directory / 'link.txt').symlink_to('target 日本語.txt')
            except OSError as error:
                if os.name != 'nt':
                    raise
                print('Symlink fixture unavailable:', error, flush=True)
            else:
                (directory / 'link-enabled').touch()
        arguments = ["argument café 日本語", "", "with space"] if suite == "host" else []
        result = subprocess.run([str(binary), *arguments], cwd=directory, text=True, encoding='utf-8', capture_output=True, env=environment, timeout=20)
        if result.returncode:
            raise SystemExit(result.stdout + result.stderr)
        if suite == 'host':
            assert 'host stderr probe' in result.stderr, result.stderr
        assert 'PASS ' + suite in result.stdout, result.stdout
        if suite == 'filesystem':
            if os.name == 'nt':
                check = r"""
                $ErrorActionPreference = 'Stop'
                foreach ($name in @('private.txt','copied-permissions.txt','session.txt','private-directory')) {
                  $acl = Get-Acl -LiteralPath (Join-Path $env:DNA_TEST_DIR $name)
                  $rules = @($acl.Access)
                  if (!$acl.AreAccessRulesProtected -or $rules.Count -ne 1) { throw "Private DACL missing: $name" }
                  $sid = $rules[0].IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
                  if ($sid -ne 'S-1-3-4' -or $rules[0].AccessControlType -ne 'Allow') { throw "Unexpected private ACE: $name" }
                }
                $original = Get-Acl -LiteralPath (Join-Path $env:DNA_TEST_DIR 'private.txt')
                $copied = Get-Acl -LiteralPath (Join-Path $env:DNA_TEST_DIR 'copied-permissions.txt')
                if ($original.Sddl -ne $copied.Sddl) { throw 'Source security descriptor was not preserved' }
                """
                subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', check],
                               env=dict(environment, DNA_TEST_DIR=str(directory)), check=True, timeout=20)
            else:
                for name in ('private.txt', 'copied-permissions.txt', 'session.txt'):
                    assert (directory / name).stat().st_mode & 0o777 == 0o600, name
                assert (directory / 'private-directory').stat().st_mode & 0o777 == 0o700
        print(mode + ': ' + result.stdout.strip(), flush=True)
