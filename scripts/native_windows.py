"""Native Windows DLL/editor build using the MSYS2 UCRT64 providers."""
import hashlib
import json
import mmap
import struct
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

from build_limits import compiler_lock
from dyn_path import real_dyn
from sdk_check import window_builder
from sdk_compat import environment as sdk_environment

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / 'build/deps'
PACKAGES = ('vterm', 'tree-sitter >= 0.25', 'libpcre2-8', 'libutf8proc', 'harfbuzz', 'fribidi', 'freetype2')
IMPORTS = ('kernel32', 'advapi32', 'ucrt', 'vterm', 'tree-sitter', 'pcre2-8', 'utf8proc')


def run(command, **kwargs):
    return subprocess.run([str(part) for part in command], check=True, **kwargs)


def prefix():
    return Path(os.environ.get('DNA_WINDOWS_PREFIX', 'C:/msys64/ucrt64')).resolve()


def tool(name):
    candidate = prefix() / 'bin' / (name + '.exe')
    if not candidate.is_file() and name == 'pkg-config':
        candidate = prefix() / 'bin/pkgconf.exe'
    if not candidate.is_file():
        raise SystemExit('Native Windows build requires ' + str(candidate))
    return candidate


def environment(compiler):
    result = sdk_environment(compiler)
    result['PATH'] = os.pathsep.join((str(DEPS / 'install/bin'), str(DEPS / 'install/lib'),
        str(prefix() / 'bin'), result.get('PATH', '')))
    result['DNA_WINDOWS_PREFIX'] = str(prefix())
    result['CC'] = shlex.quote(tool('gcc').as_posix())
    result['PKG_CONFIG'] = str(tool('pkg-config'))
    result['DYN_LIBRARY_PATH'] = os.pathsep.join((str(DEPS / 'install/lib'), str(prefix() / 'lib')))
    return result


def stage_bridge(destination):
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(ROOT / 'src/native/dyn', destination)
    for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
        shutil.copytree(ROOT / 'src' / module, destination / module)
    (destination / 'windows_providers.dyn').write_text('#target(kernel: windows)\n#link("utf8proc")\n#link("tree-sitter")\n', encoding='utf-8')


def cross_objects():
    """Compile every real support service together; never report runtime proof."""
    compiler = real_dyn()
    if compiler is None:
        raise SystemExit('Install the pinned Dyn SDK first')
    stage = ROOT / 'build/native-windows/cross-bridge'
    stage_bridge(stage)
    for target in ('x86_64-windows', 'aarch64-windows'):
        for mode in ('debug', 'release'):
            run([sys.executable, ROOT / 'scripts/compile.py', compiler, 'build', stage,
                '--shared', '--' + mode, '--target', target, '--emit-object', '--no-link',
                '--output', stage.parent / (target + '-' + mode)], env=sdk_environment(compiler))
            print('PASS complete Windows service objects: ' + target + ' ' + mode, flush=True)
    return compiler


def import_libraries(destination):
    """Expose only native import libraries, with names Dyn's linker resolves."""
    kits = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Windows Kits/10/Lib'
    for name in IMPORTS:
        candidates = [prefix() / 'lib' / ('lib' + name + '.dll.a')]
        if name in ('kernel32', 'advapi32', 'ucrt'):
            folder = 'ucrt' if name == 'ucrt' else 'um'
            sdk = sorted(kits.glob('*/' + folder + '/x64/' + name + '.lib'), reverse=True)
            # Dyn links without the MinGW CRT startup objects. The SDK UCRT
            # library supplies conveniences such as atexit that MinGW's bare
            # DLL import archive expects its own startup libraries to provide.
            if name == 'ucrt':
                candidates = sdk + candidates
            else:
                candidates += sdk
            candidates += [prefix() / 'lib' / ('lib' + name + '.a')]
        source = next((path for path in candidates if path.is_file()), None)
        if source is None:
            raise SystemExit('Missing native import library: ' + name)
        shutil.copyfile(source, destination / ('lib' + name + '.dll.a'))


def dll_imports(path):
    listing = subprocess.check_output([str(tool('objdump')), '-p', str(path)], text=True, encoding='utf-8', errors='replace')
    return re.findall(r'^\s*DLL Name:\s*(\S+)\s*$', listing, re.MULTILINE)


def pe_interface(path):
    """Read native PE imports/exports by name or ordinal without loading code."""
    path = Path(path)
    with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as image:
        def unpack(form, offset):
            if offset < 0 or offset + struct.calcsize(form) > len(image):
                raise RuntimeError('Truncated PE record: ' + str(path))
            return struct.unpack_from(form, image, offset)
        if image[:2] != b'MZ':
            raise RuntimeError('Not a PE image: ' + str(path))
        header = unpack('<I', 60)[0]
        if image[header:header+4] != b'PE\0\0':
            raise RuntimeError('Invalid PE signature: ' + str(path))
        sections = unpack('<H', header+6)[0]
        optional_size = unpack('<H', header+20)[0]
        optional = header+24
        magic = unpack('<H', optional)[0]
        if magic not in (0x10b, 0x20b):
            raise RuntimeError('Unsupported PE optional header: ' + str(path))
        stride, ordinal_flag = (8, 1 << 63) if magic == 0x20b else (4, 1 << 31)
        directories = optional + (112 if magic == 0x20b else 96)
        count = unpack('<I', directories-4)[0]
        headers_size = unpack('<I', optional+60)[0]
        mappings = []
        for index in range(sections):
            section = optional+optional_size+40*index
            virtual_size, address, raw_size, raw = unpack('<IIII', section+8)
            mappings.append((address, max(virtual_size, raw_size), raw, raw_size))
        def offset(rva):
            if rva < headers_size and rva < len(image):
                return rva
            for address, size, raw, raw_size in mappings:
                if address <= rva < address+size and rva-address < raw_size:
                    result = raw+rva-address
                    if result < len(image):
                        return result
            raise RuntimeError('Unmapped PE RVA ' + hex(rva) + ': ' + str(path))
        def text(rva):
            first = offset(rva)
            end = image.find(b'\0', first, min(len(image), first+4096))
            if end < 0:
                raise RuntimeError('Unterminated PE name: ' + str(path))
            return image[first:end].decode('ascii')
        def directory(index):
            return unpack('<II', directories+index*8) if index < count else (0, 0)
        imports = {}
        import_rva, _ = directory(1)
        if import_rva:
            first = offset(import_rva)
            for index in range(4096):
                original, stamp, chain, name, thunk = unpack('<IIIII', first+20*index)
                if not (original or stamp or chain or name or thunk):
                    break
                imported = imports.setdefault(text(name), set())
                table = offset(original or thunk)
                for entry in range(131072):
                    value = unpack('<Q' if stride == 8 else '<I', table+entry*stride)[0]
                    if value == 0:
                        break
                    imported.add(value & 65535 if value & ordinal_flag else text(value+2))
                else:
                    raise RuntimeError('Unbounded PE import table: ' + str(path))
            else:
                raise RuntimeError('Unbounded PE dependency table: ' + str(path))
        exports, forwarders = set(), {}
        export_rva, export_size = directory(0)
        if export_rva:
            record = unpack('<IIHHIIIIIII', offset(export_rva))
            base, functions, names, addresses, name_table, ordinal_table = record[5:]
            if functions > 1048576 or names > 1048576:
                raise RuntimeError('Invalid PE export count: ' + str(path))
            values = [unpack('<I', offset(addresses)+4*index)[0] for index in range(functions)]
            for index, address in enumerate(values):
                if address:
                    exports.add(base+index)
                    if export_rva <= address < export_rva+export_size:
                        forwarders[base+index] = text(address)
            for index in range(names):
                name = text(unpack('<I', offset(name_table)+4*index)[0])
                ordinal = unpack('<H', offset(ordinal_table)+2*index)[0]
                if ordinal >= functions or not values[ordinal]:
                    raise RuntimeError('Invalid PE named export: ' + str(path))
                exports.add(name)
                if base+ordinal in forwarders:
                    forwarders[name] = forwarders[base+ordinal]
        return {'imports': imports, 'exports': exports, 'forwarders': forwarders}


def audit_runtime(roots):
    """Report exact dependency paths and unresolved procedures before LoadLibrary."""
    roots = [Path(path).resolve() for path in roots]
    directories = list(dict.fromkeys(path.parent for path in roots))
    system = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32'
    cache, errors, visited = {}, [], set()
    def contract(name):
        return name.lower().startswith(('api-ms-win-', 'ext-ms-win-'))
    def locate(name, owner):
        for folder in dict.fromkeys((*directories, owner.parent, system)):
            candidate = folder / name
            if candidate.is_file():
                return candidate.resolve()
        return None
    def interface(path):
        if path not in cache:
            cache[path] = pe_interface(path)
        return cache[path]
    def require(owner, dependency, symbol, chain=()):
        if contract(dependency):
            return
        target = locate(dependency, owner)
        if target is None:
            errors.append(str(owner) + ' imports ' + dependency + '!' + str(symbol) + '; selected DLL: MISSING')
            return
        identity = (target, symbol)
        if identity in chain:
            errors.append('PE forwarder cycle: ' + str(identity))
            return
        view = interface(target)
        if symbol not in view['exports']:
            errors.append(str(owner) + ' imports ' + dependency + '!' + str(symbol) + '; selected DLL: ' + str(target) + '; procedure NOT EXPORTED')
            return
        forwarded = view['forwarders'].get(symbol)
        if forwarded:
            library, name = forwarded.rsplit('.', 1)
            require(target, library if library.lower().endswith('.dll') else library+'.dll', int(name[1:]) if name.startswith('#') else name, (*chain, identity))
    pending = list(roots)
    while pending:
        owner = pending.pop()
        if owner in visited:
            continue
        visited.add(owner)
        view = interface(owner)
        print('PE audit: ' + str(owner) + ' (' + str(sum(map(len, view['imports'].values()))) + ' imports)', flush=True)
        for dependency, symbols in sorted(view['imports'].items()):
            if contract(dependency):
                continue
            target = locate(dependency, owner)
            print('  ' + dependency + ' -> ' + (str(target) if target else 'MISSING'), flush=True)
            if target is not None:
                pending.append(target)
            for symbol in sorted(symbols, key=str):
                require(owner, dependency, symbol)
    if errors:
        for error in errors[:64]:
            print('PE IMPORT ERROR: ' + error, file=sys.stderr, flush=True)
        raise RuntimeError('PE import audit found ' + str(len(errors)) + ' unresolved procedures/dependencies')
    print('PASS PE import/export audit: ' + str(len(visited)) + ' images', flush=True)


def snapshot_runtime(roots, destination, tools=False):
    """Copy the real PE import closure plus explicitly loaded text providers."""
    destination.mkdir(parents=True, exist_ok=True)
    from conpty import install as install_conpty
    companions = install_conpty(destination)
    providers = ('libharfbuzz-0.dll', 'libfribidi-0.dll', 'libfreetype-6.dll')
    pending = [Path(path) for path in roots] + [path for path in companions if path.suffix.lower() in ('.dll', '.exe')]
    if tools:
        helper = DEPS / 'install/bin/dna-language.exe'
        if not helper.is_file():
            raise SystemExit('Missing native language helper: ' + str(helper))
        pending.append(helper)
        shutil.copytree(DEPS / 'install/share/dna', destination / 'share/dna', dirs_exist_ok=True)
    for name in providers:
        path = prefix() / 'bin' / name
        if not path.is_file():
            raise SystemExit('Missing runtime text provider: ' + str(path))
        pending.append(path)
    # Mesa's WGL dispatcher may load its Gallium provider dynamically.
    if (prefix() / 'bin/opengl32.dll').is_file():
        pending += list((prefix() / 'bin').glob('*gallium*.dll'))
        pending += list((prefix() / 'bin').glob('*glapi*.dll'))
    available = {path.name.lower(): path for directory in (destination, DEPS / 'install/lib', prefix() / 'bin')
                 for path in directory.glob('*.dll')}
    system = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32'
    visited = {}
    while pending:
        source = pending.pop()
        key = source.name.lower()
        if key in visited:
            continue
        if key.startswith(('msys-', 'cygwin', 'sdl')):
            raise SystemExit('Non-native or SDL runtime dependency: ' + source.name)
        visited[key] = source
        for name in dll_imports(source):
            imported = available.get(name.lower())
            if imported is not None:
                pending.append(imported)
            elif not name.lower().startswith(('api-ms-win-', 'ext-ms-win-')) and not (system / name).is_file():
                raise SystemExit('Unresolved runtime DLL ' + name + ' imported by ' + source.name)
    manifest = []
    for source in sorted(visited.values(), key=lambda path: path.name.lower()):
        target = destination / source.name
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
        manifest.append({'name': source.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    (destination / 'dna-runtime.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    captured = [destination / item['name'] for item in manifest]
    audit_runtime(captured)
    return captured


def dependencies():
    if os.name != 'nt':
        raise SystemExit('Full native Windows builds require a Windows host; use cross_objects() for object checks')
    DEPS.mkdir(parents=True, exist_ok=True)
    with compiler_lock(DEPS / '.native-windows.lock'):
        compiler = real_dyn()
        if compiler is None:
            raise SystemExit('Install the pinned Dyn SDK first')
        for name in ('gcc', 'objdump', 'pkg-config'):
            tool(name)
        triple = subprocess.check_output([str(tool('gcc')), '-dumpmachine'], text=True).strip()
        if triple != 'x86_64-w64-mingw32':
            raise SystemExit('Native Windows build currently requires the MSYS2 UCRT64 x64 toolchain: ' + triple)
        env = environment(compiler)
        run([tool('pkg-config'), '--exists', *PACKAGES], env=env)
        library = DEPS / 'install/lib'
        binary = DEPS / 'install/bin'
        library.mkdir(parents=True, exist_ok=True)
        binary.mkdir(parents=True, exist_ok=True)
        import_libraries(library)
        bridge = ROOT / 'build/native-windows/bridge'
        stage_bridge(bridge)
        support = library / 'dna_native.dll'
        run([sys.executable, ROOT / 'scripts/compile.py', compiler, 'build', bridge,
            '--shared', '--release', '--output', support], env=env)
        generated_import = support.with_name(support.name + '.a')
        if not generated_import.is_file():
            raise SystemExit('Dyn did not generate the Windows support import library: ' + str(generated_import))
        shutil.copyfile(generated_import, library / 'libdna_native.dll.a')
        window = library / 'dyn_window.dll'
        run([sys.executable, window_builder(compiler), '--output', window], env=env)
        if not (library / 'libdyn_window.dll.a').is_file():
            raise SystemExit('Native Win32 window import library was not generated')
        snapshot_runtime((support, window), library)
        snapshot_runtime((support, window), binary)
        data = DEPS / 'install/share/dna'
        data.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'languages/registry.toml', data / 'languages.toml')
        shutil.copytree(ROOT / 'languages/queries', data / 'queries', dirs_exist_ok=True)
        installer = ROOT / 'build/native-windows/installer'
        if installer.exists():
            shutil.rmtree(installer)
        shutil.copytree(ROOT / 'installer', installer)
        for module in ('filesystem', 'host', 'cstring', 'owned_arena'):
            shutil.copytree(ROOT / 'src' / module, installer / module)
        run([sys.executable, ROOT / 'scripts/compile.py', compiler, 'build', installer,
            '--release', '--output', binary / 'dna-language.exe'], env=env)
        print('Built native Windows support/window DLLs and captured runtime dependencies.', flush=True)
        return compiler


def build(args):
    if args.backend not in ('auto', 'native'):
        raise SystemExit('Windows uses the native Win32 backend; select --backend native or auto')
    compiler = dependencies()
    mode = args.mode or ('release' if args.release else 'debug')
    stage = ROOT / ('build/native-windows/editor-' + mode)
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(args.source.resolve(), stage)
    if args.smoke:
        shutil.copytree(ROOT / 'tests/editor', stage, dirs_exist_ok=True)
    binary = args.output.resolve() if args.output else ROOT / ('build/dna-native-' + mode + '.exe')
    binary.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, ROOT / 'scripts/compile.py', compiler, 'build', stage, '--' + mode,
        *(['--no-cache'] if args.no_cache else []), '--output', binary], env=environment(compiler))
    snapshot_runtime((binary, DEPS / 'install/lib/dna_native.dll', DEPS / 'install/lib/dyn_window.dll'), binary.parent, tools=True)
    print('Built ' + str(binary) + '; native Win32 GUI with adjacent runtime DLLs, no SDL.', flush=True)
