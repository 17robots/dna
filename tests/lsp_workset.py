#!/usr/bin/env python3
"""Real-peer LSP protocol plus fixture-only instrumentation of visited records."""
import argparse
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
DYN=os.environ.get('DYN',str(ROOT.parent/'dyn/compiler/build/dyn-release'))
def function(source,name):
    start=source.index('fn '+name+'(');body=source.index('{',start);depth,end=1,body+1
    quote=None
    while depth:
        if quote:
            if source[end]=='\\':end+=2;continue
            if source[end]==quote:quote=None
        elif source.startswith('//',end):
            end=source.index('\n',end)
            continue
        elif source[end] in ('"',"'"):quote=source[end]
        elif source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return start,end,source[start:end]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline',type=Path,help='old language_server.dyn; must fail the 0/1 visit contract')
args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='dna-lsp-workset-') as directory:
    work=Path(directory);stage=work/'editor'
    shutil.copytree(ROOT/'src',stage)
    main=stage/'main.dyn'
    main.write_text(main.read_text().replace('fn main() {','fn unused_editor_entry() {',1)+'\n'+(ROOT/'tests/lsp_workset/main.dyn').read_text())
    lsp=stage/'language_server.dyn';source=lsp.read_text()
    if args.baseline:
        baseline=args.baseline.read_text()
        for name in ('lsp_sync','lsp_wait_ms'):
            start,end,_=function(source,name)
            source=source[:start]+function(baseline,name)[2]+source[end:]
        start,end,body=function(source,'lsp_sync')
        needle='    slot := app.documents.slots[slot_index]'
        assert needle in body
        body=body.replace(needle,'    workset_visits+=1\n'+needle,1)
        source=source[:start]+body+source[end:]
    else:
        start,end,body=function(source,'lsp_sync_slot')
        body=body.replace('{','{\n    workset_visits+=1',1)
        source=source[:start]+body+source[end:]
    lsp.write_text(source)
    env=dict(os.environ,DYN_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'),LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'),DNA_WORKSET_DIR=str(work),DNA_WORKSET_LSP='python3 '+str(ROOT/'tests/fake_lsp.py'))
    for mode in ('debug','release'):
        binary=work/('probe-'+mode)
        subprocess.run(['python3',str(ROOT/'scripts/compile.py'),DYN,'build',str(stage),'--'+mode,'--output',str(binary)],env=env,check=True,timeout=120)
        result=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=20)
        print(result.stderr,end='',flush=True)
        if args.baseline:
            idle=re.search(r'LSP idle record visits: (\d+)',result.stderr)
            edited=re.search(r'LSP single-edit record visits: (\d+)',result.stderr)
            assert result.returncode!=0 and idle and edited and int(idle[1])>0 and int(edited[1])>1,result.stderr
            print('PASS red baseline exposes record polling: '+mode,flush=True)
        else:
            assert result.returncode==0,result.stderr
            print('PASS targeted LSP protocol/workset lifecycle: '+mode,flush=True)
