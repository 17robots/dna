#!/usr/bin/env python3
"""Exercise the Dyn adapter library through its real C ABI."""
import ctypes as c
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lib = c.CDLL(str(root/'build/deps/install/lib/libdna_native.so'))
lib.dna_theme_select.argtypes = [c.c_bool]
lib.dna_theme_override.argtypes = [c.c_uint32]
lib.dna_theme_override.restype = c.c_uint32
lib.dna_theme_set_override.argtypes = [c.c_uint32, c.c_uint32]
lib.dna_theme_generation.restype = c.c_uint32
lib.dna_theme_select(False)
assert lib.dna_theme_mode() == 0
initial = lib.dna_theme_generation()
for index in range(32):
    assert lib.dna_theme_override(index) == 0x1000000
    lib.dna_theme_set_override(index, index * 123)
    assert lib.dna_theme_override(index) == index * 123
assert lib.dna_theme_generation() == initial + 32
lib.dna_theme_set_override(32, 1)
lib.dna_theme_set_override(0, 0x1000000)
assert lib.dna_theme_generation() == initial + 32
lib.dna_theme_select(True)
assert lib.dna_theme_mode() == 1
assert all(lib.dna_theme_override(i) == 0x1000000 for i in range(33))
lib.dna_default_font.argtypes = [c.c_void_p, c.c_size_t]
lib.dna_match_font.argtypes = [c.c_char_p, c.c_void_p, c.c_size_t]
lib.dna_fonts.argtypes = [c.c_void_p, c.c_size_t]
lib.dna_fonts.restype = c.c_size_t
assert lib.dna_fonts(None, 4096) == 0
assert not lib.dna_default_font(None, 4096)
assert not lib.dna_match_font(None, None, 0)
output = c.create_string_buffer(65536)
assert lib.dna_default_font(output, len(output)) and Path(output.value.decode()).is_file()
assert lib.dna_match_font(b'monospace', output, len(output)) and Path(output.value.decode()).is_file()
assert not lib.dna_match_font(b'', output, len(output))
for capacity in (0, 1, 2, 8, 4096, 65535):
    c.memset(output, 0x7f, len(output))
    used = lib.dna_fonts(output, capacity)
    assert used < capacity if capacity else used == 0
    assert output.raw[capacity] == 0x7f, 'overwrote caller capacity'
    if capacity:
        assert output.raw[used] == 0
        if used:
            assert output.raw[used - 1] == 10
            assert all(Path(p.decode()).is_file() for p in output.raw[:used].splitlines())
small = c.create_string_buffer(b'xxxx')
assert not lib.dna_default_font(small, 2) and small.value == b'xxxx'
print('PASS Dyn support library: C ABI, theme boundaries, Fontconfig ownership and output capacities')
