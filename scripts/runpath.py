#!/usr/bin/env python3
"""Linker argument embedding where DNA binaries find their bundled libraries.

Relative to the executable: build/ binaries use build/deps/install/lib and a
packaged bin/dna uses ../lib, so running a binary directly needs no
LD_LIBRARY_PATH. DT_RPATH (not RUNPATH) also covers libraries loaded by
libdna_native. System libraries still resolve through the normal search path.
"""


def runpath():
    return '-rpath=$ORIGIN/deps/install/lib:$ORIGIN/../lib:$ORIGIN/../deps/install/lib'


if __name__ == '__main__':
    print(runpath())
