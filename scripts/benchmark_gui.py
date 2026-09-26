#!/usr/bin/env python3
"""Compare GUI launch-to-first-buffer and idle memory in isolated Gamescope.

This deliberately does not compare SDL presentation with Neovim RPC completion.
The common endpoint is the first non-null buffer commit on the toplevel Wayland
surface. It does not prove file content was drawn, compositor presentation, or
physical display latency. Memory includes each editor's complete process tree;
RSS sums double-count shared pages, so proportional set size is also reported.
Requires gamescope, neovide, nvim, a working GPU, and readable /proc smaps_rollup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def process_memory(parent):
    parents = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / 'status').read_text()
            parents[int(entry.name)] = int(re.search(r'^PPid:\s+(\d+)', status, re.M)[1])
        except (OSError, TypeError):
            continue
    selected = {parent}
    while True:
        expanded = selected | {pid for pid, ppid in parents.items() if ppid in selected}
        if expanded == selected:
            break
        selected = expanded
    result = {'rss_kib': 0, 'pss_kib': 0, 'processes': []}
    for pid in sorted(selected):
        rollup = Path(f'/proc/{pid}/smaps_rollup').read_text()
        result['rss_kib'] += int(re.search(r'^Rss:\s+(\d+)', rollup, re.M)[1])
        result['pss_kib'] += int(re.search(r'^Pss:\s+(\d+)', rollup, re.M)[1])
        result['processes'].append(Path(f'/proc/{pid}/comm').read_text().strip())
    return result


def trial(name, command, env, directory, index, settle):
    surfaces, toplevels, attached = {}, set(), set()
    first = None
    partial = b''
    start = time.monotonic()
    process = subprocess.Popen(command, env=env, cwd=ROOT, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, start_new_session=True)
    poll = selectors.DefaultSelector()
    poll.register(process.stderr, selectors.EVENT_READ)
    try:
        with (directory / f'{name}-{index}.wayland.log').open('wb') as log:
            while first is None or time.monotonic() < first + settle:
                if process.poll() is not None:
                    raise RuntimeError(f'{name} exited early: {process.returncode}; see {log.name}')
                if time.monotonic() - start > 30:
                    raise RuntimeError(f'{name} did not submit a toplevel buffer; see {log.name}')
                for key, _ in poll.select(0.02):
                    data = os.read(key.fd, 65536)
                    observed = time.monotonic()
                    log.write(data)
                    partial += data
                    lines = partial.split(b'\n')
                    partial = lines.pop()
                    for line in lines:
                        text = line.decode(errors='replace')
                        match = re.search(r'get_xdg_surface\(new id xdg_surface#(\d+), wl_surface#(\d+)\)', text)
                        if match:
                            surfaces[match[1]] = match[2]
                        match = re.search(r'xdg_surface#(\d+)\.get_toplevel\(', text)
                        if match and match[1] in surfaces:
                            toplevels.add(surfaces[match[1]])
                        match = re.search(r'wl_surface#(\d+)\.attach\(wl_buffer#', text)
                        if match:
                            attached.add(match[1])
                        match = re.search(r'wl_surface#(\d+)\.commit\(', text)
                        if first is None and match and match[1] in toplevels & attached:
                            first = observed
            memory = process_memory(process.pid)
            return {'editor': name, 'trial': index,
                    'first_buffer_observed_ms': (first - start) * 1000, **memory}
    finally:
        poll.close()
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        process.stderr.close()


def worker(args):
    directory = args.output.resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dna-gui-benchmark-') as temporary:
        config = Path(temporary)
        fixture = config / 'fixture.txt'
        fixture.write_text('This is a line of text to edit in the document.\n' * 1100)
        env = dict(os.environ, WAYLAND_DEBUG='client', SDL_VIDEODRIVER='wayland',
                   DNA_DEFAULT_SERVERS='0', DNA_RECOVERY='0', DNA_CONFIG=str(config / 'none'),
                   XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(config / 'data'),
                   XDG_CACHE_HOME=str(config / 'cache'), WINIT_UNIX_BACKEND='wayland')
        for variable in list(env):
            if variable.startswith('NEOVIDE_') or variable in ('LD_PRELOAD', 'DYN_EDITOR_SMOKE', 'SDL_RENDER_DRIVER', 'NEOVIM_BIN'):
                env.pop(variable, None)
        commands = {
            'dna': [str(args.dna.resolve()), str(fixture)],
            'neovide': ['neovide', '--no-fork', '--size', '1100x760', '--',
                        '-u', 'NONE', '-i', 'NONE', '--noplugin', str(fixture)],
        }
        results = []
        # One excluded warmup for each application; subsequent trials alternate order.
        for name, command in commands.items():
            trial(name, command, env, directory, 'warmup', args.settle)
        for index in range(args.trials):
            names = list(commands) if index % 2 == 0 else list(reversed(commands))
            for name in names:
                result = trial(name, commands[name], env, directory, index, args.settle)
                results.append(result)
                print(json.dumps(result), flush=True)
        summary = {}
        for name in commands:
            samples = [row for row in results if row['editor'] == name]
            summary[name] = {
                field + '_median': statistics.median(row[field] for row in samples)
                for field in ('first_buffer_observed_ms', 'rss_kib', 'pss_kib')
            }
            summary[name]['first_buffer_observed_ms_max'] = max(row['first_buffer_observed_ms'] for row in samples)
        report = {
            'endpoint': 'launch to observer reading first toplevel non-null Wayland buffer commit',
            'limitations': ['Not content-verified, not physical/display latency.',
                           'Wayland debug logging and observer scheduling add overhead.',
                           'Idle plain-text workload; no language servers or syntax plugins.',
                           'Separate application rendering stacks/default fonts; headless compositor, same GPU.',
                           'RSS sums include shared-page double counting; PSS apportions shared pages.',
                           'GPU device allocations and compositor memory are not included.'],
            'fixture_bytes': fixture.stat().st_size, 'settle_seconds': args.settle,
            'dna_binary': str(args.dna.resolve()),
            'dna_sha256': hashlib.sha256(args.dna.read_bytes()).hexdigest(),
            'window_pixels': [1100, 760], 'versions': {
                'neovide': subprocess.check_output(['neovide', '--version'], text=True).strip(),
                'neovim': subprocess.check_output(['nvim', '--version'], text=True).splitlines()[0],
            }, 'summary': summary, 'trials': results,
        }
        pending = args.output.with_suffix('.pending.json')
        pending.write_text(json.dumps(report, indent=2) + '\n')
        pending.replace(args.output)
        print(json.dumps(summary, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dna', type=Path, default=ROOT / 'dna')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/gui-benchmark/results.json')
    parser.add_argument('--trials', type=int, default=5)
    parser.add_argument('--settle', type=float, default=2)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.trials < 1 or args.settle <= 0:
        parser.error('trials and settle must be positive')
    if args.worker:
        if not os.environ.get('GAMESCOPE_WAYLAND_DISPLAY') or os.environ.get('WAYLAND_DISPLAY') != os.environ.get('GAMESCOPE_WAYLAND_DISPLAY'):
            parser.error('worker requires the isolated Gamescope display')
        worker(args)
        return
    for executable in ('gamescope', 'neovide', 'nvim'):
        if not shutil.which(executable):
            parser.error(f'{executable} is required')
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = ['gamescope', '--backend', 'headless', '--expose-wayland',
               '--force-windows-fullscreen', '-W', '1100', '-H', '760', '--',
               sys.executable, str(Path(__file__).resolve()), '--worker',
               '--dna', str(args.dna.resolve()), '--output', str(args.output),
               '--trials', str(args.trials), '--settle', str(args.settle)]
    args.output.unlink(missing_ok=True)
    with args.output.with_suffix('.compositor.log').open('w') as log:
        compositor = subprocess.Popen(command, cwd=ROOT, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 120 + args.trials * 20
        try:
            while compositor.poll() is None and not args.output.exists():
                if time.monotonic() > deadline:
                    raise TimeoutError('GUI benchmark exceeded its deadline')
                time.sleep(0.1)
            # Some GPU drivers hang during compositor shutdown after the child exits.
            # The atomic result file is only published after every trial completes.
            try:
                compositor.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print('Results complete; stopping compositor stuck during shutdown.', file=sys.stderr)
        finally:
            if compositor.poll() is None:
                os.killpg(compositor.pid, signal.SIGKILL)
                compositor.wait()
    # Gamescope does not always propagate its child's status.
    if not args.output.exists():
        raise RuntimeError(f'No results produced; inspect {log.name}')


if __name__ == '__main__':
    main()
