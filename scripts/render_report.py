#!/usr/bin/env python3
"""Summarize DNA frame traces with bounded memory; no third-party dependencies."""
import argparse
from collections import Counter
import heapq
import json
from pathlib import Path


def summarize(path, slow_us=8000):
    reasons = {}
    counts = Counter()
    work = Counter()
    operations = {}
    allocations = {}
    wakes = Counter()
    copies = Counter()
    slowest = []
    frames = 0
    slow = 0
    native_memory = {}
    summary = None
    with Path(path).open() as source:
        for line_number, line in enumerate(source, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f'Invalid/incomplete JSON at line {line_number}: {error.msg}') from error
            kind = record.get('type')
            if kind == 'schema':
                if record.get('version') != 1:
                    raise ValueError('Unsupported render trace version')
                reasons = {int(mask): name for mask, name in record['reasons'].items()}
            elif kind == 'frame':
                frames += 1
                tags = [name for mask, name in reasons.items() if record['reasons'] & mask]
                counts.update(tags)
                for field in ('total_us', 'panes_us', 'present_us', 'events', 'document_updates', 'palette_updates', 'ui_updates', 'ui_hits', 'ui_creations'):
                    work[field] += record.get(field, 0)
                elapsed = record['total_us']
                slow += elapsed >= slow_us
                heapq.heappush(slowest, (elapsed, record['frame'], record['at_us'], ','.join(tags)))
                if len(slowest) > 10:
                    heapq.heappop(slowest)
            elif kind == 'operation':
                name = record['name']
                totals = operations.setdefault(name, Counter())
                totals['calls'] += 1
                for field in ('wall_us', 'cpu_us', 'process_cpu_us'):
                    totals[field] += record.get(field, 0)
                totals['max_wall_us'] = max(totals['max_wall_us'], record['wall_us'])
            elif kind == 'wake':
                label = record['name'] + ('_event' if record['event'] else '_timeout')
                wakes[label] += 1
                wakes['wall_us'] += record['wall_us']
                wakes['main_cpu_us'] += record.get('cpu_us', 0)
                wakes['process_cpu_us'] += record.get('process_cpu_us', 0)
            elif kind == 'allocation':
                totals = allocations.setdefault(record['name'], Counter())
                if record['release']:
                    totals['releases'] += 1
                    totals['lifetime_us'] += record['lifetime_us']
                    totals['max_lifetime_us'] = max(totals['max_lifetime_us'], record['lifetime_us'])
                else:
                    totals['allocations'] += 1
                    totals['requested_bytes'] += record['bytes']
                totals['largest_bytes'] = max(totals['largest_bytes'], record['bytes'])
            elif kind == 'copy':
                copies[record['name']] += record['bytes']
            elif kind == 'native_memory':
                native_memory[record['name']] = record
            elif kind == 'summary':
                summary = record
    if not reasons:
        raise ValueError('Missing trace schema')
    complete = summary is not None and not summary['truncated'] and summary['frames'] == frames
    return dict(native_memory=native_memory, frames=frames, complete=complete, summary=summary, reasons=dict(counts),
                work=dict(work), slow_frames=slow, slowest=sorted(slowest, reverse=True),
                operations=operations, allocations=allocations, wakes=dict(wakes), copies=dict(copies))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--slow-ms', type=float, default=8)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        report = summarize(args.trace, args.slow_ms * 1000)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'{error}\n')
    if args.json:
        print(json.dumps(report, indent=2))
        return
    frames = report['frames']
    print(f"{frames} recorded frames; {'complete' if report['complete'] else 'live, truncated, or incomplete trace'}")
    if frames:
        print(f"Mean draw/present wall time: {report['work']['total_us'] / frames / 1000:.3f} ms; {report['slow_frames']} frames >= {args.slow_ms:g} ms")
    summary = report['summary']
    if summary and summary.get('elapsed_us', 0):
        elapsed = summary['elapsed_us']
        print(f"Run CPU: main {summary['main_cpu_us']/elapsed*100:.2f}%; whole process {summary['process_cpu_us']/elapsed*100:.2f}% of one core (includes tracing)")
    print('Causes (one frame can have several):')
    for name, count in sorted(report['reasons'].items(), key=lambda item: (-item[1], item[0])):
        print(f'  {name:12} {count:8}')
    print(f"Document text updates: {report['work'].get('document_updates', 0)}; palette updates: {report['work'].get('palette_updates', 0)}")
    print(f"UI cache: {report['work'].get('ui_hits', 0)} hits, {report['work'].get('ui_updates', 0)} updates, {report['work'].get('ui_creations', 0)} text objects created")
    if report['operations']:
        print('Main-thread operations (nested phases are not additive):')
        for name, values in sorted(report['operations'].items(), key=lambda item: -item[1]['cpu_us']):
            print(f"  {name:20} {values['calls']:7} calls  CPU {values['cpu_us']/1000:9.3f} ms  wall {values['wall_us']/1000:9.3f} ms  max {values['max_wall_us']/1000:7.3f} ms")
    if report['allocations']:
        print('Tracked arena reservations (not RSS or all library allocations):')
        for name, values in report['allocations'].items():
            print(f"  {name:20} {values['allocations']:6} creates  {values['releases']:6} releases  largest {values['largest_bytes']:9} bytes  max lifetime {values['max_lifetime_us']/1000000:.3f}s")
        if report['summary']:
            print(f"  Peak reserved: {report['summary'].get('arena_peak_reserved', 0)} bytes; scratch reuses: {report['summary'].get('arena_reuses', 0)}")
    if report['native_memory']:
        print('Native allocations (text-object byte sizes are opaque):')
        for name, values in report['native_memory'].items():
            print(f"  {name:20} peak {values['peak_bytes']:10} bytes; live {values['live_bytes']:10} bytes / {values['live_objects']} objects; {values['allocations']} creates, {values['releases']} releases")
    if report['wakes']:
        print('Wakeups: ' + ', '.join(f'{key}={value}' for key, value in report['wakes'].items() if not key.endswith('_us')))
        print(f"CPU during waits: main {report['wakes']['main_cpu_us']/1000:.3f} ms; whole process {report['wakes']['process_cpu_us']/1000:.3f} ms")
    if report['copies']:
        print('Copied bytes: ' + ', '.join(f'{key}={value}' for key, value in report['copies'].items()))
    print('Slowest frames:')
    for elapsed, frame, at, tags in report['slowest']:
        print(f'  #{frame:<6} at {at / 1000000:8.3f}s  {elapsed / 1000:7.3f}ms  {tags}')
    print('Timings exclude each record’s serialization/writes; process CPU includes concurrent workers. SDL present is not GPU/compositor latency.')


if __name__ == '__main__':
    main()
