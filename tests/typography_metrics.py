#!/usr/bin/env python3
"""Verify actual native glyph bounds fit typography rows across scales/sizes."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
font=next((Path(x) for x in [os.environ.get('DNA_TYPOGRAPHY_FONT',''),'/usr/share/fonts/noto/NotoSansMono-Regular.ttf','/usr/share/fonts/TTF/DejaVuSansMono.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'] if x and Path(x).is_file()),None)
if font is None:raise SystemExit('Set DNA_TYPOGRAPHY_FONT to a monospace face')
fallback=next((Path(x) for x in [os.environ.get('DNA_TYPOGRAPHY_FALLBACK',''),'/usr/share/fonts/noto/NotoSansArabic-Bold.ttf'] if x and Path(x).is_file()),None)
if fallback is None:print('SKIP configured fallback glyph bounds: set DNA_TYPOGRAPHY_FALLBACK to NotoSansArabic-Bold.ttf',flush=True)
with tempfile.TemporaryDirectory(prefix='dna-typography-',dir=ROOT/'build') as temporary:
    work=Path(temporary);stage=work/'src';shutil.copytree(ROOT/'src',stage)
    shutil.copyfile(ROOT/'tests/editor/typography_metrics_smoke.dyn',stage/'typography_metrics_smoke.dyn')
    gui=stage/'platform/gui.dyn';source=gui.read_text()
    at=source.index('pub fn native_text_bitmap(')
    body=source.index('{',at)
    source=source[:body+1]+'\n if y+#cast(f32,height)>typography_probe_ink_bottom {typography_probe_ink_bottom=y+#cast(f32,height)}\n'+source[body+1:]
    source+='''\ntypography_probe_ink_bottom:f32
pub fn typography_probe_reset(){typography_probe_ink_bottom=0.0}
pub fn typography_probe_bottom()f32{return typography_probe_ink_bottom}
'''
    gui.write_text(source)
    native=stage/'text/native.dyn'
    native.write_text(native.read_text()+'''\npub fn typography_probe_uses_fallback(handle:rawptr)bool {
 text:=#cast(*NativeText,handle)
 for glyph in text.layout.glyphs {if !glyph.hidden && glyph.font!=#cast(rawptr,text.font) {return true}}
 return false
}
''')
    (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer:rawptr,window:rawptr,input_storage:[]u8){
 typography_metrics_smoke(app,typography,renderer,sdl.typography_probe_reset,sdl.typography_probe_bottom,ttf.typography_probe_uses_fallback,FALLBACK_PATH)
}
fn finish_probe(app:*App){}
'''.replace('FALLBACK_PATH',json.dumps(str(fallback) if fallback else '')))
    env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_FONT=str(font),DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary=work/'editor'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([str(binary)],env=env,check=True,timeout=90)
        print(f'PASS native typography ({mode}): glyph bounds, fractional rows and shrinking resize across 27 size/scale/leading combinations; {font.name}'+(f'; configured {fallback.name} fallback glyphs verified' if fallback else ''),flush=True)
