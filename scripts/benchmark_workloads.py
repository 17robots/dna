#!/usr/bin/env python3
"""Benchmark hard DNA terminal workloads at acknowledged screen changes.

All fixtures/settings are temporary. No product source or personal settings are
modified. Run each immutable release binary separately with the same arguments;
JSON retains raw samples and binary/fixture hashes for paired comparisons.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import signal
import statistics
import sys
import tempfile
import time

from benchmark_editors import Session

ROOT = Path(__file__).resolve().parents[1]
WORKLOADS = ('large-1m', 'large-10m', 'large-100m', 'unicode-long', 'multiselect', 'lsp')
ESCAPE = b'\x1b[27u'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def summarize(values):
    if not values:
        return {'samples': 0}
    ordered = sorted(values)
    return {'samples': len(values), 'median_ms': statistics.median(values),
            'p95_ms': ordered[math.ceil(.95*len(values))-1],
            'p99_ms': ordered[math.ceil(.99*len(values))-1], 'max_ms': max(values)}


def descendants(pid):
    found = set()
    pending = [pid]
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        try:
            for task in Path(f'/proc/{current}/task').iterdir():
                pending.extend(map(int, (task/'children').read_text().split()))
        except (FileNotFoundError, ProcessLookupError):
            pass
    return found


def usage(pid):
    cpu_ticks = minor = major = rss = pss = dirty = 0
    live = []
    for current in sorted(descendants(pid)):
        try:
            stat = Path(f'/proc/{current}/stat').read_text().rsplit(')', 1)[1].split()
            fields = {line.split(':')[0]: line.split(':')[1].strip()
                      for line in Path(f'/proc/{current}/smaps_rollup').read_text().splitlines()
                      if ':' in line}
            cpu_ticks += int(stat[11])+int(stat[12])
            minor += int(stat[7]); major += int(stat[9])
            rss += int(fields['Rss'].split()[0]); pss += int(fields['Pss'].split()[0])
            dirty += int(fields['Private_Dirty'].split()[0]); live.append(current)
        except (FileNotFoundError, ProcessLookupError):
            pass
    return {'pids': live, 'cpu_ticks': cpu_ticks, 'minor_faults': minor, 'major_faults': major,
            'rss_kib': rss, 'pss_kib': pss, 'private_dirty_kib': dirty}


def close(session):
    # Native LSP/process transports may own another process group. Terminate
    # only descendants created for this temporary editor before killing it.
    for child in sorted(descendants(session.pid)-{session.pid}, reverse=True):
        try:
            if os.getpgid(child) == child:
                os.killpg(child, signal.SIGKILL)
            else:
                os.kill(child, signal.SIGKILL)
        except ProcessLookupError:
            pass
    session.close()


def rows(session):
    return tuple(re.findall(r'ROW\d{7}', session.text()))


def document_mode(session):
    for line in reversed(session.text().splitlines()):
        match = re.match(r'\s*(NORMAL|INSERT|SELECT)\s', line)
        if match:
            return match[1]
    return None


def document_position(session):
    for line in reversed(session.text().splitlines()):
        if line.lstrip().startswith(('NORMAL ', 'INSERT ', 'SELECT ')):
            matches = re.findall(r'\b(\d+):(\d+)\b', line)
            if matches:
                return tuple(map(int, matches[-1]))
    return None


def contiguous_rows(values):
    numbers = [int(value[3:]) for value in values]
    return bool(numbers) and all(b == a+1 for a, b in zip(numbers, numbers[1:]))


def wait_peer(session, log, method, count, timeout):
    def observed():
        return sum(event.get('method') == method for event in peer_events(log)) >= count
    session.wait(observed, timeout=timeout)


def peer_events(log):
    if not log.exists():
        return []
    events = []
    for line in log.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # A concurrent append may not yet contain its newline.
    return events


def command(session, text, predicate, timeout):
    # Ordered bytes reach the real parser. Only the predicate acknowledges
    # completion; no sleep is substituted for a screen/file response.
    session.send(b':', lambda: 'Type a command' in session.text(), timeout)
    return session.send(text.encode()+b'\r', predicate, timeout)


def write_large(path, size):
    start = b'BENCH_START\n'
    end = b'BENCH_END\n'
    with path.open('wb') as stream:
        stream.write(start)
        row = 0
        while stream.tell()+75+len(end) < size:
            batch = []
            batch_bytes = 0
            for _ in range(4096):
                line = f'ROW{row:07} abcdefghijklmnopqrstuvwxyz 0123456789 text for paging\n'.encode()
                if stream.tell()+batch_bytes+len(line)+len(end) > size:
                    break
                batch.append(line); batch_bytes += len(line); row += 1
            if not batch:
                break
            stream.write(b''.join(batch))
        remaining = size-stream.tell()-len(end)
        stream.write(b'a'*remaining)
        stream.write(end)


def fixture(workload, directory):
    path = directory/('input.dyn' if workload == 'lsp' else 'input.txt')
    if workload.startswith('large-'):
        amount = int(workload.split('-')[1][:-1])*1024*1024
        write_large(path, amount)
    elif workload == 'unicode-long':
        path.write_text('BENCH_START '+('é中 e\u0301 אבג العربية 😀 '*4096)+' BENCH_END')
    elif workload == 'multiselect':
        path.write_text('BENCH_START\n'+''.join(f'needle item {i:02}\n' for i in range(16))+'BENCH_END\n')
    else:
        path.write_text('BENCH_START value\n// deterministic active LSP workload\n')
    return path


def environment(directory, lsp):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('DNA_', 'DYN_EDITOR_')) and key != 'LD_PRELOAD'}
    config = directory/'config.toml'
    config.write_text('reduced_motion = true\nrelative_numbers = false\n'
                      'automatic_completion = false\nreload_config = false\n')
    if lsp:
        peer = ROOT/'tests/fixtures/benchmark_lsp.py'
        server = shlex.join([sys.executable, str(peer), str(directory/'lsp-events.jsonl')])
        with config.open('a') as stream:
            stream.write('\n[languages.dyn]\nserver = '+json.dumps(server)+'\nauto_start = true\n')
    for name in ('home', 'config', 'state', 'cache'):
        (directory/name).mkdir()
    env.update(HOME=str(directory/'home'), XDG_CONFIG_HOME=str(directory/'config'),
               XDG_STATE_HOME=str(directory/'state'), XDG_CACHE_HOME=str(directory/'cache'),
               DNA_CONFIG=str(config), DNA_DEFAULT_SERVERS='0', DNA_RECOVERY='0', DNA_DYN_LSP='',
               DNA_LANGUAGE_DIR=str(ROOT/'build/test-languages'), TERM='xterm-256color', COLORTERM='truecolor')
    return env


def edit_samples(session, count, timeout, selected=1, lsp_log=None):
    if selected == 1:
        inserted = lambda: 'xBENCH_START' in session.text()
        erased = lambda: 'BENCH_START' in session.text() and 'xBENCH_START' not in session.text()
    else:
        inserted = lambda: session.text().count('xneedle') == selected
        erased = lambda: session.text().count('needle') == selected and 'xneedle' not in session.text()
    session.send(b'i', lambda: document_mode(session) == 'INSERT', timeout)
    # Warm mode transition and first edit, still acknowledged by actual text.
    session.send(b'x', inserted, timeout)
    session.send(b'\x7f', erased, timeout)
    insert = []; erase = []; complete = []
    for index in range(count):
        before_changes = sum(e.get('method') == 'textDocument/didChange' for e in peer_events(lsp_log)) if lsp_log else 0
        insert.append(session.send(b'x', inserted, timeout))
        if lsp_log:
            wait_peer(session, lsp_log, 'textDocument/didChange', before_changes+1, timeout)
            before = sum(e.get('method') == 'textDocument/completion' for e in peer_events(lsp_log))
            marker = f'bench_complete_{before+1:04}'
            complete.append(session.send(b'\0', lambda: marker in session.text(), timeout))
            session.send(ESCAPE, lambda: marker not in session.text(), timeout)
        before_changes = sum(e.get('method') == 'textDocument/didChange' for e in peer_events(lsp_log)) if lsp_log else 0
        erase.append(session.send(b'\x7f', erased, timeout))
        if lsp_log:
            wait_peer(session, lsp_log, 'textDocument/didChange', before_changes+1, timeout)
    session.send(ESCAPE, lambda: document_mode(session) == 'NORMAL', timeout)
    return {'insert': insert, 'backspace': erase, **({'completion': complete} if lsp_log else {})}


def trial(binary, workload, samples, timeout, directory):
    path = fixture(workload, directory)
    original = path.read_bytes() if workload == 'multiselect' else None
    env = environment(directory, workload == 'lsp')
    session = Session([str(binary), '--tui', str(path)], env, directory)
    canonical_config = (directory/'config.toml').read_text().replace(str(directory), '$BENCH_DIR')
    result = {'workload': workload, 'fixture_bytes': path.stat().st_size,
              'fixture_sha256': digest(path),
              'config_sha256': hashlib.sha256(canonical_config.encode()).hexdigest(),
              'config_hash_scope': 'temporary directory normalized to $BENCH_DIR',
              'phase_memory': {}}
    before = None
    wall = None
    try:
        result['stage'] = 'startup'
        result['startup_ms'] = session.wait(lambda: 'BENCH_START' in session.text(), session.started, timeout)
        if workload == 'lsp':
            wait_peer(session, directory/'lsp-events.jsonl', 'textDocument/didOpen', 1, timeout)
        result['phase_memory']['opened'] = usage(session.pid)
        before = usage(session.pid); wall = time.monotonic()
        result['stage'] = 'editing'
        if workload == 'multiselect':
            session.send(b'gg%s', lambda: 'select:' in session.text(), timeout)
            session.send(b'needle', lambda: 'select: needle' in session.text(), timeout)
            session.send(b'\r', lambda: 'select:' not in session.text(), timeout)
            raw = edit_samples(session, samples, timeout, selected=16)
            # Verify all selections through the real save path, not only color
            # or status text. One undo must restore the original document.
            session.send(b'i', lambda: document_mode(session) == 'INSERT', timeout)
            session.send(b'Z', lambda: session.text().count('Zneedle') == 16, timeout)
            session.send(ESCAPE, lambda: document_mode(session) == 'NORMAL', timeout)
            expected = original.replace(b'needle', b'Zneedle')
            command(session, 'write', lambda: path.read_bytes() == expected, timeout)
            session.send(b'u', lambda: 'Zneedle' not in session.text(), timeout)
            command(session, 'write', lambda: path.read_bytes() == original, timeout)
            result['multiselect_saved_exactly'] = True
            result['undo_restored_exactly'] = True
        else:
            raw = edit_samples(session, samples, timeout,
                               lsp_log=directory/'lsp-events.jsonl' if workload == 'lsp' else None)
        result['raw_ms'] = raw
        result['phase_memory']['edited'] = usage(session.pid)
        edited = result['phase_memory']['edited']
        stable_edit_tree = before['pids'] == edited['pids']
        result['editing_cpu_seconds'] = ((edited['cpu_ticks']-before['cpu_ticks'])/os.sysconf('SC_CLK_TCK')) if stable_edit_tree else None
        result['editing_wall_seconds'] = time.monotonic()-wall
        result['editing_minor_faults'] = edited['minor_faults']-before['minor_faults'] if stable_edit_tree else None
        result['editing_major_faults'] = edited['major_faults']-before['major_faults'] if stable_edit_tree else None
        if workload.startswith('large-'):
            result['stage'] = 'paging'
            scrolling = []
            base_rows, base_position = rows(session), document_position(session)
            if not base_rows or base_position is None:
                raise RuntimeError('paging fixture has no row/status acknowledgment')
            result['paging_base_position'] = base_position
            result['paging_base_rows'] = base_rows
            for index in range(samples):
                result['paging_step'] = index
                # A page key moves twenty document rows. Two keys guarantee
                # viewport movement in the fixed 32-row terminal, avoiding
                # no-op timing while the cursor is still inside the viewport.
                down = index % 2 == 0
                key = (b'\x1b[6~' if down else b'\x1b[5~')*2
                def acknowledged(down=down):
                    current, position = rows(session), document_position(session)
                    if position is None or not contiguous_rows(current):
                        return False
                    if down:
                        return position[0] > base_position[0] and current != base_rows
                    # Normal-mode paging can turn an empty caret into a
                    # one-cell selection. Its end column changes legitimately;
                    # the document row and complete viewport are the endpoint.
                    return position[0] == base_position[0] and current == base_rows
                scrolling.append(session.send(key, acknowledged, timeout))
            result['paging_keys_per_action'] = 2
            raw['paging'] = scrolling
        if workload == 'unicode-long':
            result['stage'] = 'unicode-jumps'
            jumps = []
            for _ in range(samples):
                jumps.append(session.send(b'ge', lambda: 'BENCH_END' in session.text(), timeout))
                jumps.append(session.send(b'gg', lambda: 'BENCH_START' in session.text(), timeout))
            raw['line_end_start'] = jumps
        if workload == 'lsp':
            events = peer_events(directory/'lsp-events.jsonl')
            counts = {method: sum(e.get('method') == method for e in events)
                      for method in ('initialize', 'initialized', 'textDocument/didOpen',
                                     'textDocument/didChange', 'textDocument/completion')}
            if counts['textDocument/completion'] != samples or counts['textDocument/didChange'] < samples*2:
                raise RuntimeError('active LSP traffic not proven: '+str(counts))
            result['lsp_methods'] = counts
            result['lsp_diagnostics_sent'] = sum(e.get('event') == 'diagnostic' for e in events)
            result['lsp_peer_log'] = events
        after = usage(session.pid)
        result['phase_memory']['completed'] = after
        same_tree = before['pids'] == after['pids']
        result['process_tree_stable_for_cpu'] = same_tree
        result['cpu_seconds'] = ((after['cpu_ticks']-before['cpu_ticks'])/os.sysconf('SC_CLK_TCK')) if same_tree else None
        result['workload_wall_seconds'] = time.monotonic()-wall
        result['minor_faults'] = after['minor_faults']-before['minor_faults'] if same_tree else None
        result['major_faults'] = after['major_faults']-before['major_faults'] if same_tree else None
        result['raw_ms'] = raw
        result['latency'] = {key: summarize(values) for key, values in raw.items()}
        result['status'] = 'pass'
        result['stage'] = 'complete'
    except Exception as error:
        result.update(status='partial' if result.get('raw_ms') else 'fail', error=str(error), screen=session.text())
        if result.get('raw_ms'):
            result['latency'] = {key: summarize(values) for key, values in result['raw_ms'].items()}
        result['phase_memory']['failed'] = usage(session.pid)
        if result.get('stage') == 'unicode-jumps':
            result['unavailable_actions'] = {'line_end_start': 'end marker did not become visible; see error/screen'}
        if result.get('stage') == 'paging':
            result['paging_final_position'] = document_position(session)
            result['paging_final_rows'] = rows(session)
    finally:
        close(session)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workloads', nargs='+', choices=WORKLOADS, default=list(WORKLOADS))
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--cpus', default='2,3,4,5')
    args = parser.parse_args()
    if args.samples < 1 or args.repeats < 1 or args.timeout <= 0:
        parser.error('samples/repeats/timeout must be positive')
    binary = args.binary.resolve()
    os.sched_setaffinity(0, set(map(int, args.cpus.split(','))))
    report = {'schema': 1, 'binary': str(binary), 'binary_sha256': digest(binary),
              'runner_sha256': digest(Path(__file__)), 'cpus': sorted(os.sched_getaffinity(0)),
              'endpoint': 'PTY input write to changed screen content reconstructed by libvterm; no physical display',
              'cpu_scope': 'editor and descendant process CPU during actions/waits; /proc scheduler ticks',
              'cpu_resolution_seconds': 1/os.sysconf('SC_CLK_TCK'),
              'percentile_rule': 'nearest rank; p99 with fewer than100 observations is the maximum',
              'terminal': {'columns': 120, 'rows': 32}, 'samples_per_action': args.samples,
              'results': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dna-expanded-benchmark-') as temporary:
        for repeat in range(args.repeats):
            for workload in args.workloads:
                directory = Path(temporary)/f'{repeat}-{workload}'
                directory.mkdir()
                result = trial(binary, workload, args.samples, args.timeout, directory)
                result['repeat'] = repeat
                report['results'].append(result)
                args.output.write_text(json.dumps(report, indent=2)+'\n')
                print(json.dumps({key: value for key, value in result.items()
                                  if key not in ('raw_ms', 'lsp_peer_log', 'screen')}), flush=True)
    if any(row['status'] != 'pass' for row in report['results']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
