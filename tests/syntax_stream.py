#!/usr/bin/env python3
"""Full-context syntax reads chunks and releases cancelled sources exactly once."""
import ctypes as c
import os
from pathlib import Path
import threading
import shutil
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
lib = c.CDLL(str(ROOT / 'build/deps/install/lib/libdna_native.so'))
Read = c.CFUNCTYPE(c.c_void_p, c.c_void_p, c.c_uint32, c.POINTER(c.c_uint32))
Done = c.CFUNCTYPE(None, c.c_void_p)
class Request(c.Structure):
    _fields_ = [('context', c.c_void_p), ('read', Read), ('done', Done),
                ('length', c.c_uint32), ('low', c.c_uint32), ('high', c.c_uint32),
                ('revision', c.c_uint64), ('document_revision', c.c_uint64)]
lib.dna_syntax_open_named.argtypes = [c.c_char_p, c.c_char_p]
lib.dna_syntax_open_named.restype = c.c_void_p
lib.dna_syntax_stream.argtypes = [c.c_void_p, c.POINTER(Request)]
lib.dna_syntax_stream_needed.argtypes = [c.c_void_p, c.c_uint64]
lib.dna_syntax_colors.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32, c.c_uint64]
lib.dna_syntax_close.argtypes = [c.c_void_p]
sources = {}
@Read
def read(context, offset, length):
    source = sources[context]
    length[0] = min(16381, len(source['text']) - offset)
    return c.addressof(source['bytes']) + offset if length[0] else None
@Done
def done(context):
    sources[context]['calls'] += 1
    sources[context]['done'].set()

def submit(worker, text, low, high, revision, document_revision=None):
    key = len(sources) + 1
    source = dict(text=text, bytes=c.create_string_buffer(text), calls=0, done=threading.Event())
    sources[key] = source
    request = Request(key, read, done, len(text), low, high, revision, document_revision or revision)
    assert lib.dna_syntax_stream(worker, c.byref(request)) == 1
    return source

def colors(worker, size, revision):
    output = c.create_string_buffer(size)
    deadline = time.monotonic() + 20
    while not lib.dna_syntax_colors(worker, output, size, revision):
        assert time.monotonic() < deadline, ('syntax stream not ready', revision)
        time.sleep(.005)
    return output.raw

worker = lib.dna_syntax_open_named(os.fsencode(ROOT / 'build/test-languages'), b'dyn')
assert worker
try:
    text = b'/* opener\n' + b'int quoted = "no";\n' * 700000 + b'*/\nfn tail() {}\n'
    low = text.index(b'*/') - 200
    high = len(text)
    source = submit(worker, text, low, high, 1)
    result = colors(worker, high - low, 1)
    assert result[:200] == b'\1' * 200, result[:200]
    assert result[-13:-11] == b'\3\3', result[-15:]
    assert source['done'].wait(3) and source['calls'] == 1
    # Same document, another color range: reuse its complete grammar context.
    source = submit(worker, text, low - 500, low, 2, document_revision=1)
    assert colors(worker, 500, 2) == b'\1' * 500
    assert source['done'].wait(3) and source['calls'] == 1
    assert lib.dna_syntax_stream_needed(worker, 2) == 0
    # Predicates read a capture split across source chunks, including UTF-8.
    text = b'fn main() { ' + b' ' * 16370 + 'name := "héllo" }'.encode()
    source = submit(worker, text, 0, len(text), 3)
    result = colors(worker, len(text), 3)
    assert result[:2] == b'\3\3'
    assert result[text.index(b'"'):].startswith(b'\2' * len('"héllo"'.encode()))
    assert source['done'].wait(3)
    # Superseding requests and closing must release all accepted sources.
    for revision in range(4, 12):
        submit(worker, b'fn repeated() {}\n' * 300000, 0, 128, revision)
finally:
    lib.dna_syntax_close(worker)
# Predicate captures may span several chunks. Keep predicate behavior identical
# to contiguous parsing rather than silently skipping it for streamed input.
with tempfile.TemporaryDirectory(prefix='dna-stream-predicate-') as directory:
    package = Path(directory) / 'dyn'
    shutil.copytree(ROOT / 'build/test-languages/dyn', package)
    (package / 'highlights.scm').write_text('((identifier) @constant (#match? @constant "^A+$"))\n')
    worker = lib.dna_syntax_open_named(os.fsencode(directory), b'dyn')
    assert worker
    try:
        name = b'A' * 20000
        text = b'fn main() { ' + name + b' := 1 }'
        source = submit(worker, text, 0, len(text), 20)
        result = colors(worker, len(text), 20)
        assert result[12:12 + len(name)] == b'\6' * len(name)
        assert source['done'].wait(3)
    finally:
        lib.dna_syntax_close(worker)
for source in sources.values():
    assert source['done'].wait(3) and source['calls'] == 1, source['calls']
print('PASS syntax streams: context beyond 8 MiB, range changes, chunked UTF-8, cancellation and source lifetime')
