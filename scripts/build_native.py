#!/usr/bin/env python3
"""Build the Linux native GUI without SDL."""
import argparse
import ctypes
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from runpath import runpath
ROOT=Path(__file__).resolve().parents[1]
def run(command,**kwargs):
    subprocess.run([str(part) for part in command],check=True,**kwargs)
def build():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend',choices=('auto','x11','wayland'),default='auto')
    parser.add_argument('--release',action='store_true')
    parser.add_argument('--mode',choices=('debug','release'))
    parser.add_argument('--output',type=Path,help='Also publish the verified binary at this path')
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--no-cache',action='store_true')
    parser.add_argument('--source',type=Path,default=ROOT/'src',help='Native source tree, including a staged module profile')
    args=parser.parse_args()
    if args.backend=='auto':
        args.backend='wayland' if os.environ.get('WAYLAND_DISPLAY') else 'x11'
    if not sys.platform.startswith('linux'): raise SystemExit('Native GUI currently targets Linux.')
    # Fail before replacing build outputs
    # when the native text backend cannot load its runtime providers.
    for library in ('libharfbuzz.so.0', 'libfribidi.so.0', 'libfreetype.so.6'):
        try:
            ctypes.CDLL(library)
        except OSError as error:
            raise SystemExit(f'Native text requires {library}: {error}')
    from dyn_path import real_dyn
    compiler=real_dyn()
    if compiler is None: raise SystemExit('Dyn compiler not found; set DYN to the matching compiler')
    from sdk_check import require_ui_sdk
    require_ui_sdk(str(compiler))
    from deps import compiler_and_runtime
    _, runtime=compiler_and_runtime()
    if not (runtime/'dynrt_shared.o').exists(): raise SystemExit('DYN must point at compiler with shared runtime objects')
    mode=args.mode or ('release' if args.release else 'debug')
    output=ROOT/('build/native-wayland' if args.backend=='wayland' else 'build/native-gui');output.mkdir(parents=True,exist_ok=True)
    if args.backend=='wayland':
        from sdk_check import window_builder
        native_build=window_builder(compiler)
        run([sys.executable,native_build,'--output',output/'libdyn_window.so'],
            env=dict(os.environ, CC=os.environ.get('CC','cc')+' -Wl,-soname,libdyn_window.so'))
    (output/'deps').mkdir(exist_ok=True)
    install=output/'deps/install'
    if not install.exists(): install.symlink_to(ROOT/'build/deps/install',target_is_directory=True)
    bridge=output/'bridge'
    stage=output/'editor'
    for folder in (bridge,stage):
        if folder.exists(): shutil.rmtree(folder)
    shutil.copytree(ROOT/'src/native/dyn',bridge)
    run([sys.executable,ROOT/'scripts/compile.py',compiler,'build',bridge,'--shared','--release','--emit-object','--output',output/'support.so'])
    flags=shlex.split(subprocess.check_output(['pkg-config','--libs','vterm','tree-sitter','libpcre2-8','libutf8proc'],text=True))
    hidden=output/'hide-runtime.map';hidden.write_text('{ local: memcpy; memmove; memset; };\n')
    runtime_name='dna_native_wayland' if args.backend=='wayland' else 'dna_native_gui'
    runtime_file='lib'+runtime_name+'.so'
    run(['cc','-shared','-Wl,-soname,'+runtime_file,'-Wl,-z,defs','-Wl,--version-script='+str(hidden),output/'support.so.o',runtime/'dynrt_shared.o',runtime/'dynrt_support_pic.o','-lutil','-pthread','-ldl',*flags,'-o',output/(runtime_file+'.tmp')])
    (output/(runtime_file+'.tmp')).replace(output/runtime_file)
    # Keep direct-load support-library oracles on the same native ABI.
    compatibility=output/'libdna_native.so.tmp'
    compatibility.unlink(missing_ok=True)
    compatibility.symlink_to(runtime_file)
    compatibility.replace(output/'libdna_native.so')
    shutil.copytree(args.source.resolve(),stage)
    shutil.copyfile(ROOT/f'modules/native/platform_{args.backend}.dyn',stage/'platform/backend/backend.dyn')
    if args.backend=='x11':
        for source in [stage/'platform/gui.dyn',*(stage/'platform/native_present').rglob('*.dyn')]:
            source.write_text(source.read_text().replace('"vendor/window/wayland"','"vendor/window"'))
    if args.smoke: shutil.copytree(ROOT/'tests/editor',stage,dirs_exist_ok=True)
    for source in stage.rglob('*.dyn'):
        text=source.read_text()
        rewritten=text.replace('#link("dna_native")', '#link("'+runtime_name+'")')
        if rewritten!=text: source.write_text(rewritten)
    environment=dict(os.environ,DYN_LIBRARY_PATH=str(output))
    name=('dna-native-wayland' if args.backend=='wayland' else 'dna-native')+('-smoke' if args.smoke else '')+'-'+mode
    binary=ROOT/'build'/name
    # Staged test/profile sources must never replace the full release editor.
    if args.source.resolve()!=ROOT/'src' and args.output:
        binary=args.output.resolve()
        binary.parent.mkdir(parents=True,exist_ok=True)
    library_paths=runpath()+':$ORIGIN/'+output.name
    if args.output:
        library_paths+=':$ORIGIN/'+os.path.relpath(output,args.output.resolve().parent)
    run([sys.executable,ROOT/'scripts/compile.py',compiler,'build',stage,'--'+mode,*(['--no-cache'] if args.no_cache else []),'--output',binary,'--link',library_paths,'--link','--version-script='+str(hidden)],env=environment)
    dependencies=subprocess.check_output(['ldd',str(binary)],text=True)
    print(dependencies)
    if 'libSDL' in dependencies: raise SystemExit('Native profile unexpectedly links SDL')
    if args.backend=='wayland' and any(library in dependencies for library in ('libX11.so','libGLX.so')):
        raise SystemExit('Wayland profile unexpectedly links X11/GLX')
    if args.output:
        destination=args.output.resolve()
        if destination!=binary:
            destination.parent.mkdir(parents=True,exist_ok=True)
            temporary=destination.with_name(destination.name+'.tmp')
            shutil.copy2(binary,temporary)
            temporary.replace(destination)
    print('Built '+name+'; native '+args.backend+' GUI, no SDL.')
def main():
    # Staging and support-library replacement must be serialized together, not
    # just the individual compiler calls inside this build.
    from build_limits import compiler_lock
    (ROOT/'build').mkdir(exist_ok=True)
    with compiler_lock(ROOT/'build/.native-build.lock'):
        build()

if __name__=='__main__': main()
