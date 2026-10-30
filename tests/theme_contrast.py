#!/usr/bin/env python3
"""Check native default theme inks on the backgrounds where UI draws them."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
DYN=os.environ.get('DYN',str(ROOT.parent/'dyn/compiler/build/dyn-release'))
s=(ROOT/'src/theme.dyn').read_text()
start=s.index('fn default_theme(');end=s.index('\nfn paint(',start)
probe=s[:s.index('extern fn theme_mode')]+'''light:bool
fn theme_mode()i32 {if light {return 1}\n return 0}
'''+s[start:end]+'''
fn main(){
 for mode in 0..2 {
  light=mode==1
  t:=default_theme()
  colors:=[t.background,t.surface,t.selection,t.text,t.muted,t.cursor]
  bytes:[18]u8=[]
  for i in 0..6 {bytes[i*3]=colors[i].red
   bytes[i*3+1]=colors[i].green
   bytes[i*3+2]=colors[i].blue}
  _=#syscall(1,1,&bytes[0],18)
 }
}
'''
def luminance(rgb):
    channels=[v/255 for v in rgb]
    channels=[v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in channels]
    return sum(v*w for v,w in zip(channels,(0.2126,0.7152,0.0722)))
def contrast(a,b):
    lo,hi=sorted((luminance(a),luminance(b)))
    return (hi+0.05)/(lo+0.05)
with tempfile.TemporaryDirectory(prefix='dna-theme-contrast-') as temp:
    work=Path(temp);(work/'main.dyn').write_text(probe)
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary=work/'probe'
        subprocess.run(['python3',str(ROOT/'scripts/compile.py'),DYN,'build',str(work),'--'+mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        data=subprocess.check_output([str(binary)])
        assert len(data)==36
        for i,name in enumerate(('charcoal','light')):
            values=[data[i*18+j:i*18+j+3] for j in range(0,18,3)]
            background,surface,selection,text,muted,accent=values
            checks=[('text/background',text,background),('text/surface',text,surface),('text/selection',text,selection),('muted/background',muted,background),('muted/surface',muted,surface),('shortcut/surface',accent,surface)]
            for label,ink,fill in checks:
                value=contrast(ink,fill)
                assert value>=4.5,f'{name} {label} contrast {value:.2f}:1 below 4.5:1'
            print(f'PASS {mode} {name}: normal, selected, muted and shortcut inks >=4.5:1 on their UI backgrounds',flush=True)
