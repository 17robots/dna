#!/usr/bin/env python3
"""Check tiny settled Dyn tokens through real worker and native framebuffer."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from native_gpu_probe import install as gpu_probe
ROOT=Path(__file__).resolve().parents[1]
roots=[ROOT/'build/test-languages']
# Standalone runs and clean CI must provision this before starting the worker.
if not (roots[0]/'dyn/parser.so').is_file():
 subprocess.run([sys.executable,str(ROOT/'scripts/compile.py'),
                 str(ROOT/'build/deps/install/bin/dna-language'),'install','dyn'],
                env=dict(os.environ,DNA_LANGUAGE_DIR=str(roots[0])),check=True,timeout=180)
installed=Path.home()/'.config/dna/languages'
if (installed/'dyn/parser.so').is_file():roots.append(installed)
font=Path('/usr/share/fonts/TTF/ZedMonoNerdFontMono-Regular.ttf')
with tempfile.TemporaryDirectory(prefix='dna-settled-syntax-',dir=ROOT/'build') as temporary:
 work=Path(temporary);stage=work/'src';shutil.copytree(ROOT/'src',stage)
 for name in ('native_typing_frame_smoke.dyn','native_syntax_settled_frame_smoke.dyn'):
  shutil.copyfile(ROOT/'tests/editor'/name,stage/name)
 gui=stage/'platform/gui.dyn';source=gui.read_text()
 begin=source.index('fn sdl_present(');end=source.index('\nfn sdl_scale(',begin)
 source=source[:begin]+'fn sdl_present(renderer:rawptr)bool{return true}\n'+source[end:]
 source+='''\npub fn typing_probe_pixels() []const u8 {return native_gui.surface.pixels}
pub fn typing_probe_resize(width,height:i32) {
 native_gui.window.width=width
 native_gui.window.height=height
 if !native_resize() {#panic("settled frame resize")}
}
'''
 gui.write_text(gpu_probe(source))
 (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer:rawptr,window:rawptr,input_storage:[]u8){
 native_syntax_settled_frame_smoke(app,typography,renderer,window,NativeTypingFrameProbe{pixels:sdl.typing_probe_pixels,resize:sdl.typing_probe_resize})
}
fn finish_probe(app:*App){}
''')
 configs=[work/'missing.toml']
 if font.is_file():
  config=work/'one-dark.toml';config.write_text(f'theme = "one-dark"\nfont = "{font}"\nfont_size = 14\nline_height = 1.25\n')
  configs.append(config)
 for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
  binary=work/'editor'
  subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
  for root in roots:
   for config in configs:
    env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(config),DNA_LANGUAGE_DIR=str(root),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    subprocess.run([str(binary)],env=env,check=True,timeout=90)
    print(f'PASS settled native Dyn tokens ({mode}, {root}, {config.name}): loaded and typed fn, mainthing, print and string visibly colored',flush=True)
