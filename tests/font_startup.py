#!/usr/bin/env python3
"""Startup reuses an identical open font; explicit reloads still reopen files."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'src/config.dyn').read_text()
start=source.index('fn config_open_font(')
end=source.index('\nfn release_config_font(',start)
with tempfile.TemporaryDirectory(prefix='dna-font-startup-') as directory:
    root=Path(directory)
    for module in ('buffer','ttf'):(root/module).mkdir()
    (root/'buffer/buffer.dyn').write_text('use "std/bytes"\npub fn equal(a,b:[]const u8)bool{return bytes.equal(a,b)}\n')
    (root/'ttf/ttf.dyn').write_text('''pub opens:usize
pub fn open(path:*const u8,points:f32)rawptr {opens+=1
 return #cast(rawptr,2)}
''')
    (root/'main.dyn').write_text('''use "std/c"
use "std/mem"
use "./buffer" buffer
use "./ttf" ttf
struct Fonts {original_font_path:[4096]u8,original_font_length:usize}
struct App {fonts:Fonts}
struct Typography {original_font:rawptr,points,scale:f32}
'''+source[start:end]+'''
fn main(){
 app:=App{}
 path:[32]u8=[]
 name:[]const u8="same.ttf"
 _=mem.copy(path[..#len(name)],name)
 _=mem.copy(app.fonts.original_font_path[..#len(name)],name)
 app.fonts.original_font_length=#len(name)
 typography:=Typography{original_font:#cast(rawptr,1),points:16.0,scale:2.0}
 if config_open_font(&app,&typography,&path[0],32.0,true)!=typography.original_font || ttf.opens!=0 {#panic("startup font opened twice")}
 if config_open_font(&app,&typography,&path[0],32.0,false)==typography.original_font || ttf.opens!=1 {#panic("explicit reload must reopen font file")}
 if config_open_font(&app,&typography,&path[0],28.0,true)==typography.original_font || ttf.opens!=2 {#panic("different startup font size needs independent font")}
 path[0]=100
 if config_open_font(&app,&typography,&path[0],32.0,true)==typography.original_font || ttf.opens!=3 {#panic("different font path reused original")}
}
''')
    for mode in ('debug','release'):
        binary=root/mode
        subprocess.run(['python3',str(ROOT/'scripts/compile.py'),os.environ.get('DYN','dyn'),'build',str(root),'--'+mode,'--output',str(binary)],check=True)
        subprocess.run([str(binary)],check=True,timeout=10)
print('PASS startup font reuse: same path/size, explicit file reload, changed size and path (debug/release)')
