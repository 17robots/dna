#!/usr/bin/env python3
"""Bounded trace quantiles, latency population and backward compatibility."""
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('render_report', ROOT/'scripts/render_report.py')
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)
with tempfile.TemporaryDirectory(prefix='dna-latency-report-') as temporary:
    path = Path(temporary)/'trace.jsonl'
    rows = [dict(type='schema', version=1, reasons={'2': 'key'})]
    for index in range(1, 101):
        rows.append(dict(type='frame', frame=index, at_us=index*100000, reasons=2,
                         total_us=index*1000, dequeue_to_present_us=index*1000,
                         latest_input_to_present_us=index*100, animation_interval_us=16667,
                         refresh_budget_us=16667, late_animation_interval=int(index > 95)))
    path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')
    report = reporter.summarize(path)
    latency = report['input_latency']
    assert latency['n'] == 100 and latency['max_us'] == 100000
    for percentile in (50, 95, 99):
        result = latency[f'p{percentile}_us']
        exact = percentile*1000
        assert result <= exact < result+max(1, exact/64), (percentile, result, exact)
    assert report['latest_input_latency']['max_us'] == 10000
    assert report['known_refresh_intervals'] == 100 and report['late_animation_intervals'] == 5
    for row in rows[1:]:
        for key in ('dequeue_to_present_us', 'latest_input_to_present_us', 'animation_interval_us', 'refresh_budget_us', 'late_animation_interval'):
            row.pop(key)
    path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')
    old = reporter.summarize(path)
    assert old['frames'] == 100 and old['input_latency']['n'] == 0
    assert old['frame_times']['max_us'] == 100000
histogram = reporter.TimingHistogram()
for exponent in range(64):
    for mantissa in range(128):
        histogram.add(min((1 << 64)-1, (128+mantissa) << exponent))
assert len(histogram.buckets) <= 64*128
assert histogram.report()['max_us'] == (1 << 64)-1
print('PASS bounded latency/frame quantiles, coalesced populations, late intervals and legacy traces')
