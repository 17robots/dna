#!/usr/bin/env python3
"""Native popup geometry/readback tests with deterministic time."""
import os
from pathlib import Path
import shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-popup-motion-',dir=ROOT/'build') as temporary:
    work=Path(temporary);stage=work/'src';shutil.copytree(ROOT/'src',stage)
    shutil.copyfile(ROOT/'tests/editor/popup_surface_motion_smoke.dyn',stage/'popup_surface_motion_smoke.dyn')
    platform=stage/'platform/platform.dyn';s=platform.read_text().replace('pub extern fn ticks "dna_ticks"() u64','pub fn ticks()u64{return popup_probe_now}')
    s+='\npopup_probe_now:u64=1000\npub fn popup_probe_time(now:u64){popup_probe_now=now}\n';platform.write_text(s)
    gui=stage/'platform/gui.dyn';s=gui.read_text();start=s.index('fn sdl_present(');end=s.index('\nfn sdl_scale(',start)
    s=s[:start]+'fn sdl_present(renderer:rawptr)bool{return true}\n'+s[end:]
    s+='''\npub fn popup_probe_pixels()[]const u8{return native_gui.surface.pixels}
pub fn popup_probe_resize(width,height:i32){native_gui.window.width=width
 native_gui.window.height=height
 if !native_resize(){#panic("popup motion resize")}}
''';gui.write_text(s)
    if '--negative-control' in sys.argv:
        animation=stage/'animation.dyn';source=animation.read_text()
        start=source.index('fn animated_surface(');body=source.index('{',start)
        depth,end=1,body+1
        while depth:
            if source[end]=='{':depth+=1
            elif source[end]=='}':depth-=1
            end+=1
        source=source[:start]+source[start:body]+'{return target}'+source[end:]
        animation.write_text(source)
    (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer:rawptr,window:rawptr,input_storage:[]u8){
 popup_surface_motion_smoke(app,typography,renderer,window,PopupSurfaceProbe{time:sdl.popup_probe_time,pixels:sdl.popup_probe_pixels,resize:sdl.popup_probe_resize})
}
fn finish_probe(app:*App){}
''')
    env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary=work/'editor'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        if '--negative-control' in sys.argv:
            result=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30)
            assert result.returncode and 'popup opening must grow spatially' in result.stderr,result.stdout+result.stderr
            print(f'PASS popup spatial negative control ({mode}): disabled geometry detected',flush=True)
            continue
        subprocess.run([str(binary)],env=env,check=True,timeout=30)
        print(f'PASS native popup surface motion ({mode}): spatial growth, hit/cache bounds, selection, immediate input and opt-outs',flush=True)
