#!/usr/bin/env python3
"""Ignored text after a command key must not cancel the split it just opened."""
import os
from pathlib import Path
import shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-entrance-event-',dir=ROOT/'build') as temp:
 work=Path(temp);stage=work/'src';shutil.copytree(ROOT/'src',stage)
 shutil.copyfile(ROOT/'tests/fixtures/entrance_command_text.dyn',stage/'startup_probe.dyn')
 platform=stage/'platform/platform.dyn';s=platform.read_text().replace('pub extern fn ticks "dna_ticks"() u64','pub fn ticks()u64{return entrance_event_now}')
 s+='\nentrance_event_now:u64=1000\n'
 platform.write_text(s)
 gui=stage/'platform/gui.dyn';s=gui.read_text()
 start=s.index('  for native_gui.deferred_count!=0',s.index('fn sdl_poll('));end=s.index('\nfn sdl_wait_timeout(',start)
 s=s[:start]+'  return false\n}\n'+s[end:]
 start=s.index('fn sdl_wait_timeout(');end=s.index('\nfn sdl_wait(',start)
 s=s[:start]+'''fn sdl_wait_timeout(event:*Event,milliseconds:i32)bool {
 if sdl_poll(event) {return true}
 entrance_event_now+=8
 return false
}
'''+s[end:]
 start=s.index('fn sdl_present(');end=s.index('\nfn sdl_scale(',start)
 s=s[:start]+'''fn sdl_present(renderer:rawptr)bool {
 entrance_event_callback()
 entrance_event_now+=8
 return true
}
'''+s[end:]
 s+='\nentrance_event_callback:fn()\npub fn entrance_event_setup(callback:fn()){entrance_event_callback=callback}\n'
 gui.write_text(s)
 env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
 for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
  binary=work/'editor'
  subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
  subprocess.run([str(binary)],env=env,check=True,timeout=15)
  print(f'PASS command text entrance ({mode}): ignored text preserves split animation; genuine text inserts immediately and ends fade in actual event loop',flush=True)
