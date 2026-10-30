#!/usr/bin/env python3
"""Measure warm production CPU drawing at fixed sizes, excluding GPU/presentation.

Requires a native desktop session and the development SDK. An isolated staged
build replaces only presentation and the startup probe; it draws real document
and picker code. Results are CPU component measurements, not input/display
latency. Run without concurrent builds or other benchmarks.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''fn startup_probe(app:*App, typography:*Typography, renderer:rawptr, window:rawptr, input_storage:[]u8) {
 sample:[64000]u8=[]
 used:usize=0
 for row in 0..400 {
  text:="fn example() { sample := 1234; value := sample + 17 }\n"
  used+=copy_text(sample[used..],text)
 }
 _=buffer.load(app.documents.current,sample[..used])
 app.view.reduced_motion=true
 PICKER_SETUP
 for size in 0..3 {
  width:i32=960
  height:i32=640
  if size==1 {width=1920
   height=1080}
  if size==2 {width=2560
   height=1440}
  sdl.frame_probe_size(width,height)
  for frame in 0..SAMPLE_COUNT {
   buffer.move_to(app.documents.current,frame%20*100,false)
   cpu_started:=frame_probe_cpu()
   started:=render_clock()
   draw(renderer,window,app,typography)
   elapsed:=(render_clock()-started)/1000
   cpu_elapsed:=(frame_probe_cpu()-cpu_started)/1000
   if frame>=5 {
    output:[128]u8=[]
    at:usize=0
    add_number(output[..],&at,#cast(usize,width))
    add_text(output[..],&at," ")
    add_number(output[..],&at,#cast(usize,elapsed))
    add_text(output[..],&at," ")
    add_number(output[..],&at,#cast(usize,cpu_elapsed))
    add_text(output[..],&at,"\n")
    _=#syscall(1,1,&output[0],at)
   }
  }
 }
 app.running=false
}
fn finish_probe(app:*App) {}
fn frame_probe_cpu() u64 {
 time:=ThreadTime{}
 if thread_clock(3,&time)!=0 {#panic("thread CPU clock")}
 return #cast(u64,time.seconds)*1000000000+#cast(u64,time.nanoseconds)
}
'''
PICKER = '''app.prompt_state.panel=Panel.Open
 app.completion.count=64
 for row in 0..64 {
  entry:=&app.completion.entries[row]
  entry.length=0
  add_text(entry.name[..],&entry.length,"src/native_example_")
  add_number(entry.name[..],&entry.length,row)
  add_text(entry.name[..],&entry.length,".dyn")
 }'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--components', action='store_true', help='Record pane, popup paint, and composite wall times')
    parser.add_argument('--scenario', choices=('document', 'picker'), default='picker')
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--ui-cache', type=Path, help='Optional previous UI cache source for a paired comparison')
    parser.add_argument('--renderer', type=Path, default=ROOT/'src/platform/gui.dyn')
    parser.add_argument('--output', type=Path, default=ROOT/'build/native-frame-cost.json')
    parser.add_argument('--cpu', type=int, help='Pin the measured child to one allowed logical CPU')
    parser.add_argument('--budget-ms', type=float, help='Optional local p95 CPU budget; hardware dependent')
    args = parser.parse_args()
    if not 5 <= args.samples <= 1000:
        parser.error('--samples must be between 5 and 1000')
    (ROOT/'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='native-frame-', dir=ROOT/'build') as directory:
        work = Path(directory)
        stage = work/'src'
        shutil.copytree(ROOT/'src', stage)
        if args.ui_cache:
            shutil.copyfile(args.ui_cache, stage/'ui_cache.dyn')
        original = args.renderer.read_text()
        start = original.index('fn sdl_present(')
        end = original.index('\nfn sdl_scale(', start)
        renderer = original[:start]+'fn sdl_present(renderer:rawptr) bool { return true }\n'+original[end:]
        renderer += '''\npub fn frame_probe_size(width,height:i32) {
 native_gui.window.width=width
 native_gui.window.height=height
 if !native_resize() {#panic("probe surface resize")}
}\n'''
        (stage/'platform/gui.dyn').write_text(renderer)
        (stage/'startup_probe.dyn').write_text(PROBE.replace('PICKER_SETUP', PICKER if args.scenario=='picker' else '').replace('SAMPLE_COUNT', str(args.samples+5)))
        if args.components:
            view=stage/'view.dyn'
            text=view.read_text().replace('  if popup_shown(app) {','  probe_started:=render_clock()\n  if popup_shown(app) {',1)
            text=text.replace('  if app.prompt_state.panel == Panel.Terminal {','  probe_begun:=render_clock()\n  if app.prompt_state.panel == Panel.Terminal {',1)
            text=text.replace('  popup_present(renderer, app)','  probe_painted:=render_clock()\n  popup_present(renderer, app)\n  frame_probe_components(probe_begun-probe_started,probe_painted-probe_begun,render_clock()-probe_painted)',1)
            view.write_text(text)
            probe=stage/'startup_probe.dyn'
            probe.write_text(probe.read_text()+r'''
fn frame_probe_components(begin,paint,composite:u64) {
 output:[128]u8=[]
 at:usize=0
 add_text(output[..],&at,"P ")
 add_number(output[..],&at,#cast(usize,begin/1000))
 add_text(output[..],&at," ")
 add_number(output[..],&at,#cast(usize,paint/1000))
 add_text(output[..],&at," ")
 add_number(output[..],&at,#cast(usize,composite/1000))
 add_text(output[..],&at,"\n")
 _=#syscall(1,1,&output[0],at)
}
''')
        with (work/'build.log').open('w') as log:
            build = subprocess.run([sys.executable, str(ROOT/'scripts/build_native.py'), '--source', str(stage), '--mode', 'release', '--output', str(work/'editor')], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        if build.returncode:
            raise SystemExit((work/'build.log').read_text())
        environment = {key:value for key,value in os.environ.items() if not key.startswith('DNA_')}
        environment.update(DYN_EDITOR_SMOKE='1', DNA_VSYNC='0', DNA_DEFAULT_SERVERS='0', DNA_RECOVERY='0', DNA_CONFIG=str(work/'missing.toml'), XDG_CONFIG_HOME=str(work/'config'), XDG_STATE_HOME=str(work/'state'))
        run = subprocess.run([str(work/'editor')], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=120, preexec_fn=(lambda: os.sched_setaffinity(0, {args.cpu})) if args.cpu is not None else None)
        if run.returncode:
            raise SystemExit(run.stdout+run.stderr)
        if args.components:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.with_suffix('.raw.log').write_text(run.stdout)
        rows = {}
        cpu_rows = {}
        for line in run.stdout.splitlines():
            fields = line.split()
            if len(fields)==3 and all(x.isdigit() for x in fields):
                rows.setdefault(fields[0], []).append(int(fields[1])/1000)
                cpu_rows.setdefault(fields[0], []).append(int(fields[2])/1000)
        if len(rows)!=3 or any(len(v)!=args.samples for v in rows.values()):
            raise SystemExit('Incomplete frame samples: '+run.stdout)
        report = {'scenario':args.scenario, 'mode':'release', 'ui_cache_sha256':hashlib.sha256((stage/'ui_cache.dyn').read_bytes()).hexdigest(), 'logical_cpu':args.cpu, 'renderer_sha256':hashlib.sha256(original.encode()).hexdigest(), 'scope':'Warm CPU drawing only; fixed 400-line document and 64-row picker; excludes scanning, GPU, compositor, and physical input/display latency.', 'resolutions':{w:{'samples_ms':values, 'cpu_samples_ms':cpu_rows[w], 'cpu_p50_ms':statistics.median(cpu_rows[w]), 'cpu_p95_ms':sorted(cpu_rows[w])[(95*len(values)+99)//100-1], 'p50_ms':statistics.median(values), 'p95_ms':sorted(values)[(95*len(values)+99)//100-1]} for w,values in rows.items()}}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({w:{k:v for k,v in r.items() if not k.endswith('samples_ms')} for w,r in report['resolutions'].items()}, indent=2))
        if args.budget_ms is not None and any(r['p95_ms']>args.budget_ms for r in report['resolutions'].values()):
            raise SystemExit('FAIL warm CPU draw exceeds local frame budget')

if __name__ == '__main__':
    main()
