#!/usr/bin/env python3
"""PTY lifecycle, terminal escape handling, and asynchronous syntax regression."""
import ctypes as c
import os
from pathlib import Path
import tempfile
import subprocess
import time
ROOT=Path(__file__).resolve().parents[1]
lib=c.CDLL(str(ROOT/'build/deps/install/lib/libdna_native.so'))
lib.dna_language_helper.argtypes=[c.c_void_p,c.c_size_t]
helper_path=c.create_string_buffer(4096)
assert lib.dna_language_helper(helper_path,len(helper_path))
helper=Path(os.fsdecode(helper_path.value));assert helper.is_file()
with tempfile.TemporaryDirectory() as config:
    package_root=Path(config)/'languages'
    env=dict(os.environ,PATH='/nonexistent',XDG_CONFIG_HOME=config,DNA_LANGUAGE_DIR=str(package_root))
    def listing():
        result=subprocess.run([str(helper),'list'],env=env,capture_output=True,text=True,check=True)
        assert 'Installed languages:' in result.stdout and 'Available to install:' in result.stdout, result.stdout
        return result.stdout.split('Available to install:',1)
    installed,available=listing()
    assert '(none)' in installed
    assert all(name+':' in available for name in ('dyn','json','html','c','cpp','python','javascript','typescript','tsx','rust','go','bash','css','toml','yaml'))
    # An incomplete directory is not an installed language.
    package=package_root/'dyn';package.mkdir(parents=True)
    installed,available=listing()
    assert 'dyn:' not in installed and 'dyn:' in available
    source=ROOT/'build/test-languages/dyn'
    if source.exists():
        import shutil
        for filename in ('parser.so','highlights.scm','extensions'):
            shutil.copyfile(source/filename,package/filename)
        installed,available=listing()
        assert 'dyn:' in installed and 'dyn:' not in available
        assert 'json:' in available and 'html:' in available
        (package/'parser.so').unlink()
        installed,available=listing()
        assert 'dyn:' not in installed and 'dyn:' in available
print('PASS installed Dyn helper lookup/list without Python or PATH tools')
lib.dna_terminal_open.argtypes=[c.c_char_p,c.c_char_p,c.c_char_p];lib.dna_terminal_open.restype=c.c_void_p
for name in ('poll','alive','close'):
    getattr(lib,'dna_terminal_'+name).argtypes=[c.c_void_p]
lib.dna_terminal_text.argtypes=[c.c_void_p,c.c_char_p,c.c_size_t]
lib.dna_terminal_key.argtypes=[c.c_void_p,c.c_uint32,c.c_uint16]
lib.dna_terminal_snapshot.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t];lib.dna_terminal_snapshot.restype=c.c_size_t
with tempfile.TemporaryDirectory() as directory:
    p=lib.dna_terminal_open(os.fsencode(directory),b'/bin/sh',b'')
    assert p
    try:
        command=b"pwd > location; mkdir nested; cd nested; pwd > ../changed; printf '\\033[31mred\\033[0m'; exit 7"
        lib.dna_terminal_text(p,command,len(command));lib.dna_terminal_key(p,13,0)
        deadline=time.monotonic()+5
        while lib.dna_terminal_alive(p) and time.monotonic()<deadline:
            lib.dna_terminal_poll(p);time.sleep(.01)
        assert not lib.dna_terminal_alive(p),'shell did not exit'
        screen=c.create_string_buffer(32768);lib.dna_terminal_snapshot(p,screen,len(screen))
        assert b'red' in screen.value and b'\x1b' not in screen.value
        assert (Path(directory)/'location').read_text().strip()==directory
        assert (Path(directory)/'changed').read_text().strip()==directory+'/nested'
    finally: lib.dna_terminal_close(p)
print('PASS PTY shell, pwd/cd, ANSI output, exit/reaping')
lib.dna_syntax_open.argtypes=[c.c_char_p,c.c_char_p];lib.dna_syntax_open.restype=c.c_void_p
lib.dna_syntax_open_named.argtypes=[c.c_char_p,c.c_char_p];lib.dna_syntax_open_named.restype=c.c_void_p
lib.dna_syntax_name.argtypes=[c.c_void_p];lib.dna_syntax_name.restype=c.c_char_p
lib.dna_syntax_update.argtypes=[c.c_void_p,c.c_char_p,c.c_uint32,c.c_uint64]
lib.dna_syntax_colors.argtypes=[c.c_void_p,c.c_void_p,c.c_uint32,c.c_uint64]
lib.dna_syntax_close.argtypes=[c.c_void_p]
root=ROOT/'build/test-languages'
if (root/'dyn').exists():
    p=lib.dna_syntax_open(os.fsencode(root),b'test.dyn');assert p
    try:
        text=b'fn main() { value := "hello" // comment\n}\n'
        output=(c.c_ubyte*len(text))()
        lib.dna_syntax_update(p,text,len(text),1)
        deadline=time.monotonic()+5
        while not lib.dna_syntax_colors(p,output,len(text),1) and time.monotonic()<deadline: time.sleep(.01)
        assert output[0]==3 and output[text.index(b'hello')]==2 and output[text.index(b'comment')]==1
        assert not lib.dna_syntax_colors(p,output,len(text),2),'stale colors accepted'
        # The installed parser and bundled query must agree on allocator syntax.
        builtins = ('alloc', 'alloc_or_panic', 'alloc_uninit', 'alloc_uninit_or_panic',
                    'alloc_slice', 'alloc_slice_or_panic', 'alloc_slice_uninit',
                    'alloc_slice_uninit_or_panic')
        source = 'fn allocation(output: Allocator) #AllocResult(*u8) {\n'
        source += '  fixed: [4 * 1024]u8 = []\n  other := #allocator(nil, &callback)\n'
        for index, builtin in enumerate(builtins):
            arguments = 'u8, output, 4' if 'slice' in builtin else 'u8, output'
            source += f'  value{index} := #{builtin}({arguments})\n'
        source += '  return #alloc(u8, output)\n}\n'
        text = source.encode()
        output = (c.c_ubyte * len(text))()
        lib.dna_syntax_update(p, text, len(text), 2)
        deadline = time.monotonic() + 5
        while not lib.dna_syntax_colors(p, output, len(text), 2):
            assert time.monotonic() < deadline, 'allocator syntax timed out'
            time.sleep(.01)
        for token in ('allocator', 'AllocResult', *builtins):
            start = text.index(('#' + token + '(').encode())
            assert list(output[start:start + len(token) + 1]) == [4] * (len(token) + 1), token
        assert output[text.index(b'Allocator')] == 5, 'Allocator primitive highlighting'

    finally: lib.dna_syntax_close(p)
    print('PASS background Dyn highlighting and revision isolation')

    interposer=ROOT/'build/highlight-render.so'
    subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'highlight_render', str(interposer)], check=True)
    with tempfile.TemporaryDirectory() as directory:
        fixture=Path(directory)/'highlight.dyn';fixture.write_text('fn main() { value := "hello" // comment\n}\n')
        env=dict(os.environ,SDL_VIDEODRIVER='dummy',DNA_CONFIG=str(Path(directory)/'absent.toml'),DNA_LANGUAGE_DIR=str(root),LD_PRELOAD=str(interposer))
        for mode in ('debug','release'):
            subprocess.run([str(ROOT/'build'/f'dna-{mode}'),str(fixture)],env=env,timeout=10,check=True)
else:
    print('SKIP grammar checks: install Dyn into build/test-languages to enable them')

# Every bundled package added to the catalogue must load and paint real tokens.
for language,filename,text,token,expected in (
    ('json',b'test.json',b'{"count": 42}',b'42',6),
    ('html',b'test.html',b'<p title="hello">text</p>',b'p',5),
    ('c',b'test.c',b'int main(void) { return 42; }',b'return',3),
    ('cpp',b'test.cpp',b'class Example {};',b'class',3),
    ('python',b'test.py',b'def hello():\n    return 42\n',b'def',3),
    ('javascript',b'test.js',b'const value = "hello";',b'const',3),
    ('typescript',b'test.ts',b'const value: string = "hello";',b'const',3),
    ('tsx',b'test.tsx',b'const view = <div>Hello</div>;',b'const',3),
    ('rust',b'test.rs',b'fn main() { let value = 42; }',b'fn',3),
    ('go',b'test.go',b'package main\nfunc main() {}',b'func',3),
    ('bash',b'test.sh',b'if true; then echo "hello"; fi',b'if',3),
    ('css',b'test.css',b'/* comment */ p { color: red; }',b'comment',1),
    ('toml',b'test.toml',b'name = "hello"\n',b'hello',2),
    ('yaml',b'test.yaml',b'name: "hello"\n',b'hello',2),
    # Upstream queries with predicates, exact file names, bundled queries.
    ('lua',b't.lua',b'local x = "hi" -- note\nreturn x\n',b'local',3),
    ('markdown',b't.md',b'# Title\n\n```\ncode\n```\n',b'Title',3),
    ('zig',b't.zig',b'const std = @import("std");\npub fn main() void {}\n',b'const',3),
    ('odin',b't.odin',b'package main\nmain :: proc() { x := "hi" }\n',b'package',3),
    ('java',b't.java',b'class A { void f() { return; } }\n',b'class',3),
    ('ruby',b't.rb',b'def hello\n  "hi"\nend\n',b'def',3),
    ('php',b't.php',b'<?php function f() { return "hi"; }\n',b'function',3),
    ('c_sharp',b't.cs',b'class A { void F() { return; } }\n',b'class',3),
    ('kotlin',b't.kt',b'fun main() { val x = "hi" }\n',b'fun',3),
    ('haskell',b't.hs',b'main = putStrLn "hi"\n',b'"hi"',2),
    ('ocaml',b't.ml',b'let x = "hi"\n',b'let',3),
    ('elixir',b't.ex',b'defmodule A do\n  def f, do: "hi"\nend\n',b'"hi"',2),
    ('erlang',b't.erl',b'-module(a).\nf() -> "hi".\n',b'"hi"',2),
    ('dockerfile',b'Dockerfile',b'FROM alpine\nRUN echo hi\n',b'FROM',3),
    ('make',b'Makefile',b'all:\n\techo "hi"\n# note\n',b'# note',1),
    ('cmake',b'CMakeLists.txt',b'project(a)\n# note\n',b'# note',1),
    ('nix',b't.nix',b'let x = "hi"; in x\n',b'let',3),
    ('xml',b't.xml',b'<a b="hi"><!-- note --></a>\n',b'note',1),
    ('scss',b't.scss',b'$x: 1;\n@mixin m { color: red; }\n',b'@mixin',3),
    ('ini',b't.ini',b'[section]\nkey = value\n; note\n',b'; note',1),
    ('just',b'justfile',b'# note\nbuild:\n    echo hi\n',b'# note',1),
    ('kdl',b't.kdl',b'node "hi" // note\n',b'"hi"',2),
    ('typst',b't.typ',b'#let x = "hi"\n',b'"hi"',2),
    ('scala',b't.scala',b'object A { def f = "hi" }\n',b'object',3),
    ('dart',b't.dart',b'void main() { var x = "hi"; }\n',b'"hi"',2),
    ('julia',b't.jl',b'function f()\n  return "hi"\nend\n',b'function',3),
    ('r',b't.r',b'f <- function(x) { "hi" }\n',b'function',3),
    ('fish',b't.fish',b'function f\n  echo "hi"\nend\n',b'function',3),
    ('nu',b't.nu',b'def f [] { "hi" }\n',b'def',3),
    ('gleam',b't.gleam',b'pub fn main() { "hi" }\n',b'pub',3),
    ('svelte',b't.svelte',b'<p>hi</p>\n<!-- note -->\n',b'note',1),
    ('vue',b't.vue',b'<template><p>hi</p></template>\n<!-- note -->\n',b'note',1),
    ('glsl',b't.glsl',b'void main() { return; }\n',b'return',3),
    ('proto',b't.proto',b'syntax = "proto3";\nmessage A {}\n',b'message',3),
    ('graphql',b't.graphql',b'query A { field }\n',b'query',3),
    ('clojure',b't.clj',b'(defn f [] "hi") ; note\n',b'"hi"',2),
    ('elm',b't.elm',b'module A exposing (..)\nx = "hi"\n',b'"hi"',2),
    ('gdscript',b't.gd',b'extends Node\nfunc _ready():\n\tvar x = "hi"\n',b'func',3),
    ('hcl',b't.tf',b'resource "a" "b" {\n  x = "hi"\n}\n',b'"hi"',2),
):
    if not (root/language).exists():
        print(f'SKIP {language} grammar: install into build/test-languages to enable')
        continue
    detected=lib.dna_syntax_open(os.fsencode(root),filename);assert detected,language
    assert lib.dna_syntax_name(detected)==language.encode()
    lib.dna_syntax_close(detected)
    handle=lib.dna_syntax_open_named(os.fsencode(root),language.encode());assert handle,language
    assert lib.dna_syntax_name(handle)==language.encode()
    try:
        colors=(c.c_ubyte*len(text))()
        lib.dna_syntax_update(handle,text,len(text),1)
        deadline=time.monotonic()+5
        while not lib.dna_syntax_colors(handle,colors,len(text),1) and time.monotonic()<deadline:
            time.sleep(.01)
        assert colors[text.index(token)]==expected,(language,list(colors))
    finally:
        lib.dna_syntax_close(handle)
    print(f'PASS {language} package loading and highlighting')

assert not lib.dna_syntax_open_named(os.fsencode(root),b'../dyn')
assert not lib.dna_syntax_open_named(os.fsencode(root),b'nonexistent')

if (root/'json').exists():
    handle=lib.dna_syntax_open_named(os.fsencode(root),b'json');assert handle
    try:
        text=b' '*1000000+b'{"count":42}'
        colors=(c.c_ubyte*len(text))()
        lib.dna_syntax_update(handle,text,len(text),77)
        deadline=time.monotonic()+5
        while not lib.dna_syntax_colors(handle,colors,len(text),77) and time.monotonic()<deadline:time.sleep(.01)
        assert colors[text.index(b'42')]==6
        # At buffer.LargeFile (16 MiB) and above, updates are ignored.
        large=b' '*16777216
        lib.dna_syntax_update(handle,large,len(large),78)
        time.sleep(.3)
        assert not lib.dna_syntax_colors(handle,(c.c_ubyte*len(large))(),len(large),78)
    finally:lib.dna_syntax_close(handle)
    print('PASS highlighting a 1 MB file; large files stay plain')

# Incremental parsing must produce the same colors as a fresh parse, including
# UTF-8 edits, multiline replacements, undo-like changes and coalesced revisions.
if (root/'json').exists():
    retained=lib.dna_syntax_open_named(os.fsencode(root),b'json');assert retained
    def painted(handle, source, revision):
        result=(c.c_ubyte*len(source))()
        lib.dna_syntax_update(handle,source,len(source),revision)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if lib.dna_syntax_colors(handle,result,len(source),revision): return bytes(result)
            time.sleep(.001)
        raise AssertionError('incremental syntax timeout')
    try:
        cases=[b'{"count":42}', '{"é中":"é","items":[1,2]}'.encode(), b'{\n"items":[\n3,4\n]\n}', b'{"count":42}', b'', b'[]', b'{"unfinished":']
        for revision in range(1,43):
            text=cases[revision%len(cases)]
            # Supersede an intermediate snapshot without waiting for its parse.
            lib.dna_syntax_update(retained,b'{"discarded":true}',18,revision*2)
            actual=painted(retained,text,revision*2+1)
            fresh=lib.dna_syntax_open_named(os.fsencode(root),b'json');assert fresh
            try: expected=painted(fresh,text,1)
            finally: lib.dna_syntax_close(fresh)
            assert actual==expected,(revision,text,actual,expected)
    finally: lib.dna_syntax_close(retained)
    print('PASS incremental highlighting equals fresh parses through UTF-8/coalesced edits')
