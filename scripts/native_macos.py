"""Native Darwin support-library and Cocoa editor build path."""
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys

from dyn_path import real_dyn
from sdk_check import window_builder
from sdk_compat import environment as sdk_environment
from build_limits import compiler_lock

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT/'build/deps'
PACKAGES = ('vterm', 'tree-sitter >= 0.25', 'libpcre2-8', 'libutf8proc')
TEXT_PACKAGES = ('harfbuzz', 'fribidi', 'freetype2')


def run(command, **kwargs):
    subprocess.run([str(part) for part in command], check=True, **kwargs)


def linker_environment(compiler):
    environment = sdk_environment(compiler)
    sdk = subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip()
    linker = DEPS/'macos-linker/ld64.lld'
    linker.parent.mkdir(parents=True, exist_ok=True)
    native = subprocess.check_output(['xcrun', '--find', 'ld'], text=True).strip()
    if not linker.is_symlink() or str(linker.resolve()) != native:
        linker.unlink(missing_ok=True)
        linker.symlink_to(native)
    environment['DYN_LINKER'] = 'external'
    environment['PATH'] = str(linker.parent)+os.pathsep+environment.get('PATH', '')
    prefixes = list(dict.fromkeys(subprocess.check_output(
        ['pkg-config', '--variable=libdir', package], text=True).strip()
        for package in ('libutf8proc', *TEXT_PACKAGES)))
    environment['DYN_LIBRARY_PATH'] = os.pathsep.join((str(DEPS/'install/lib'), *prefixes))
    links = ['--link', str(Path(sdk)/'usr/lib/libSystem.tbd'), '--link', '-syslibroot', '--link', sdk]
    for path in (str(DEPS/'install/lib'), *prefixes, '@executable_path/deps/install/lib', '@executable_path/../lib'):
        links += ['--link', '-rpath', '--link', path]
    return environment, links


def runtime_objects(compiler):
    stem = 'dynrt_macos_x64' if platform.machine() == 'x86_64' else 'dynrt_macos'
    for directory in (compiler.parent, compiler.parent.parent/'lib/dyn'):
        objects = [directory/(stem+'_shared.o'), directory/(stem+'_support.o')]
        if all(path.is_file() for path in objects):
            return objects
    raise SystemExit('Matching Darwin SDK runtime objects are required: '+stem+'_{shared,support}.o')


def dependencies():
    DEPS.mkdir(parents=True, exist_ok=True)
    with compiler_lock(DEPS/'.native-macos.lock'):
        return build_dependencies()


def build_dependencies():
    if sys.platform != 'darwin':
        raise SystemExit('Darwin native builds require a macOS host')
    if subprocess.run(['pkg-config', '--exists', *PACKAGES, *TEXT_PACKAGES]).returncode:
        raise SystemExit('Install libvterm, Tree-sitter >=0.25, PCRE2 and utf8proc development packages')
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first')
    library = DEPS/'install/lib'
    library.mkdir(parents=True, exist_ok=True)
    environment, links = linker_environment(compiler)
    support = DEPS/'dna-support-macos'
    run([sys.executable, ROOT/'scripts/compile.py', compiler, 'build', ROOT/'src/native/dyn',
         '--shared', '--release', '--emit-object', '--no-link', '--output', support], env=environment)
    symbols = subprocess.check_output(['nm', '-gU', str(support)+'.o'], text=True)
    exports = sorted({line.split()[-1] for line in symbols.splitlines()
                      if line.split() and line.split()[-1].startswith('_dna_')})
    if not exports:
        raise SystemExit('Native support object contains no DNA ABI exports')
    exported = DEPS/'macos-exports.txt'
    exported.write_text('\n'.join(exports)+'\n')
    flags = shlex.split(subprocess.check_output(['pkg-config', '--libs', *PACKAGES], text=True))
    destination = library/'libdna_native.dylib'
    temporary = library/'libdna_native.tmp.dylib'
    run(['cc', '-dynamiclib', '-Wl,-undefined,error', '-Wl,-install_name,@rpath/libdna_native.dylib',
         '-Wl,-exported_symbols_list,'+str(exported), str(support)+'.o', *runtime_objects(compiler),
         *flags, '-o', temporary])
    temporary.replace(destination)
    run([sys.executable, window_builder(compiler), '--output', library/'libdyn_window.dylib'])
    (DEPS/'install/bin').mkdir(parents=True, exist_ok=True)
    (DEPS/'install/share/dna').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT/'languages/registry.toml', DEPS/'install/share/dna/languages.toml')
    shutil.copytree(ROOT/'languages/queries', DEPS/'install/share/dna/queries', dirs_exist_ok=True)
    run([sys.executable, ROOT/'scripts/compile.py', compiler, 'build', ROOT/'installer',
         '--release', '--output', DEPS/'install/bin/dna-language', *links], env=environment)
    return compiler


def build(args):
    if args.backend not in ('auto', 'native'):
        raise SystemExit('macOS uses the native Cocoa backend; select --backend native or auto')
    compiler = dependencies()
    mode = args.mode or ('release' if args.release else 'debug')
    stage = ROOT/'build/native-macos/editor'
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(args.source.resolve(), stage)
    if args.smoke:
        shutil.copytree(ROOT/'tests/editor', stage, dirs_exist_ok=True)
    environment, links = linker_environment(compiler)
    binary = args.output.resolve() if args.output else ROOT/('build/dna-native-'+mode)
    binary.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, ROOT/'scripts/compile.py', compiler, 'build', stage, '--'+mode,
         *(['--no-cache'] if args.no_cache else []), '--output', binary, *links], env=environment)
    run(['otool', '-L', binary])
    print('Built '+str(binary)+'; native Cocoa GUI, no SDL.')
