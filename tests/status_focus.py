#!/usr/bin/env python3
"""Production status segments distinguish focused panes without changing hit geometry."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get('DYN', str(ROOT.parent / 'dyn/compiler/build/dyn-release'))

def function(source, name):
    start = source.index('fn ' + name + '(')
    body = source.index('{', start)
    depth, end = 1, body + 1
    while depth:
        if source[end] == '{': depth += 1
        elif source[end] == '}': depth -= 1
        end += 1
    return source[start:end] + '\n'

source = '''use "./buffer" buffer
const UiBackground:u32=2
const UiText:u32=8
const UiClip:u32=16
const UiClickable:u32=1
const UiHover:u32=128
const UiMuted:u32=512
const UiAxisX:usize=0
const UiAxisY:usize=1
const StatusBase:usize=1000000
struct App {view:View}
struct View {focused:usize}
struct Rgb {red,green,blue:u8}
struct Theme {selection:Rgb}
fn theme() Theme {return Theme{selection:Rgb{red:53,green:65,blue:80}}}
struct Box {value:usize,padding:[2]f32,flags:u32,fill:Rgb}
struct UiState {boxes:[2]Box,cell:f32=8.0}
enum UiSizeKind {Text,Percent}
fn ui_key(ui:*UiState,name:[]const u8) u64 {return 0}
fn ui_make(ui:*UiState,key:u64,flags:u32) usize {ui.boxes[1].flags=flags
 return 1}
fn ui_text_set(ui:*UiState,index:usize,text:[]const u8) {}
fn ui_size(ui:*UiState,index,axis:usize,kind:UiSizeKind,value,strict:f32) {}
fn ui_animate(app:*App,ui:*UiState,index:usize,selected:bool) {}
''' + function((ROOT / 'src/chrome.dyn').read_text(), 'status_segment') + '''
fn main() {
 app:=App{}
 ui:=UiState{}
 status_segment(&app,&ui,0,"mode","NORMAL",0,0)
 if (ui.boxes[1].flags & UiBackground)==0 || ui.boxes[1].fill.red!=53 {#panic("focused mode has no selection background")}
 if (ui.boxes[1].flags & UiMuted)!=0 {#panic("focused mode is muted")}
 status_segment(&app,&ui,1,"mode","NORMAL",0,0)
 if (ui.boxes[1].flags & UiMuted)==0 {#panic("inactive mode is as bright as focused mode")}
 if (ui.boxes[1].flags & UiBackground)!=0 {#panic("inactive mode retains focus background")}
 status_segment(&app,&ui,1,"message","diagnostic",80,UiClip)
 expected:=UiText|UiClip|UiClickable|UiHover|UiMuted
 if ui.boxes[1].flags!=expected || ui.boxes[1].value!=1001080 || ui.boxes[1].padding[0]!=8.0 {#panic("inactive status lost click, clip or spacing")}
 app.view.focused=1
 status_segment(&app,&ui,1,"file","main.dyn",21,0)
 if ui.boxes[1].flags!=(UiText|UiClickable|UiHover) {#panic("newly focused file does not regain normal ink")}
 status_segment(&app,&ui,1,"mode","INSERT REC",0,0)
 if ui.boxes[1].flags!=(UiText|UiBackground) {#panic("recording mode loses focus background")}
}
'''
with tempfile.TemporaryDirectory(prefix='dna-status-focus-') as temporary:
    work=Path(temporary)
    (work/'buffer').mkdir()
    (work/'buffer/buffer.dyn').write_text('pub fn equal(a,b:[]const u8) bool {if #len(a)!=#len(b) {return false}\n for i in 0..#len(a) {if a[i]!=b[i] {return false}}\n return true}\n')
    (work/'main.dyn').write_text(source)
    for mode in ('debug','release'):
        binary=work/('status-'+mode)
        subprocess.run(['python3',str(ROOT/'scripts/compile.py'),DYN,'build',str(work),'--'+mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([str(binary)],check=True)
        print('PASS status focus '+mode+': active mode fill, inactive muted, focus transfer and unchanged hit geometry',flush=True)
