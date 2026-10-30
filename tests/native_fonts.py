#!/usr/bin/env python3
"""Real font C ABI over std/font/system; no Fontconfig aliases/configuration.

Creates supported TrueType fixtures under an isolated initial HOME. Collections
and CFF faces are intentionally unsupported until std/font supports them.
Run after scripts/deps.py rebuilds the native bridge.
"""
import ctypes as c
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'build/deps/install/lib/libdna_native.so'
FAMILY = 'DNA Native Font Fixture 94813'
PROPORTIONAL = 'DNA Proportional Fixture 94813'
u16 = lambda n: struct.pack('>H', n)
u32 = lambda n: struct.pack('>I', n)


def face(family, weight=400, mono=True):
    head = bytearray(54)
    head[12:16] = u32(0x5f0f3cf5)
    head[18:20] = u16(1000)
    hhea = bytearray(36)
    hhea[4:8] = struct.pack('>hh', 1000, -200)
    hhea[34:36] = u16(1)
    cmap = (u16(0) + u16(1) + u16(3) + u16(1) + u32(12)
            + struct.pack('>12H', 4, 24, 0, 2, 2, 0, 0, 65535, 0, 65535, 1, 0))
    records, strings = b'', b''
    for name_id, value in ((16, family), (17, 'Regular' if weight == 400 else 'Bold')):
        raw = value.encode('utf-16-be')
        records += struct.pack('>6H', 3, 1, 0x409, name_id, len(raw), len(strings))
        strings += raw
    os2 = bytearray(64)
    os2[4:6] = u16(weight)
    tables = {
        b'head': head, b'hhea': hhea, b'maxp': u32(65536) + u16(1),
        b'hmtx': u16(600) + u16(0), b'loca': bytes(4), b'glyf': b'', b'cmap': cmap,
        b'name': u16(0) + u16(2) + u16(30) + records + strings,
        b'OS/2': os2, b'post': bytes(12) + u32(int(mono)),
    }
    offset = 12 + 16 * len(tables)
    directory, body = b'', b''
    for tag, data in tables.items():
        directory += tag + u32(0) + u32(offset) + u32(len(data))
        body += data
        offset += len(data)
    return u32(65536) + u16(len(tables)) + bytes(6) + directory + body


def probe(home):
    lib = c.CDLL(str(LIBRARY))
    for name in ('dna_fonts', 'dna_font_families'):
        fn = getattr(lib, name)
        fn.argtypes = [c.c_void_p, c.c_size_t]
        fn.restype = c.c_size_t
    lib.dna_default_font.argtypes = [c.c_void_p, c.c_size_t]
    lib.dna_match_font.argtypes = [c.c_char_p, c.c_void_p, c.c_size_t]
    output = c.create_string_buffer(1024 * 1024)
    font_root = home / '.local/share/fonts'
    regular = str(font_root / 'fixture.ttf').encode()
    bold = str(font_root / 'fixture-bold.ttf').encode()
    for fn in (lib.dna_fonts, lib.dna_font_families):
        assert fn(None, 4096) == 0
        for capacity in (0, 1, 2, 8, 4096, 1048575):
            c.memset(output, 0x7f, len(output))
            used = fn(output, capacity)
            assert used < capacity if capacity else used == 0
            assert output.raw[capacity] == 0x7f, 'writes past capacity'
            if capacity:
                assert output.raw[used] == 0
                if used:
                    assert output.raw[used - 1] == 10, 'partial list entry'
    used = lib.dna_fonts(output, len(output))
    paths = output.raw[:used].splitlines()
    assert regular in paths and bold in paths
    assert str(font_root / 'proportional.ttf').encode() not in paths
    assert str(font_root / 'unsupported.otf').encode() not in paths
    assert str(font_root / 'unsupported.ttc').encode() not in paths
    assert all(Path(path.decode()).is_file() for path in paths)
    used = lib.dna_font_families(output, len(output))
    families = output.raw[:used].splitlines()
    assert families.count(FAMILY.encode()) == 1
    assert PROPORTIONAL.encode() not in families
    for family in (FAMILY.encode(), FAMILY.upper().encode()):
        assert lib.dna_match_font(family, output, len(output)) == 1
        assert output.value == regular, 'regular weight selected'
    for family in (None, b'', b'DNA Missing Family 94813', PROPORTIONAL.encode()):
        output.value = b'unchanged'
        assert lib.dna_match_font(family, output, len(output)) == 0
        assert output.value == b'unchanged'
    assert lib.dna_default_font(output, len(output)) == 1
    assert Path(output.value.decode()).is_file()
    assert lib.dna_match_font(b'MONOSPACE', output, len(output)) == 1
    for capacity in (0, 1, 2):
        output.value = b'unchanged'
        assert lib.dna_match_font(FAMILY.encode(), output, capacity) == 0
        assert output.value == b'unchanged'
    assert lib.dna_default_font(None, 4096) == 0
    assert lib.dna_match_font(FAMILY.encode(), None, 4096) == 0


if len(sys.argv) == 3 and sys.argv[1] == '--probe':
    probe(Path(sys.argv[2]))
else:
    assert LIBRARY.is_file(), 'build native bridge with scripts/deps.py first'
    if shutil.which('readelf'):
        dependencies = subprocess.check_output(['readelf', '-d', str(LIBRARY)], text=True)
        symbols = subprocess.check_output(['readelf', '--dyn-syms', '--wide', str(LIBRARY)], text=True)
        assert 'libfontconfig' not in dependencies, 'direct fontconfig DT_NEEDED remains'
        assert not re.search(r'\bFc[A-Z]\w*', symbols), 'Fontconfig imports remain'
    with tempfile.TemporaryDirectory(prefix='dna-fonts-') as directory:
        home = Path(directory)
        fonts = home / '.local/share/fonts'
        fonts.mkdir(parents=True)
        (fonts / 'fixture.ttf').write_bytes(face(FAMILY))
        (fonts / 'fixture-bold.ttf').write_bytes(face(FAMILY, 700))
        (fonts / 'proportional.ttf').write_bytes(face(PROPORTIONAL, mono=False))
        (fonts / 'unsupported.otf').write_bytes(b'OTTO' + bytes(64))
        (fonts / 'unsupported.ttc').write_bytes(b'ttcf' + bytes(64))
        env = dict(os.environ, HOME=str(home))
        env['LD_LIBRARY_PATH'] = str(LIBRARY.parent) + os.pathsep + env.get('LD_LIBRARY_PATH', '')
        subprocess.run([sys.executable, __file__, '--probe', str(home)], env=env, check=True, timeout=120)
    print('PASS native fonts: C ABI, supported user fonts, mono filtering, regular/case-insensitive matching, exact misses, unique families, capacities; no direct fontconfig import')
