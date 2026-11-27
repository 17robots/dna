#!/usr/bin/env python3
"""Assemble a relocatable Linux preview with a deterministic archive envelope.

Compiler/system inputs are recorded, not claimed to be bit-reproducible.
No upload, installation, or system package mutation happens here.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'build/packages'
OUT.mkdir(parents=True, exist_ok=True)
PREFIX = ROOT/'build/deps/install'
ENV = dict(os.environ, LD_LIBRARY_PATH=os.pathsep.join(str(path) for path in
           (PREFIX/'lib', ROOT/'build/native-wayland', ROOT/'build/native-gui')))
NAME = 'dna-preview-linux-x86_64'
VERSION = re.search(r'const DnaVersion: (?:str|\[\]const u8) = "([^"]+)"', (ROOT/'src/version.dyn').read_text())[1]
GLIBC = re.compile(r'^(libc|libm|libpthread|librt|libdl|libresolv|libutil)\.so\.')
# Display-server and GL dispatch libraries must match the host's graphics
# driver: NVIDIA's EGL/GLX vendor libraries load them too, and an older bundled
# copy (Ubuntu 24.04's libwayland-client 1.22) breaks them on newer hosts. These
# are shipped only as fallbacks under lib/host/<soname>/, which the launcher
# adds to the search path only for sonames the host's ldconfig cache lacks.
HOST = re.compile(r'^lib(EGL|GL|GLX|GLdispatch|OpenGL|GLESv2|gbm|drm|wayland-[a-z]+|X11|X11-xcb|xcb(-[a-z0-9]+)?|Xau|Xdmcp|Xext|Xrender|Xfixes|Xi|Xrandr|Xcursor|Xss|Xtst)\.so\.')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def needed(path): return re.findall(r'\(NEEDED\).*?\[(.*?)\]', subprocess.check_output(['readelf', '-d', str(path)], text=True))
def host_fallbacks(roots, loaded, libraries):
    # Bundled libraries reachable from the editor without passing through a
    # host display/GL library stay in lib/; the rest (HOST and anything only
    # they need, such as libXdmcp's libbsd) become host fallbacks.
    core=set(); pending=[*loaded, *(name for root in roots for name in needed(root))]
    while pending:
        name=pending.pop()
        if name in core or name not in libraries or HOST.match(name): continue
        core.add(name); pending.extend(needed(libraries[name]))
    return set(libraries)-core
def dependencies(binary):
    dynamic = subprocess.check_output(['readelf', '-d', str(binary)], text=True)
    for needed in re.findall(r'\(NEEDED\).*?\[(.*?)\]', dynamic):
        if '/' in needed: raise SystemExit(f'Nonrelocatable dependency in {binary.name}: {needed}; rebuild with SONAME')
    output = subprocess.check_output(['ldd', str(binary)], env=ENV, text=True)
    if 'not found' in output: raise SystemExit(output)
    for line in output.splitlines():
        match = re.match(r'\s*(\S+) => (/\S+) ', line)
        if match:
            name=match[1]
            if Path(name).name.startswith('ld-linux-'): continue
            if '/' in name: raise SystemExit(f'Unexpected absolute dependency name: {name}')
            if not GLIBC.match(name): yield name, Path(match[2])
with tempfile.TemporaryDirectory(prefix='dna-package-') as temporary:
    tree = Path(temporary)/NAME
    (tree/'bin').mkdir(parents=True); (tree/'lib').mkdir(); (tree/'share/dna').mkdir(parents=True)
    shutil.copy2(ROOT/'build/dna-native-wayland-release', tree/'bin/dna-wayland')
    shutil.copy2(ROOT/'build/dna-native-release', tree/'bin/dna-x11')
    shutil.copy2(PREFIX/'bin/dna-language', tree/'bin/dna-language')
    shutil.copytree(PREFIX/'share/dna', tree/'share/dna', dirs_exist_ok=True)
    for directory in ('themes', 'layouts'):
        shutil.copytree(ROOT/directory, tree/'share/dna'/directory)
    shutil.copy2(ROOT/'config.example.toml', tree/'share/dna/config.example.toml')
    shutil.copytree(ROOT/'packaging/linux/share/applications', tree/'share/applications')
    shutil.copy2(ROOT/'packaging/linux/dna-install-desktop', tree/'dna-install-desktop')
    (tree/'README.md').write_text("""# DNA Linux preview

Run `./dna [file-or-directory]` from this directory, or add this directory to PATH.
Use `./dna --version` or `./dna version` to print the application version.
Keep `bin`, `lib`, and `share` beside the launcher. No Dyn SDK or Python is
required to run the editor. A system monospace font, compatible glibc, and
Linux display/graphics-driver libraries are required. The launcher uses the host's
Wayland, X11 and GL libraries; copies under lib/host are used only where the host
has none (for example `--tui` on a headless machine). The launcher selects Wayland
when WAYLAND_DISPLAY is set, otherwise X11. Both binaries also support --tui.

Run `./dna-install-desktop` to register DNA and DNA (Terminal) in your app
launcher. It writes per-user desktop entries, respecting XDG_DATA_HOME. Run it
again after moving or upgrading this extracted package. Terminal mode uses the
terminal configured by your desktop launcher. No root access is needed.

- `i`: insert; Escape: normal mode; `:write`: save; `:`: command palette.
- Space f: file picker; Space b: buffer picker; Space e: editable explorer.
- Space /: global regex search; `:replace-preview text`: preview replacement
  after a completed search. Applying edits changes buffers; save explicitly.
- Space t: bottom terminal; Escape Escape: terminal normal mode.
- `:themes`, `:layouts`, `:settings`: discovery pickers.
- `:session-save`, `:session-load`, `:recoveries`: workspace persistence.

Copy `share/dna/config.example.toml` to `~/.config/dna/config.toml` to configure
DNA. Place custom themes/layouts in sibling `themes`/`layouts` directories;
examples are under `share/dna/`. `DNA_CONFIG` overrides the configuration path.

`:languages` groups Installed and Available packages. Use i to install, x to
uninstall, u to update, and / to filter. Space marks multiple packages; q (or c) clears
marks. Use gg/Home and G/End for the first/last package, including in visual
mode. Use v then arrows or j/k to select a range. With no marks, u updates all
installed packages. Packages live in ~/.config/dna/languages (or
$XDG_CONFIG_HOME/dna/languages); DNA_LANGUAGE_DIR overrides this location.
Grammar installation additionally needs curl, tar, sha256sum, timeout, awk,
and a C compiler. These developer tools are not included in this archive.

See PLUGINS.md for the experimental process API. The uppercase example lives
in examples/plugins/uppercase. Plugins require explicit loading and permission
review; editor API permissions are not an OS sandbox.

This is an experimental preview: dynamically allocated buffers, 268,435,455 text bytes per buffer,
8 views. LSP clients are included; install language servers separately.
See PRERELEASE.md for known limitations and the validation scope.
Other platform ports are not included. `build-info.json`
records dependencies; SHA256SUMS verifies extracted files. Nothing is installed
system-wide by extracting or running this archive.
""")
    shutil.copytree(ROOT/'examples/plugins/uppercase',tree/'examples/plugins/uppercase',ignore=shutil.ignore_patterns('*.dyncache*','__pycache__'))
    shutil.copy2(ROOT/'PLUGINS.md', tree/'PLUGINS.md')
    shutil.copy2(ROOT/'PRERELEASE.md', tree/'PRERELEASE.md')
    shutil.copy2(ROOT/'LICENSE', tree/'LICENSE')
    shutil.copy2(ROOT/'plugin-catalog.example.json', tree/'plugin-catalog.example.json')
    for example in ('lsp.example.json','plugin-catalog.example.json'):
        shutil.copy2(ROOT/example,tree/'share/dna'/example)
    libraries = {}
    # Text providers are loaded dynamically by the native shaper. Bundle them
    # and their dependencies as well as the ELF-linked window/runtime libraries.
    providers=[]; provider_names=[]
    for library in ('harfbuzz', 'fribidi', 'freetype'):
        path=Path(subprocess.check_output(['cc', '-print-file-name=lib'+library+'.so'], text=True).strip()).resolve()
        if not path.is_file(): raise SystemExit('Missing native text provider: '+library)
        soname=re.search(r'\(SONAME\).*?\[(.*?)\]', subprocess.check_output(['readelf','-d',str(path)], text=True))
        if not soname: raise SystemExit('Missing text provider SONAME: '+str(path))
        libraries[soname[1]]=path
        providers.append(path); provider_names.append(soname[1])

    for binary in (tree/'bin/dna-wayland', tree/'bin/dna-x11', tree/'bin/dna-language', PREFIX/'lib/libdna_native.so', *providers):
        for name, source in dependencies(binary):
            if name in libraries and libraries[name] != source.resolve(): raise SystemExit(f'Conflicting {name}')
            libraries[name] = source.resolve()
    if any('SDL' in name for name in libraries): raise SystemExit('Package contains an SDL dependency')
    libraries['libdna_native.so'] = (PREFIX/'lib/libdna_native.so').resolve()
    # Text providers are dlopened, so they are roots themselves.
    fallbacks=host_fallbacks([tree/'bin/dna-wayland', tree/'bin/dna-x11', tree/'bin/dna-language'], provider_names, libraries)
    if not any(name.startswith('libwayland-client.') for name in fallbacks): raise SystemExit('libwayland-client must be a host fallback')
    inventory=[]
    for name, source in sorted(libraries.items()):
        record={'name':name, 'sha256':sha(source)}
        if name in fallbacks:
            (tree/'lib/host'/name).mkdir(parents=True)
            shutil.copyfile(source, tree/'lib/host'/name/name)
            record['host_fallback']=True
        else:
            shutil.copyfile(source, tree/'lib'/name)
        if shutil.which('pacman'):
            package=subprocess.run(['pacman','-Qqo',str(source)],capture_output=True,text=True)
            if package.returncode == 0:
                owner=package.stdout.strip();record['package']=subprocess.check_output(['pacman','-Q',owner],text=True).strip()
                license_dir=Path('/usr/share/licenses')/owner
                if license_dir.is_dir():shutil.copytree(license_dir,tree/'licenses'/owner,dirs_exist_ok=True)
                # License directories do not always use the package name.
                listing=subprocess.check_output(['pacman','-Ql',owner],text=True)
                for entry in listing.splitlines():
                    _,_,filename=entry.partition(' ')
                    license_file=Path(filename)
                    if filename.startswith('/usr/share/licenses/') and license_file.is_file():
                        target=tree/'licenses/system'/license_file.relative_to('/usr/share/licenses')
                        target.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(license_file,target)
        elif shutil.which('dpkg'):
            # Debian/Ubuntu builds: the owning package and its copyright file.
            package=subprocess.run(['dpkg','-S',str(source)],capture_output=True,text=True)
            if package.returncode == 0:
                owner=package.stdout.split(':',1)[0].strip()
                version=subprocess.run(['dpkg-query','-W','-f=${Version}',owner],capture_output=True,text=True).stdout.strip()
                record['package']=f'{owner} {version}'.strip()
                copyright_file=Path('/usr/share/doc')/owner/'copyright'
                if copyright_file.is_file():
                    target=tree/'licenses'/owner/'copyright'
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(copyright_file,target)
            else:
                # Built from source into /usr/local (tree-sitter on Ubuntu).
                stem=name.split('.so')[0].removeprefix('lib')
                local=Path('/usr/local/share/licenses')/stem
                if local.is_dir():
                    record['package']=stem+' (source build)'
                    shutil.copytree(local,tree/'licenses'/stem,dirs_exist_ok=True)
        inventory.append(record)
    common=Path('/usr/share/licenses/common')
    if common.is_dir():shutil.copytree(common,tree/'licenses/common',dirs_exist_ok=True)
    # This entrypoint works from any cwd and does not require a Dyn SDK.
    launcher='''#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# Display and GL libraries come from the host so they match its graphics
# driver; lib/host/<soname> is used only for sonames the host does not have.
cache=
for ldconfig in "$(command -v ldconfig || true)" /sbin/ldconfig /usr/sbin/ldconfig; do
    if [ -n "$ldconfig" ] && [ -x "$ldconfig" ] && cache=$("$ldconfig" -p); then
        break
    fi
    cache=
done
tab=$(printf '\\t')
path="$root/lib"
for fallback in "$root"/lib/host/*; do
    [ -d "$fallback" ] || continue
    case "$cache" in
        *"$tab${fallback##*/} (libc6,x86-64"*) ;;
        *) path="$path:$fallback" ;;
    esac
done
export LD_LIBRARY_PATH="$path${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
if [ -n "${WAYLAND_DISPLAY:-}" ]; then
    exec "$root/bin/dna-wayland" "$@"
fi
exec "$root/bin/dna-x11" "$@"
'''
    (tree/'dna').write_text(launcher);(tree/'dna').chmod(0o755)
    symbols=''.join(subprocess.check_output(['readelf','--version-info',str(binary)],text=True) for binary in [tree/'bin/dna-wayland',tree/'bin/dna-x11',tree/'bin/dna-language',*sorted(path for path in (tree/'lib').rglob('*') if path.is_file())])
    glibc=max(set(re.findall(r'GLIBC_([0-9]+(?:\.[0-9]+)+)',symbols)),key=lambda v:tuple(map(int,v.split('.'))))
    metadata={'dna':VERSION,'minimum_glibc':glibc,'format':1,'target':'linux-x86_64','dyn':subprocess.check_output([os.environ.get('DYN','dyn'),'--version'],text=True).strip(),'libraries':inventory,'runtime_requirements':['glibc compatible with this build','installed monospace font','Linux desktop display/backend and graphics-driver libraries'],'scope':'Local preview; no publication performed.'}
    (tree/'build-info.json').write_text(json.dumps(metadata,indent=2,sort_keys=True)+'\n')
    records=[]
    for path in sorted(tree.rglob('*')):
        if path.is_file():records.append(f'{sha(path)}  {path.relative_to(tree)}')
    (tree/'SHA256SUMS').write_text('\n'.join(records)+'\n')
    # Relocation check: SDK/repository paths must not be needed to start or exit.
    env=dict(os.environ, PATH='/usr/bin:/bin',HOME=temporary,LD_LIBRARY_PATH=str(tree/'lib'),DYN_EDITOR_SMOKE='1',DNA_RECOVERY='0',DNA_CONFIG=str(Path(temporary)/'missing.toml'),DNA_LANGUAGE_DIR=str(Path(temporary)/'languages'))
    env.pop('DYN_LIBRARY_PATH',None);env.pop('DNA_WORKFLOW_TEST',None)
    subprocess.run([str(tree/'dna')],cwd=temporary,env=env,check=True,timeout=20)
    destination=OUT/(NAME+'.tar.gz')
    with destination.open('wb') as output:
        with gzip.GzipFile(fileobj=output,mode='wb',mtime=0,filename='') as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as archive:
                for path in [tree,*sorted(tree.rglob('*'))]:
                    info=archive.gettarinfo(str(path),str(path.relative_to(tree.parent)))
                    info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0
                    if path.is_file():
                        with path.open('rb') as source:archive.addfile(info,source)
                    else:archive.addfile(info)
    destination.with_suffix(destination.suffix+'.sha256').write_text(f'{sha(destination)}  {destination.name}\n')
    print(destination)
