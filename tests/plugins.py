#!/usr/bin/env python3
"""Actual Dyn plugin process + bounded transport/failure lifecycle."""
import ctypes as c
import json
import os
from pathlib import Path
import tempfile
import time
root = Path(__file__).resolve().parents[1]
lib = c.CDLL(os.environ.get('DNA_NATIVE_LIBRARY',str(root/'build/deps/install/lib/libdna_native.so')))
lib.dna_plugin_open.argtypes=[c.c_char_p,c.c_char_p]; lib.dna_plugin_open.restype=c.c_void_p
lib.dna_plugin_send.argtypes=[c.c_void_p,c.c_char_p,c.c_size_t]
lib.dna_plugin_read.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t];lib.dna_plugin_read.restype=c.c_long
lib.dna_plugin_close.argtypes=[c.c_void_p]
plugin=root/'examples/plugins/uppercase/uppercase'
p=lib.dna_plugin_open(os.fsencode(plugin),os.fsencode(plugin.parent));assert p
try:
    def send(message):
        data=json.dumps(message).encode()+b'\n';assert lib.dna_plugin_send(p,data,len(data))
    def receive():
        deadline=time.monotonic()+3;storage=c.create_string_buffer(524288)
        while time.monotonic()<deadline:
            n=lib.dna_plugin_read(p,storage,len(storage)); assert n>=0
            if n: return json.loads(storage.raw[:n])
            time.sleep(.001)
        raise AssertionError('plugin timeout')
    send({'type':'initialize','version':1})
    assert receive()=={'type':'command','name':'Uppercase buffer'}
    assert receive()=={'type':'ready'}
    send({'type':'command','name':'Uppercase buffer','buffer':3,'revision':42,'text':'hello α\n'})
    assert receive()=={'type':'replace','buffer':3,'revision':42,'text':'HELLO α\n'}
    assert receive()=={'type':'done'}
finally:lib.dna_plugin_close(p)
with tempfile.TemporaryDirectory() as directory:
    executable=Path(directory)/'exit';executable.write_text('#!/bin/sh\nexit 1\n');executable.chmod(0o755)
    p=lib.dna_plugin_open(os.fsencode(executable),os.fsencode(directory));assert p
    try:
        deadline=time.monotonic()+3;storage=c.create_string_buffer(32)
        while time.monotonic()<deadline:
            n=lib.dna_plugin_read(p,storage,len(storage))
            if n<0:break
            time.sleep(.001)
        else:raise AssertionError('exit not detected')
    finally:lib.dna_plugin_close(p)
print('PASS Dyn plugin protocol, edits, Unicode, process exit')

lib.dna_plugin_install.argtypes=[c.c_char_p]*5
lib.dna_plugin_remove.argtypes=[c.c_char_p]*2
lib.dna_plugin_rollback.argtypes=[c.c_char_p]*2
lib.dna_plugin_log.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t]
lib.dna_plugin_log.restype=c.c_size_t
with tempfile.TemporaryDirectory() as directory:
    base=Path(directory);source=base/'source';source.mkdir();installed=base/'installed'
    manifest=source/'plugin.json';manifest.write_text('{"name":"fixture","executable":"run","permissions":[]}')
    executable=source/'run';executable.write_text('#!/bin/sh\necho fixture-crash >&2\nexit 7\n');executable.chmod(0o700)
    args=list(map(os.fsencode,(manifest,executable,installed)))+[b'fixture',b'run']
    assert lib.dna_plugin_install(*args)
    target=installed/'fixture'
    assert (target/'.dna-source').read_text()==str(manifest)
    executable.write_text('#!/bin/sh\necho updated-crash >&2\nexit 7\n')
    assert lib.dna_plugin_install(*args)
    assert (target/'run').read_text()==executable.read_text()
    assert len(list(installed.glob('.fixture-*')))==1
    p=lib.dna_plugin_open(os.fsencode(target/'run'),os.fsencode(target));assert p
    try:
        storage=c.create_string_buffer(4096);deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            if lib.dna_plugin_read(p,storage,len(storage))<0:break
            time.sleep(.001)
        count=lib.dna_plugin_log(p,storage,len(storage))
        assert b'updated-crash' in storage.raw[:count]
    finally:lib.dna_plugin_close(p)
    assert not lib.dna_plugin_remove(os.fsencode(installed),b'../source')
    assert lib.dna_plugin_remove(os.fsencode(installed),b'fixture')
    assert not target.exists() and len(list(installed.glob('.removed-fixture-*')))==1
    assert not lib.dna_plugin_remove(os.fsencode(base),b'source')
    assert not lib.dna_plugin_rollback(os.fsencode(base),b'../source')
print('PASS plugin update provenance, retained versions, stderr and recoverable removal')

with tempfile.TemporaryDirectory() as directory:
    base=Path(directory); source=base/'source'; source.mkdir(); installed=base/'installed'
    manifest=source/'plugin.json'; manifest.write_text('{"name":"fixture","executable":"run","permissions":[]}')
    executable=source/'run'; executable.write_text('#!/bin/sh\nexit 1\n'); executable.chmod(0o700)
    args=list(map(os.fsencode,(manifest,executable,installed)))+[b'fixture',b'run']
    assert lib.dna_plugin_install(*args)
    assert not lib.dna_plugin_rollback(os.fsencode(installed),b'fixture')
    executable.write_text('#!/bin/sh\nexit 2\n')
    assert lib.dna_plugin_install(*args)
    assert lib.dna_plugin_rollback(os.fsencode(installed),b'fixture')
    assert (installed/'fixture/run').read_text().endswith('exit 1\n')
    assert lib.dna_plugin_rollback(os.fsencode(installed),b'fixture')
    assert (installed/'fixture/run').read_text().endswith('exit 2\n')
print('PASS atomic plugin rollback and roll-forward')
