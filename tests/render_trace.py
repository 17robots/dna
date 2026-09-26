#!/usr/bin/env python3
"""Cross-check frame traces against actual SDL presents and saved input."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('render_report', ROOT/'scripts/render_report.py')
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)
probe = ROOT/'build/trace-input.so'
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'input_events', str(probe)], check=True)
for mode in ('debug', 'release'):
    with tempfile.TemporaryDirectory(prefix='dna-render-trace-') as temporary:
        folder = Path(temporary)
        target = folder/'document.txt'
        target.write_text('')
        trace = folder/'frames.jsonl'
        env = dict(os.environ, SDL_VIDEODRIVER='dummy', DNA_RECOVERY='0', DNA_CONFIG=str(folder/'config'),
                   DNA_RENDER_TRACE=str(trace), DNA_INPUT_SAVE_TEST='1', LD_PRELOAD=str(probe),
                   LD_LIBRARY_PATH=str(ROOT/'build/deps/install/lib'))
        env.pop('DYN_EDITOR_SMOKE', None)
        result = subprocess.run([str(ROOT/f'build/dna-{mode}'), str(target)], env=env, check=True, capture_output=True, text=True, timeout=10)
        presents = int(re.search(r'input burst: (\d+) frames', result.stderr)[1])
        report = reporter.summarize(trace)
        assert report['complete'] and report['frames'] == presents, (report, result.stderr)
        assert report['reasons']['startup'] == 1 and report['reasons']['text'] > 0 and report['reasons']['key'] > 0
        assert target.read_text() == 'a ' * 200
        assert report['operations']['input']['calls'] > 0
        assert report['allocations']['ui_text_cache']['allocations'] == 1
        assert report['summary']['arena_reserved'] == 0
        assert report['summary']['elapsed_us'] > 0
        assert report['summary']['main_cpu_us'] > 0
        assert report['summary']['arena_allocations'] == report['summary']['arena_releases']
        assert report['allocations']['document']['allocations'] > 0
        assert report['native_memory']['text_objects']['live_objects'] == 0
        assert report['native_memory']['text_objects']['allocations'] > 0
        assert report['wakes']
        assert report['work']['ui_hits'] > 0
        records = [json.loads(line) for line in trace.read_text().splitlines()]
        for frame in (record for record in records if record['type'] == 'frame'):
            assert frame['panes_us'] + frame['present_us'] <= frame['total_us']
        # A second launch must preserve the existing trace, not truncate it.
        before = trace.read_bytes()
        target.write_text('')
        result = subprocess.run([str(ROOT/f'build/dna-{mode}'), str(target)], env=env, check=True, capture_output=True, text=True, timeout=10)
        assert trace.read_bytes() == before and 'cannot create render trace' in result.stderr
        print(f'PASS trace matches {presents} SDL presents, attributes input, preserves existing file ({mode})')
