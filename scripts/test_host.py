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
from sdk_compat import environment as sdk_environment

suite = sys.argv[1] if len(sys.argv) > 1 else 'host'
if suite not in ('host', 'filesystem', 'clone', 'threads', 'bulk_memory'):
    raise SystemExit('usage: test_host.py [host|filesystem|clone|threads|bulk_memory]')
compiler = real_dyn()
if not compiler:
    raise SystemExit('Install the pinned Dyn SDK first.')
stage = ROOT / ('build/test-' + suite)
stage.mkdir(parents=True, exist_ok=True)
modules = () if suite in ('threads', 'bulk_memory') else ('owned_arena', 'cstring', 'host', 'filesystem')
if suite == 'clone':
    modules += ('files', 'buffer')
for module in modules:
    shutil.copytree(ROOT / 'src' / module, stage / module, dirs_exist_ok=True)
fixture = ROOT / 'tests/clone_save/native.dyn' if suite == 'clone' else ROOT / 'tests' / suite / 'main.dyn'
(stage / 'main.dyn').write_text(fixture.read_text().replace('../../src/', './'))
if suite == 'threads':
    native = ROOT / 'src/native/dyn'
    (stage / 'sync.dyn').write_text((native / 'sync.dyn').read_text().split("// Dyn's current executable entry point")[0])
    for name in ('clock.dyn', 'sync_linux.dyn', 'sync_desktop.dyn', 'sync_macos.dyn', 'sync_windows.dyn'):
        shutil.copyfile(native / name, stage / name)
if '--object-only' in sys.argv[2:]:
    if suite != 'threads':
        raise SystemExit('--object-only is supported for threads only')
    for target in ('x86_64-windows', 'aarch64-windows', 'x86_64-macos', 'aarch64-macos'):
        for mode in ('debug', 'release'):
            subprocess.run([str(compiler), 'build', str(stage), '--' + mode, '--target', target,
                            '--emit-object', '--no-link', '--quiet', '--output', str(stage / (target + '-' + mode))],
                           check=True, timeout=120, env=sdk_environment(compiler))
        print('PASS native thread objects: ' + target, flush=True)
    raise SystemExit
if suite == 'bulk_memory':
    for source in (ROOT/'src/buffer').glob('memory_*.dyn'):
        shutil.copyfile(source, stage/source.name)
    for source in (ROOT/'tests/bulk_memory').glob('fill_*.dyn'):
        shutil.copyfile(source, stage/source.name)
# mise merges parent configuration. Do not leak Linux library paths into a
# native-host test, even when the SDK was installed through a staged config.
environment = dict(os.environ, DNA_HOST_TEST="value café 日本語", DNA_HOST_EMPTY="",
                   DNA_TEST_FILE_MAPPING="1" if sys.platform == "darwin" or os.name == "nt" else "0")
environment.pop("DNA_HOST_MISSING_7ab218", None)
for key in ('DYN_LIBRARY_PATH', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH'):
    environment.pop(key, None)
links = []
if suite in ('threads', 'bulk_memory') and sys.platform.startswith('linux'):
    libc = subprocess.check_output(['cc', '-print-file-name=libc.so.6'], text=True).strip()
    links = ['--link', libc]
if sys.platform == 'darwin':
    sdk = Path(subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip())
    # These tests use APIs beyond Dyn's minimal libSystem stub. Select native
    # SDK linking explicitly; the built-in linker does not consume -syslibroot.
    environment['DYN_LINKER'] = 'external'
    linker_directory = stage / 'linker'
    linker_directory.mkdir(exist_ok=True)
    linker = linker_directory / 'ld64.lld'
    if linker.is_symlink():
        linker.unlink()
    native_linker = subprocess.check_output(['xcrun', '--find', 'ld'], text=True).strip()
    linker.symlink_to(native_linker)
    environment['PATH'] = str(linker_directory) + os.pathsep + environment.get('PATH', '')
    links = ['--link', str(sdk / 'usr/lib/libSystem.tbd'), '--link', '-syslibroot', '--link', str(sdk)]
    if suite == 'clone':
        prefix = Path(subprocess.check_output(['brew', '--prefix', 'utf8proc'], text=True).strip())
        environment['DYN_LIBRARY_PATH'] = str(prefix / 'lib')
        links += ['--link', str(prefix / 'lib/libutf8proc.dylib')]
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
        result = subprocess.run([str(binary), *arguments], cwd=directory, text=True, encoding='utf-8', capture_output=True, env=environment, timeout=60 if suite == 'clone' else 20)
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
