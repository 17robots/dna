#!/usr/bin/env python3
"""List or delete one-off investigation output under build/.

Keeps everything the build, tests and packaging use: names referenced from
scripts/, tests/, justfile or .github/, editor binaries (dna-*), shared
objects, and caches. Everything else at the top of build/ (probe and
investigation directories, logs, diffs, captured smaps) is scratch.
Dry run by default; pass --delete to remove it.
"""
import argparse
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'build'
SCRATCH_SUFFIXES = {'.log', '.diff', '.txt', '.smaps', '.py', '.json', '.stderr', '.c', '.dyn'}


def referenced():
    names = set()
    sources = [ROOT/'justfile', *(ROOT/'scripts').rglob('*.py'), *(ROOT/'tests').rglob('*.py'), *(ROOT/'.github').rglob('*.yml')]
    for source in sources:
        try:
            text = source.read_text(errors='replace')
        except OSError:
            continue
        for match in re.finditer(r"build['\"]?\s*[/,]\s*f?['\"]?([A-Za-z0-9_.{}-]+)", text):
            names.add(match.group(1))
    return names


def kept(path, names):
    name = path.name
    if name.startswith('.') or name.startswith('dna-') and path.is_file():
        return True
    if path.suffix in ('.so', '.o') or name.endswith('.dyncache') or name.endswith('.dyncache.files'):
        return True
    for wanted in names:
        if '{' in wanted:
            prefix = wanted.split('{')[0]
            if prefix and name.startswith(prefix):
                return True
        elif name == wanted or name == wanted.rstrip('-') or (wanted.endswith('-') and name.startswith(wanted)):
            return True
    if path.is_file() and path.suffix not in SCRATCH_SUFFIXES:
        return True
    return False


def size(path):
    if path.is_file() or path.is_symlink():
        return path.lstat().st_size
    return sum(item.lstat().st_size for item in path.rglob('*') if item.is_file() and not item.is_symlink())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--delete', action='store_true', help='remove the listed scratch entries')
    arguments = parser.parse_args()
    if not BUILD.is_dir():
        return
    names = referenced()
    scratch = sorted(path for path in BUILD.iterdir() if not kept(path, names))
    total = 0
    for path in scratch:
        bytes_used = size(path)
        total += bytes_used
        print(f'{bytes_used / 1048576:9.1f} MiB  {path.relative_to(ROOT)}{"/" if path.is_dir() else ""}')
    print(f'{total / 1048576:9.1f} MiB  in {len(scratch)} scratch entries')
    if not arguments.delete:
        print('Dry run. Run `just clean-scratch --delete` to remove them.')
        return
    for path in scratch:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    print('Removed.')


main()
