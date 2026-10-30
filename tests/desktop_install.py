#!/usr/bin/env python3
"""Exercise bundled desktop registration through the real XDG command parser."""
import configparser
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'packaging/linux'


def entries(data):
    return [data/'applications/dna.desktop', data/'applications/dna-tui.desktop']


def install(package, env, *arguments):
    subprocess.run([str(package/'dna-install-desktop'), *arguments], env=env, check=True)
    subprocess.run(['desktop-file-validate', *map(str, entries(Path(env.get('XDG_DATA_HOME', str(Path(env['HOME'])/'.local/share')))))], check=True)


def launch(entry, mode, document, env, work):
    parsed = configparser.ConfigParser(interpolation=None)
    parsed.read(entry)
    assert parsed['Desktop Entry']['Terminal'] == ('true' if mode == '--tui' else 'false')
    # Keep the installed Terminal=true entry intact. Exercise its Exec field
    # without opening a user's terminal while the fixture records argv.
    probe = work/('probe-'+entry.name)
    probe.write_text(entry.read_text().replace('Terminal=true', 'Terminal=false'))
    log = Path(env['DNA_DESKTOP_TEST_LOG'])
    log.unlink(missing_ok=True)
    subprocess.run(['gio', 'launch', str(probe), str(document)], env=env, check=True)
    expected = mode+'\n'+str(document)+'\n'
    deadline = time.monotonic()+5
    while not log.exists() or log.read_text() != expected:
        assert time.monotonic() < deadline, log.read_text() if log.exists() else 'launcher did not run'
        time.sleep(.01)


with tempfile.TemporaryDirectory(prefix='dna-desktop-') as directory:
    work = Path(directory)
    package = work/'DNA with spaces "quotes" $cash `ticks` \\ and 100% & more'
    shutil.copytree(ASSETS, package)
    launcher = package/'dna'
    launcher.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" > "$DNA_DESKTOP_TEST_LOG"\n')
    launcher.chmod(0o755)
    home = work/'home'
    home.mkdir()
    data = work/'custom data'
    env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(data), PATH=os.defpath,
               DNA_DESKTOP_TEST_LOG=str(work/'argv.log'))
    document = work/'file with spaces and %f.txt'
    document.write_text('fixture')
    install(package, env)
    for entry, mode in zip(entries(data), ('--gui', '--tui')):
        launch(entry, mode, document, env, work)
    # Repeating setup is idempotent; an upgrade replaces both executable paths.
    before = [entry.read_bytes() for entry in entries(data)]
    install(package, env)
    assert before == [entry.read_bytes() for entry in entries(data)]
    newer = work/'next version'
    shutil.copytree(package, newer)
    install(newer, env)
    for entry, mode in zip(entries(data), ('--gui', '--tui')):
        assert str(package) not in entry.read_text()
        launch(entry, mode, document, env, work)
    # Source/manual setup can select a launcher and use the default XDG path.
    default_env = {key: value for key, value in env.items() if key != 'XDG_DATA_HOME'}
    install(ASSETS, default_env, '--launcher', str(newer/'dna'))
    assert all(entry.is_file() for entry in entries(home/'.local/share'))
    # Reject invalid targets before creating an application directory.
    bad_data = work/'not created'
    result = subprocess.run([str(newer/'dna-install-desktop'), '--launcher', str(work/'missing')],
                            env=dict(env, XDG_DATA_HOME=str(bad_data)), capture_output=True, text=True)
    assert result.returncode != 0 and not bad_data.exists()
    assert not list((data/'applications').glob('.dna*.desktop.*'))
print('PASS desktop registration: GUI/TUI argv, real XDG escaping, spaces/quotes/percent, custom/default XDG paths, repeat setup, upgrade, invalid target')
