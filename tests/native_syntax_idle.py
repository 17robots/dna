#!/usr/bin/env python3
"""Force worker completion after syntax's service phase in the real event loop."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-syntax-idle-',dir=ROOT/'build') as temporary:
 work=Path(temporary);stage=work/'src';shutil.copytree(ROOT/'src',stage)
 shutil.copyfile(ROOT/'tests/fixtures/native_syntax_idle.dyn',stage/'startup_probe.dyn')
 gui=stage/'platform/gui.dyn';source=gui.read_text()
 # Queue delivery remains production; remove unrelated desktop input/readiness.
 start=source.index('  for native_gui.deferred_count!=0',source.index('fn sdl_poll('))
 end=source.index('\nfn sdl_wait_timeout(',start)
 source=source[:start]+'  return false\n}\n'+source[end:]
 start=source.index('fn sdl_wait_timeout(');end=source.index('\nfn sdl_wait(',start)
 source=source[:start]+'''fn sdl_wait_timeout(event:*Event,milliseconds:i32)bool {
 if sdl_poll(event) {return true}
 syntax_idle_callback(milliseconds)
 return false
}
'''+source[end:]
 start=source.index('fn sdl_present(');end=source.index('\nfn sdl_scale(',start)
 source=source[:start]+'fn sdl_present(renderer:rawptr)bool{return true}\n'+source[end:]
 source+='''\nsyntax_idle_callback:fn(i32)
pub fn syntax_idle_setup(callback:fn(i32)){syntax_idle_callback=callback}
'''
 gui.write_text(source)
 scheduler=stage/'scheduler.dyn';source=scheduler.read_text().replace('  phase.* = (phase.* + 1) % 11','  syntax_idle_phase(app,phase.*)\n  phase.* = (phase.* + 1) % 11')
 scheduler.write_text(source)
 syntax=stage/'syntax.dyn';source=syntax.read_text().replace('  if syntax_colors(slot.syntax,','  if !syntax_idle_hold_ack && syntax_colors(slot.syntax,')
 syntax.write_text(source)
 env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),DNA_LANGUAGE_DIR=str(ROOT/'build/test-languages'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
 for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
  binary=work/'editor'
  subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
  subprocess.run([str(binary)],env=env,check=True,timeout=15)
  print(f'PASS native syntax idle completion ({mode}): wake after syntax phase reaches fresh highlighted paint before idle',flush=True)
