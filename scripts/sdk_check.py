"""Check SDK capabilities required by the current development UI."""
import os
from pathlib import Path


def require_ui_sdk(compiler, environment=None):
    """Fail before building the editor with an older bundled SDK."""
    environment = os.environ if environment is None else environment
    compiler = Path(compiler).resolve()
    roots = []
    if environment.get('DYN_SDK'):
        roots.append(Path(environment['DYN_SDK']).resolve())
    roots.extend((compiler.parent.parent / 'compiler', compiler.parent.parent))
    candidates = [root / 'std/ui/box' for root in roots]
    candidates.append(compiler.parent.parent / 'share/dyn/ui/box')
    if any(candidate.is_dir() for candidate in candidates):
        return
    raise SystemExit(
        'Current DNA UI requires Dyn preview.28 or newer containing std/ui/box. '
        'The published preview.27 SDK does not contain it.\n'
        'Select the pinned SDK with: mise install && mise exec -- just run\n'
        'For a source SDK, select the matching development compiler and SDK:\n'
        'DYN="$PWD/../dyn/compiler/build/dyn-release" '
        'DYN_SDK="$PWD/../dyn/compiler" just run\n'
        'Build that compiler first with: (cd ../dyn/compiler && just release)')


def window_builder(compiler):
    """Locate the native window builder in source and installed SDK layouts."""
    compiler = Path(compiler).resolve()
    if os.environ.get('DYN_SDK'):
        roots = [Path(os.environ['DYN_SDK']).resolve()]
    else:
        roots = [compiler.parent.parent, compiler.parent.parent / 'share/dyn']
    for root in roots:
        builder = root / 'vendor/window/native/build.py'
        if builder.is_file():
            return builder
    raise SystemExit('Dyn SDK is missing vendor/window/native/build.py; '
                     'install preview.28 or set DYN_SDK to a matching checkout.')
