#!/usr/bin/env python3
"""Real native spatial pane/split/dock motion with deterministic time/readback."""
import os
from pathlib import Path
import shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dna-panel-geometry-',dir=ROOT/'build') as temporary:
    work=Path(temporary);stage=work/'src';shutil.copytree(ROOT/'src',stage)
    shutil.copyfile(ROOT/'tests/editor/surface_entrance_smoke.dyn',stage/'surface_entrance_smoke.dyn')
    platform=stage/'platform/platform.dyn';s=platform.read_text().replace('pub extern fn ticks "dna_ticks"() u64','pub fn ticks()u64{return geometry_probe_now}')
    s+='\ngeometry_probe_now:u64=1000\npub fn geometry_probe_time(now:u64){geometry_probe_now=now}\n';platform.write_text(s)
    gui=stage/'platform/gui.dyn';s=gui.read_text();start=s.index('fn sdl_present(');end=s.index('\nfn sdl_scale(',start)
    s=s[:start]+'fn sdl_present(renderer:rawptr)bool{return true}\n'+s[end:]
    s+='''\npub fn geometry_probe_pixels()[]const u8{return native_gui.surface.pixels}
pub fn geometry_probe_resize(width,height:i32){native_gui.window.width=width
 native_gui.window.height=height
 if !native_resize(){#panic("geometry resize")}}
''';gui.write_text(s)
    if '--negative-control' in sys.argv:
        view=stage/'view.dyn';s=view.read_text().replace('  pane_animate_layout(app, 0)','  app.view.animation.resized=true\n  pane_animate_layout(app, 0)');view.write_text(s)
    (stage/'startup_probe.dyn').write_text('''fn startup_probe(app:*App,typography:*Typography,renderer:rawptr,window:rawptr,input_storage:[]u8){
 surface_entrance_smoke(app,typography,renderer,window,SurfaceEntranceProbe{time:sdl.geometry_probe_time,pixels:sdl.geometry_probe_pixels,resize:sdl.geometry_probe_resize})
}
fn finish_probe(app:*App){}
''')
    env=dict(os.environ,DYN_EDITOR_SMOKE='1',DNA_DEFAULT_SERVERS='0',DNA_RECOVERY='0',DNA_CONFIG=str(work/'missing.toml'),XDG_CONFIG_HOME=str(work/'config'),XDG_STATE_HOME=str(work/'state'))
    for mode in os.environ.get('DNA_SMOKE_MODES','debug release').split():
        binary=work/'editor'
        subprocess.run([sys.executable,str(ROOT/'scripts/build_native.py'),'--source',str(stage),'--mode',mode,'--output',str(binary)],check=True,stdout=subprocess.DEVNULL)
        if '--negative-control' in sys.argv:
            result=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30)
            assert result.returncode and 'split must grow spatially' in result.stderr,result.stdout+result.stderr
            print(f'PASS spatial panel negative control ({mode}): disabled geometry is detected',flush=True)
        else:
            subprocess.run([str(binary)],env=env,check=True,timeout=30)
            print(f'PASS native panel geometry ({mode}): split/close motion, shared boundaries, camera, immediate input, four dock sides and settled pixels',flush=True)
