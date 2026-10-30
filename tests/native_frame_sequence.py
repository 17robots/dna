#!/usr/bin/env python3
"""Repeated native uploads/swaps: exact GPU frames after typing-like CPU edits.

Readback verifies the complete backbuffer before swap; post-swap backbuffer
contents are undefined and are deliberately not asserted. This qualifies the
presenter and framebuffer reuse, not physical scanout or compositor visibility.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=r'''use "vendor/window/wayland" window_api
use "vendor/window/events"
use "std/ui/software"
use "std/mem"
use "./presenter" presenter
#link("c")
extern fn sequence_compare "memcmp"(first:*const u8,second:*const u8,length:usize)i32
fn check(ok:bool,message:[]const u8) {if !ok {#panic(message)}}
fn verify(renderer:*presenter.Presenter,surface:software.Surface,readback:[]u8) {
 renderer.api.pixel_store_i(3333,1)
 renderer.api.pixel_store_i(3330,0)
 renderer.api.pixel_store_i(3331,0)
 renderer.api.pixel_store_i(3332,0)
 renderer.api.read_pixels(0,0,surface.width,surface.height,6408,5121,#cast(rawptr,&readback[0]))
 check(renderer.api.get_error()==0,"sequence readback GL error")
 for y in 0..surface.height {
  from:=#cast(usize,y)*surface.stride
  to:=#cast(usize,surface.height-1-y)*surface.stride
  check(sequence_compare(&surface.pixels[from],&readback[to],surface.stride)==0,"sequence complete GPU frame differs from CPU framebuffer")
 }
}
fn main() {
 host:=window_api.Window{}
 check(window_api.open(&host,"DNA native frame sequence",320,160).ok,"sequence window")
 defer window_api.close(&host)
 window_api.listen_events(&host,true)
 _=window_api.set_swap_interval(&host,0)
 renderer:=presenter.Presenter{}
 check(presenter.open(&renderer).ok,"sequence presenter")
 defer presenter.close(&renderer)
 owner:=mem.arena_create(0)
 defer mem.arena_release(owner)
 max_width:=host.width
 max_height:=host.height
 check(max_width>0 && max_height>0,"sequence dimensions")
 pixels:=mem.push_bytes_uninit(owner,#cast(usize,max_width)*#cast(usize,max_height)*4)
 readback:=mem.push_bytes_uninit(owner,#len(pixels))
 // A stable background and glyph-like stripes make a lost text row or whole
 // pane visible to the exact comparison. Only a small region changes per frame.
 for y in 0..max_height {
  for x in 0..max_width {
   at:=(#cast(usize,y)*#cast(usize,max_width)+#cast(usize,x))*4
   value:u8=19
   if y%16<11 && x%8<3 {value=221}
   pixels[at]=value
   pixels[at+1]=value
   pixels[at+2]=value
   pixels[at+3]=255
  }
 }
 for frame in 0..FRAME_COUNT {
  check(window_api.poll(&host).ok,"sequence event poll")
  event:=events.Event{}
  for window_api.next_event(&host,&event) {}
  // Keep CPU memory allocated and reuse it immediately after prior swap.
  at:=(#cast(usize,frame)%#cast(usize,max_height))*#cast(usize,max_width)*4
  for x in 0..max_width {
   offset:=at+#cast(usize,x)*4
   pixels[offset]=#cast(u8,(frame*17+#cast(usize,x))%256)
   pixels[offset+1]=#cast(u8,(frame*31+#cast(usize,x))%256)
   pixels[offset+2]=#cast(u8,(frame*43+#cast(usize,x))%256)
   pixels[offset+3]=255
  }
  // Alternating smaller uploads exercise texture reallocations and restore.
  width:=max_width
  height:=max_height
  if frame%37==19 {width=max_width/2
   height=max_height/2}
  length:=#cast(usize,width)*#cast(usize,height)*4
  surface:=software.Surface{pixels:pixels[..length],width:width,height:height,stride:#cast(usize,width)*4}
  check(presenter.draw(&renderer,surface).ok,"sequence upload")
  verify(&renderer,surface,readback[..length])
  check(window_api.swap(&host).ok,"sequence swap")
  if frame%53==27 {
   presenter.close(&renderer)
   check(presenter.open(&renderer).ok,"sequence recreate")
  }
 }
}
'''
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--frames',type=int,default=128)
parser.add_argument('--modes',nargs='+',choices=('debug','release'),default=['debug','release'])
parser.add_argument('--on-current-compositor',action='store_true',help='Skip private compositor wrapper')
args=parser.parse_args()
if not 1<=args.frames<=2000:raise SystemExit('--frames must be 1..2000')
compiler=Path(os.environ.get('DYN',ROOT.parent/'dyn/compiler/build/dyn-release')).resolve()
with tempfile.TemporaryDirectory(prefix='dna-frame-sequence-') as directory:
 work=Path(directory);stage=work/'probe';stage.mkdir()
 shutil.copytree(ROOT/'src/platform/native_present',stage/'presenter')
 (stage/'main.dyn').write_text(FIXTURE.replace('FRAME_COUNT',str(args.frames)))
 library=ROOT/'build/deps/install/lib'
 env=dict(os.environ,DYN_LIBRARY_PATH=str(library),LD_LIBRARY_PATH=str(library))
 runner=ROOT/'tests/wayland_runner.py'
 for mode in args.modes:
  binary=work/mode
  subprocess.run(['python3',str(ROOT/'scripts/compile.py'),str(compiler),'build',str(stage),'--'+mode,'--output',str(binary),'--link','-rpath='+str(library)],env=env,check=True,timeout=120)
  command=[str(binary)]
  if not args.on_current_compositor and not env.get('DNA_TEST_WAYLAND_INPUT'):
   command=[sys.executable,str(runner),'--timeout',str(max(120,args.frames*3)),'--run',*command]
  subprocess.run(command,env=env,check=True,timeout=max(180,args.frames*3+30))
  print(f'PASS native frame sequence ({mode}): {args.frames} exact complete GPU frames, swaps, storage resize/recreate',flush=True)
