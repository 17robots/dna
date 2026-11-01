#!/usr/bin/env python3
"""Install a pinned, verified Microsoft app-local ConPTY bundle."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import struct
import tempfile
import time
import urllib.request
import zipfile

from build_limits import compiler_lock

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'build/deps/downloads'
VERSION = '1.25.260930003'
TAG = 'v1.25.2733.0'
PACKAGE = 'Microsoft.Windows.Console.ConPTY.' + VERSION + '.nupkg'
URL = 'https://github.com/microsoft/terminal/releases/download/' + TAG + '/' + PACKAGE
SHA256 = '6d6f8b008c655d814c498d8205d4012dcd4d0b6dfc1096461d0a185d1e3caf03'
SIZE = 1750533
LICENSES = (
    ('LICENSE', 'conpty-LICENSE.txt', 1116, '5d177f23ecfeb0ea8e050b6a5a16355e1ae9a0b286436ca8f83ed08b3795be6b'),
    ('NOTICE.md', 'conpty-NOTICE.md', 23176, 'e7fbaadee6ab20c28b87730a510ee5f5815d8fb4bd88d1d54d282dc2a74c0726'),
)


def _read_verified(path, size, digest):
    try:
        with path.open('rb') as stream:
            data = stream.read(size + 1)
    except FileNotFoundError:
        return None
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        return None
    return data


def _publish(path, data):
    if _read_verified(path, len(data), hashlib.sha256(data).hexdigest()) is not None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _download(url, path, size, digest):
    data = _read_verified(path, size, digest)
    if data is not None:
        return data
    deadline = time.monotonic() + 90
    request = urllib.request.Request(url, headers={'User-Agent': 'DNA-native-build'})
    chunks, total = [], 0
    with urllib.request.urlopen(request, timeout=30) as response:
        declared = response.headers.get('Content-Length')
        if declared is not None and int(declared) != size:
            raise RuntimeError('Unexpected ConPTY download size: ' + url)
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('ConPTY download deadline: ' + url)
            block = response.read(min(65536, size + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
            if total > size:
                raise RuntimeError('ConPTY download exceeds pinned size: ' + url)
    data = b''.join(chunks)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError('ConPTY download does not match pinned SHA-256: ' + url)
    _publish(path, data)
    return data


def _machine(data, expected, name):
    if len(data) < 64 or data[:2] != b'MZ':
        raise RuntimeError('ConPTY package member is not a PE image: ' + name)
    offset = struct.unpack_from('<I', data, 60)[0]
    if offset + 6 > len(data) or data[offset:offset + 4] != b'PE\0\0':
        raise RuntimeError('ConPTY package member has an invalid PE header: ' + name)
    if struct.unpack_from('<H', data, offset + 4)[0] != expected:
        raise RuntimeError('ConPTY package architecture mismatch: ' + name)


def install(destination: Path):
    """Publish the matching DLL, console host, licenses and a source manifest.

    OpenConsole.exe intentionally sits next to conpty.dll: the pinned DLL checks
    that app-local path before architecture subdirectories or the inbox host.
    Existing identical files stay untouched, including DLLs already loaded.
    """
    destination = Path(destination).resolve()
    architecture = 'arm64' if platform.machine().lower() in ('arm64', 'aarch64') else 'x64'
    machine = 0xAA64 if architecture == 'arm64' else 0x8664
    CACHE.mkdir(parents=True, exist_ok=True)
    with compiler_lock(CACHE / '.conpty.lock'):
        package = _download(URL, CACHE / PACKAGE, SIZE, SHA256)
        selected = {
            'runtimes/win-' + architecture + '/native/conpty.dll': 'conpty.dll',
            'build/native/runtimes/' + architecture + '/OpenConsole.exe': 'OpenConsole.exe',
        }
        files = {}
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            for member, name in selected.items():
                matches = [entry for entry in archive.infolist() if entry.filename == member]
                if len(matches) != 1 or matches[0].is_dir() or not 0 < matches[0].file_size <= 4194304:
                    raise RuntimeError('Unexpected ConPTY archive member: ' + member)
                data = archive.read(matches[0])
                _machine(data, machine, member)
                files[name] = data
        license_sources = []
        for source, name, size, digest in LICENSES:
            url = 'https://raw.githubusercontent.com/microsoft/terminal/' + TAG + '/' + source
            files[name] = _download(url, CACHE / ('conpty-' + TAG + '-' + name), size, digest)
            license_sources.append({'name': name, 'url': url, 'sha256': digest})
        for name, data in files.items():
            _publish(destination / name, data)
        manifest = {'version': VERSION, 'architecture': architecture, 'url': URL, 'sha256': SHA256,
            'licenses': license_sources,
            'files': [{'name': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                      for name, data in sorted(files.items())]}
        _publish(destination / 'conpty-package.json', (json.dumps(manifest, indent=2) + '\n').encode('utf-8'))
    return [destination / name for name in (*files, 'conpty-package.json')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for path in install(args.output):
        print(path)


if __name__ == '__main__':
    main()
