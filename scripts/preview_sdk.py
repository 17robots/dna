#!/usr/bin/env python3
"""Build and open DNA with the selected Dyn SDK and isolated settings."""
import argparse
import os
import shlex
from pathlib import Path
import subprocess

from dyn_path import real_dyn

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', nargs='?', type=Path, default=ROOT / 'examples/sdk-preview/main.dyn')
    args = parser.parse_args()
    source = args.file.resolve()
    if not source.is_file():
        parser.error(f'file does not exist: {source}')
    compiler = real_dyn()
    if compiler is None:
        parser.error('install the pinned Dyn SDK with mise install, or set DYN explicitly')
    explicit_sdk = os.environ.get('DYN_SDK')
    sdk = Path(explicit_sdk).resolve() if explicit_sdk else None
    if sdk is not None and not (sdk / 'std').is_dir():
        parser.error('DYN_SDK must point to a source SDK containing std')
    if sdk is None:
        source_sdk = compiler.parent.parent
        if (source_sdk / 'std').is_dir():
            sdk = source_sdk
        elif not (source_sdk / 'share/dyn/mem').is_dir():
            parser.error('cannot locate the selected compiler SDK; set DYN_SDK explicitly')
    preview = ROOT / 'build/sdk-preview'
    preview.mkdir(parents=True, exist_ok=True)
    config = preview / 'config.toml'
    if not config.exists():
        config.write_text('font_size = 18\nreduced_motion = true\nrelative_numbers = false\n')
    environment = dict(os.environ, DYN=str(compiler),
                       DYN_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'),
                       LD_LIBRARY_PATH=str(ROOT / 'build/deps/install/lib'),
                       DNA_CONFIG=str(config), DNA_DEFAULT_SERVERS='0',
                       DNA_DYN_LSP=shlex.join([str(compiler), 'lsp']),
                       DNA_RECOVERY='0', XDG_CONFIG_HOME=str(preview / 'config'),
                       XDG_STATE_HOME=str(preview / 'state'))
    if sdk is not None:
        environment['DYN_SDK'] = str(sdk)
    else:
        environment.pop('DYN_SDK', None)
    # Keep this a real desktop preview, independent of headless test settings.
    environment.pop('SDL_VIDEODRIVER', None)
    environment.pop('LD_PRELOAD', None)
    environment.pop('DYN_EDITOR_SMOKE', None)
    grammar = ROOT / 'build/test-languages/dyn/parser.so'
    if grammar.is_file():
        environment['DNA_LANGUAGE_DIR'] = str(grammar.parents[1])
    subprocess.run(['just', 'build', 'release'], cwd=ROOT, env=environment, check=True)
    return subprocess.call([str(ROOT / 'build/dna-release'), '--gui', str(source)],
                           cwd=ROOT, env=environment)


if __name__ == '__main__':
    raise SystemExit(main())
