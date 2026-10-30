#!/usr/bin/env python3
"""Production DNA SDK clock adapter: injected clock faults and real elapsed time."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = str(Path(os.environ.get('DYN',ROOT.parent/'dyn/compiler/build/dyn-release')).resolve())
TARGETS = ('x86_64-linux','aarch64-linux','x86_64-windows','aarch64-windows','x86_64-macos','aarch64-macos')
FAULT = '''probe_clock_value: time.ClockResult
fn check_clock(ok:bool) { if !ok { #panic("native clock fault contract") } }
fn clock_value(seconds,nanoseconds:i64) {
  probe_clock_value=time.ClockResult{ok:true,value:time.Instant{seconds:seconds,nanoseconds:nanoseconds}}
}
fn main() {
  // Failure before initialization must not manufacture an origin.
  check_clock(native_elapsed_nanoseconds()==0)
  clock_value(0,0)
  check_clock(native_elapsed_nanoseconds()==0)
  clock_value(0,123)
  check_clock(native_elapsed_nanoseconds()==123)
  clock_value(0,999999)
  check_clock(native_elapsed_nanoseconds()==999999)
  check_clock(syntax_millis()==0)
  // Earlier tracing samples must not start the public millisecond epoch.
  clock_value(0,1999999)
  check_clock(native_elapsed_nanoseconds()==1999999 && dna_ticks()==0)
  clock_value(1,3)
  check_clock(native_elapsed_nanoseconds()==1000000003 && dna_ticks()==999)
  clock_value(0,999999999)
  check_clock(native_elapsed_nanoseconds()==1000000003 && dna_ticks()==999)
  probe_clock_value=time.ClockResult{}
  check_clock(native_elapsed_nanoseconds()==1000000003 && dna_ticks()==999)
  clock_value(2,9)
  check_clock(native_elapsed_nanoseconds()==2000000009 && dna_ticks()==1999)
  // Elapsed conversion overflow must retain the last successful observation.
  clock_value(9223372036854775807,0)
  check_clock(native_elapsed_nanoseconds()==2000000009 && dna_ticks()==1999)
  clock_value(3,17)
  check_clock(native_elapsed_nanoseconds()==3000000017 && dna_ticks()==2999)
}
'''
REAL = '''fn main() {
  first:=native_elapsed_nanoseconds()
  if !time.sleep(20000000).ok { #panic("native clock sleep") }
  second:=native_elapsed_nanoseconds()
  if second<first || second-first<10000000 || second-first>10000000000 {
    #panic("native clock real elapsed")
  }
  _=syntax_millis()
  if !time.sleep(2000000).ok { #panic("syntax timing sleep") }
  if dna_ticks()!=0 { #panic("native ticks independent tracing/syntax epoch") }
  if !time.sleep(2000000).ok { #panic("native ticks sleep") }
  ticks:=dna_ticks()
  if ticks<1 || ticks>10000 { #panic("native ticks relative elapsed") }
}
'''
def replace_sample(source):
    match = re.search(r'fn\s+native_clock_sample\s*\([^)]*\)[^{]*\{',source)
    if not match:
        raise AssertionError('production native_clock_sample seam missing')
    depth, end = 1, match.end()
    while depth:
        if source[end]=='{': depth+=1
        elif source[end]=='}': depth-=1
        end+=1
    return source[:match.end()]+'\n  return probe_clock_value\n'+source[end-1:]

def build(stage,output,*flags):
    subprocess.run([DYN,'build',str(stage),'--quiet','--no-cache',*flags,'--output',str(output)],check=True,timeout=120)

source = (ROOT/'src/native/dyn/clock.dyn').read_text()
syntax = (ROOT/'src/native/dyn/syntax.dyn').read_text()
syntax_helper = syntax[syntax.index('fn syntax_millis()'):syntax.index('fn syntax_progress(')]
with tempfile.TemporaryDirectory(prefix='dna-native-clock-') as directory:
    work=Path(directory)
    for name,adapter,probe in (('fault',replace_sample(source),FAULT),('real',source,REAL)):
        stage=work/name
        stage.mkdir()
        (stage/'clock.dyn').write_text(adapter)
        (stage/'main.dyn').write_text(syntax_helper+probe)
        for mode in ('debug','release'):
            output=work/(name+'-'+mode)
            build(stage,output,'--'+mode)
            subprocess.run([str(output)],check=True,timeout=15)
        print('PASS native clock '+name+' production adapter (debug/release)',flush=True)
    for target in TARGETS:
        build(work/'real',work/target,'--release','--target',target,'--emit-object','--no-link')
        print('PASS native clock desktop object: '+target,flush=True)
print('QUALIFICATION GAP: cross objects do not qualify native Windows/macOS clock runtime')
