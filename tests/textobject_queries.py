#!/usr/bin/env python3
"""Every shipped text-object query compiles against its pinned grammar and
selects the expected function (around and inside) from inside a function body.

A query with one unknown node name fails to compile as a whole, which would
silently leave a language without text objects; this catches that.
"""
import ctypes as c
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ROOT / 'build/test-languages'
# Language: (source, function text, function body text). The cursor goes on
# the marker MARK, which sits inside the body.
SAMPLES = {
    'rust': ('// lead\nfn add(a: i32, b: i32) -> i32 {\n    a + MARK\n}\n',
             'fn add(a: i32, b: i32) -> i32 {\n    a + MARK\n}', '{\n    a + MARK\n}'),
    'c': ('/* lead */\nint add(int a, int b) {\n    return a + MARK;\n}\n',
          'int add(int a, int b) {\n    return a + MARK;\n}', '{\n    return a + MARK;\n}'),
    'cpp': ('// lead\nint add(int a, int b) {\n    return a + MARK;\n}\n',
            'int add(int a, int b) {\n    return a + MARK;\n}', '{\n    return a + MARK;\n}'),
    'python': ('# lead\ndef add(a, b):\n    return a + MARK\n',
               'def add(a, b):\n    return a + MARK', 'return a + MARK'),
    'go': ('package main\n\nfunc add(a int, b int) int {\n\treturn a + MARK\n}\n',
           'func add(a int, b int) int {\n\treturn a + MARK\n}', '{\n\treturn a + MARK\n}'),
    'javascript': ('// lead\nfunction add(a, b) {\n  return a + MARK;\n}\n',
                   'function add(a, b) {\n  return a + MARK;\n}', '{\n  return a + MARK;\n}'),
    'typescript': ('// lead\nfunction add(a: number, b: number): number {\n  return a + MARK;\n}\n',
                   'function add(a: number, b: number): number {\n  return a + MARK;\n}', '{\n  return a + MARK;\n}'),
    'tsx': ('// lead\nfunction add(a: number, b: number): number {\n  return a + MARK;\n}\n',
            'function add(a: number, b: number): number {\n  return a + MARK;\n}', '{\n  return a + MARK;\n}'),
    'bash': ('# lead\nadd() {\n  echo MARK\n}\n', 'add() {\n  echo MARK\n}', '{\n  echo MARK\n}'),
    'dyn': ('// lead\nfn add(a: i32, b: i32) i32 {\n  return a + MARK\n}\n',
            'fn add(a: i32, b: i32) i32 {\n  return a + MARK\n}', '{\n  return a + MARK\n}'),
}
FUNCTION_INSIDE, FUNCTION_AROUND, COMMENT_AROUND = 0, 1, 7

shipped = sorted(path.name.split('.')[0] for path in (ROOT / 'languages/queries').glob('*.textobjects.scm'))
assert sorted(SAMPLES) == shipped, ('every shipped query needs a sample', shipped)
for language in shipped:
    if not (LANGUAGES / language / 'parser.so').exists():
        subprocess.run(['python3', str(ROOT / 'scripts/compile.py'), str(ROOT / 'build/deps/install/bin/dna-language'),
                        'install', language], env=dict(os.environ, DNA_LANGUAGE_DIR=str(LANGUAGES)), check=True, timeout=600)

lib = c.CDLL(str(ROOT / 'build/deps/install/lib/libdna_native.so'))
lib.dna_syntax_open_named.argtypes = [c.c_char_p, c.c_char_p]
lib.dna_syntax_open_named.restype = c.c_void_p
lib.dna_syntax_update.argtypes = [c.c_void_p, c.c_char_p, c.c_uint32, c.c_uint64]
lib.dna_syntax_object.argtypes = [c.c_void_p, c.c_uint64, c.c_uint32, c.c_uint32, c.c_uint, c.c_uint,
                                  c.POINTER(c.c_uint32), c.POINTER(c.c_uint32)]
lib.dna_syntax_close.argtypes = [c.c_void_p]

with tempfile.TemporaryDirectory(prefix='dna-textobjects-') as directory:
    for language in shipped:
        package = Path(directory) / language
        shutil.copytree(LANGUAGES / language, package)
        shutil.copyfile(ROOT / 'languages/queries' / (language + '.textobjects.scm'), package / 'textobjects.scm')
        source, function, body = SAMPLES[language]
        text = source.encode()
        mark = text.index(b'MARK')
        state = lib.dna_syntax_open_named(directory.encode(), language.encode())
        assert state, language
        try:
            lib.dna_syntax_update(state, text, len(text), 1)

            def select(kind, at=mark):
                start, end = c.c_uint32(), c.c_uint32()
                if not lib.dna_syntax_object(state, 1, at, at, kind, 1, c.byref(start), c.byref(end)):
                    return None
                return text[start.value:end.value].decode()

            deadline = time.monotonic() + 5
            while select(FUNCTION_AROUND) is None and time.monotonic() < deadline:
                time.sleep(.005)
            assert select(FUNCTION_AROUND) == function, (language, 'around', select(FUNCTION_AROUND))
            assert select(FUNCTION_INSIDE) == body, (language, 'inside', select(FUNCTION_INSIDE))
            # Every language starts with a comment, except Go's package line.
            if language != 'go':
                assert select(COMMENT_AROUND, 3) is not None, (language, 'comment')
        finally:
            lib.dna_syntax_close(state)
        print('ok', language, flush=True)
print('PASS text-object queries for', len(shipped), 'languages: function around/inside and comments')
