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
ENV = dict(os.environ, LD_LIBRARY_PATH=str(PREFIX/'lib'))
NAME = 'dna-preview-linux-x86_64'
GLIBC = re.compile(r'^(libc|libm|libpthread|librt|libdl|libresolv|libutil)\.so\.')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
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
    shutil.copy2(ROOT/'build/dna-release', tree/'bin/dna')
    shutil.copy2(PREFIX/'bin/dna-language', tree/'bin/dna-language')
    shutil.copytree(PREFIX/'share/dna', tree/'share/dna', dirs_exist_ok=True)
    for directory in ('themes', 'layouts'):
        shutil.copytree(ROOT/directory, tree/'share/dna'/directory)
    shutil.copy2(ROOT/'config.example.toml', tree/'share/dna/config.example.toml')
    (tree/'README.md').write_text("""# DNA Linux preview

Run `./dna [file]` from this directory, or add this directory to PATH.
Keep `bin`, `lib`, and `share` beside the launcher. No Dyn SDK or Python is
required to run the editor. A system monospace font, compatible glibc, and
Linux display/graphics-driver libraries are required.

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

`:languages` lists syntax packages; `:language-install name` installs one.
Grammar installation additionally needs curl, tar, sha256sum, timeout, awk,
and a C compiler. These developer tools are not included in this archive.

See PLUGINS.md for the experimental process API. The uppercase example lives
in examples/plugins/uppercase. Plugins require explicit loading and permission
review; editor API permissions are not an OS sandbox.

This is a local prototype build: 16 buffers, 1,048,575 text bytes per buffer,
8 views. LSP clients are included; install language servers separately.
Other platform ports are not included. `build-info.json`
records dependencies; SHA256SUMS verifies extracted files. Nothing is installed
system-wide by extracting or running this archive.
""")
    shutil.copytree(ROOT/'examples/plugins/uppercase',tree/'examples/plugins/uppercase',ignore=shutil.ignore_patterns('*.dyncache*','__pycache__'))
    shutil.copy2(ROOT/'PLUGINS.md', tree/'PLUGINS.md')
    shutil.copy2(ROOT/'LICENSE', tree/'LICENSE')
    shutil.copy2(ROOT/'plugin-catalog.example.json', tree/'plugin-catalog.example.json')
    for example in ('lsp.example.json','plugin-catalog.example.json'):
        shutil.copy2(ROOT/example,tree/'share/dna'/example)
    libraries = {}
    for binary in (tree/'bin/dna', tree/'bin/dna-language', PREFIX/'lib/libdna_native.so'):
        for name, source in dependencies(binary):
            if name in libraries and libraries[name] != source.resolve(): raise SystemExit(f'Conflicting {name}')
            libraries[name] = source.resolve()
    libraries['libdna_native.so'] = (PREFIX/'lib/libdna_native.so').resolve()
    inventory=[]
    for name, source in sorted(libraries.items()):
        shutil.copyfile(source, tree/'lib'/name)
        record={'name':name, 'sha256':sha(source)}
        if shutil.which('pacman'):
            package=subprocess.run(['pacman','-Qqo',str(source)],capture_output=True,text=True)
            if package.returncode == 0:
                owner=package.stdout.strip();record['package']=subprocess.check_output(['pacman','-Q',owner],text=True).strip()
                license_dir=Path('/usr/share/licenses')/owner
                if license_dir.is_dir():shutil.copytree(license_dir,tree/'licenses'/owner,dirs_exist_ok=True)
                # License directories do not always use the package name (SDL3).
                listing=subprocess.check_output(['pacman','-Ql',owner],text=True)
                for entry in listing.splitlines():
                    _,_,filename=entry.partition(' ')
                    license_file=Path(filename)
                    if filename.startswith('/usr/share/licenses/') and license_file.is_file():
                        target=tree/'licenses/system'/license_file.relative_to('/usr/share/licenses')
                        target.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(license_file,target)
        inventory.append(record)
    common=Path('/usr/share/licenses/common')
    if common.is_dir():shutil.copytree(common,tree/'licenses/common',dirs_exist_ok=True)
    sdl_license=ROOT/'build/deps/SDL3_ttf-3.2.2/LICENSE.txt'
    if not sdl_license.exists():raise SystemExit('Missing SDL_ttf license; rebuild dependencies from pinned source')
    (tree/'licenses/SDL_ttf').mkdir(parents=True,exist_ok=True);shutil.copy2(sdl_license,tree/'licenses/SDL_ttf/LICENSE.txt')
    # This entrypoint works from any cwd and does not require a Dyn SDK.
    launcher='''#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export LD_LIBRARY_PATH="$root/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$root/bin/dna" "$@"
'''
    (tree/'dna').write_text(launcher);(tree/'dna').chmod(0o755)
    symbols=''.join(subprocess.check_output(['readelf','--version-info',str(binary)],text=True) for binary in [tree/'bin/dna',tree/'bin/dna-language',*sorted((tree/'lib').iterdir())])
    glibc=max(set(re.findall(r'GLIBC_([0-9]+(?:\.[0-9]+)+)',symbols)),key=lambda v:tuple(map(int,v.split('.'))))
    metadata={'minimum_glibc':glibc,'format':1,'target':'linux-x86_64','dyn':subprocess.check_output([os.environ.get('DYN','dyn'),'--version'],text=True).strip(),'libraries':inventory,'runtime_requirements':['glibc compatible with this build','installed monospace font','Linux desktop display/backend and graphics-driver libraries'],'scope':'Local preview; no publication performed.'}
    (tree/'build-info.json').write_text(json.dumps(metadata,indent=2,sort_keys=True)+'\n')
    records=[]
    for path in sorted(tree.rglob('*')):
        if path.is_file():records.append(f'{sha(path)}  {path.relative_to(tree)}')
    (tree/'SHA256SUMS').write_text('\n'.join(records)+'\n')
    # Relocation check: SDK/repository paths must not be needed to start or exit.
    env=dict(PATH='/usr/bin:/bin',HOME=temporary,LD_LIBRARY_PATH=str(tree/'lib'),SDL_VIDEODRIVER='dummy',DYN_EDITOR_SMOKE='1',DNA_RECOVERY='0',DNA_CONFIG=str(Path(temporary)/'missing.toml'),DNA_LANGUAGE_DIR=str(Path(temporary)/'languages'))
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
