#!/usr/bin/env python3
"""Isolated native window/presenter qualification; no editor service bridge or clipboard."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def run(command, **kwargs):
    subprocess.run([str(part) for part in command], check=True, timeout=180, **kwargs)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--object-only', action='store_true', help='compile desktop objects without GUI execution')
    parser.add_argument('--target', action='append', default=[], help='Dyn object target; repeatable')
    args = parser.parse_args()
    compiler = Path(os.environ.get('DYN', ROOT.parent/'dyn/compiler/build/dyn-release')).resolve()
    sdk = compiler.parent.parent
    bridge_builder = sdk/'vendor/window/native/build.py'
    if not bridge_builder.is_file():
        raise SystemExit('DYN must identify a compiler checkout containing vendor/window/native/build.py')
    with tempfile.TemporaryDirectory(prefix='dna-native-desktop-') as directory:
        work = Path(directory)
        stage = work/'probe'
        shutil.copytree(ROOT/'tests/native_desktop_fixture', stage)
        shutil.copytree(ROOT/'src/platform/native_present', stage/'presenter')
        for source in (stage/'presenter').rglob('*.dyn'):
            source.write_text(source.read_text().replace('"vendor/window/wayland"', '"vendor/window/native"').replace('"vendor/window"', '"vendor/window/native"'))
        targets = args.target or ['x86_64-windows', 'aarch64-windows', 'x86_64-macos', 'aarch64-macos']
        for target in targets:
            for mode in ('debug', 'release'):
                run([compiler,'build',stage,'--'+mode,'--target',target,'--emit-object','--no-link','--quiet','--output',work/(target+'-'+mode)])
            print('PASS isolated desktop object compilation: '+target, flush=True)
        if args.object_only:
            print('QUALIFICATION GAP: object compilation does not qualify native window, events or GL runtime')
            return
        if sys.platform.startswith('linux'):
            if not os.environ.get('WAYLAND_DISPLAY'):
                raise SystemExit('Wayland compositor required for desktop runtime qualification; use --object-only otherwise')
            library = work/'libdyn_window.so'
        elif sys.platform == 'darwin':
            library = work/'libdyn_window.dylib'
        elif sys.platform == 'win32':
            library = work/'dyn_window.dll'
        else:
            raise SystemExit('Unsupported desktop runtime host; use --object-only')
        run([sys.executable,bridge_builder,'--output',library])
        env = dict(os.environ, DYN_LIBRARY_PATH=str(work))
        if sys.platform.startswith('linux'):
            env['LD_LIBRARY_PATH'] = str(work)+os.pathsep+env.get('LD_LIBRARY_PATH','')
        elif sys.platform == 'darwin':
            env['DYLD_LIBRARY_PATH'] = str(work)+os.pathsep+env.get('DYLD_LIBRARY_PATH','')
        else:
            env['PATH'] = str(work)+os.pathsep+env.get('PATH','')
        for mode in ('debug','release'):
            output = work/('desktop-'+mode+('.exe' if sys.platform=='win32' else ''))
            run([compiler,'build',stage,'--'+mode,'--quiet','--output',output], env=env)
            if sys.platform.startswith('linux'):
                dependencies = subprocess.check_output(['ldd',str(output)],env=env,text=True)
                if any(name in dependencies for name in ('libdna_native','libSDL','libX11.so','libGLX.so')):
                    raise SystemExit('Isolated desktop unexpectedly links editor/SDL/X11 services:\n'+dependencies)
            run([output],env=env)
            print('PASS isolated desktop runtime '+mode+': controls, ordered wake, GL upload/readback, presenter recreation',flush=True)
        print('QUALIFICATION GAP: native Windows/macOS execution is unqualified on Linux; cross objects are not runtime qualification')
        print('QUALIFICATION GAP: keyboard layout/KEY.height producer snapshots are not tested; Win32/Cocoa snapshots require native runtime qualification. No clipboard qualification.')

if __name__ == '__main__':
    main()
