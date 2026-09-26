#!/usr/bin/env python3
"""Launch the normal editor, wait for real Dyn diagnostics, hover the underline."""
import os
from pathlib import Path
import subprocess
import tempfile
import sys as _sys
_sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'scripts'))
from dyn_path import with_real_dyn
ROOT = Path(__file__).resolve().parents[1]
probe = ROOT/'build/diagnostic-render.so'
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'diagnostic_render', str(probe)], check=True)
with tempfile.TemporaryDirectory(prefix='dna-diagnostic-render-') as temporary:
    root=Path(temporary);source=root/'platform.dyn'
    source.write_text((ROOT/'src/platform/platform.dyn').read_text()+'\nffefefefefefe\n')
    config=root/'config.toml';config.write_text('reduced_motion = true\n')
    env=with_real_dyn(dict(os.environ,SDL_VIDEODRIVER='dummy',DNA_CONFIG=str(config),LD_PRELOAD=str(probe),LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'),XDG_CONFIG_HOME=str(root/'config')))
    env.pop('DYN_EDITOR_SMOKE',None)
    subprocess.run([str(ROOT/'build/dna-debug'),str(source)],cwd=root,env=env,check=True,timeout=12)
