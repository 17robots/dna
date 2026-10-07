#!/usr/bin/env python3
"""Serialize compiler invocations and contain compiler/linker memory usage.

Build-time helper only; not shipped as part of the editor runtime.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

from build_limits import compiler_lock, run_windows

ROOT = Path(__file__).resolve().parents[1]

def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: compile.py COMPILER [ARGS...]')
    try:
        memory_mb = int(os.environ.get('DNA_BUILD_MEMORY_MB', '2048'))
    except ValueError:
        raise SystemExit('DNA_BUILD_MEMORY_MB must be an integer between 32 and 4096')
    if not 32 <= memory_mb <= 4096:
        raise SystemExit('DNA_BUILD_MEMORY_MB must be between 32 and 4096')
    command = sys.argv[1:]
    executable = shutil.which(command[0])
    if not executable:
        raise SystemExit(f'Compiler not found: {command[0]}')
    # A mise shim would re-apply mise.toml's environment, whose
    # DYN_LIBRARY_PATH selects static libraries for direct `dyn build` runs.
    # Recipes set their own path, so call the real compiler behind the shim.
    if Path(executable).resolve().stem == 'mise':
        sys.path.insert(0, str(ROOT / 'scripts'))
        from dyn_path import real_dyn
        executable = str(real_dyn() or executable)
    command[0] = executable
    if len(command) > 1 and command[1] in ('build', 'run') and '--jobs' not in command:
        command.extend(['--jobs', '1'])
    (ROOT / 'build').mkdir(exist_ok=True)
    with compiler_lock(ROOT / 'build/.compiler.lock'):
        print(f'DNA compiler limit: {memory_mb} MiB; serialized build', file=sys.stderr, flush=True)
        if os.name == 'nt':
            try:
                return run_windows(command, memory_mb * 1024 * 1024)
            except OSError as error:
                raise SystemExit(f'Cannot enforce Windows compiler memory limit: {error}')
        systemd = (sys.platform.startswith('linux') and
                   shutil.which('systemd-run') and shutil.which('systemctl'))
        if systemd:
            systemd = subprocess.run(['systemctl', '--user', 'show-environment'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if systemd:
            # The entire compiler process tree shares this physical-memory cap.
            # A cgroup failure must fail the build; never retry without the cap.
            command = ['systemd-run', '--user', '--scope', '--quiet',
                       f'--property=MemoryMax={memory_mb}M', '--property=MemorySwapMax=0',
                       '--', *command]
        else:
            # POSIX without systemd: inherited per-process address-space limit.
            # This may reject earlier than an RSS cap, especially on macOS.
            # Refuse the build if the kernel cannot install this limit.
            import resource
            limit = memory_mb * 1024 * 1024
            try:
                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
            except (OSError, ValueError) as error:
                # macOS refuses address-space limits outright; there the
                # serialized build is the only guard.
                if sys.platform != 'darwin':
                    raise SystemExit(f'Cannot enforce compiler address-space limit: {error}')
                print(f'Compiler address-space limit unavailable on macOS ({error}); building serialized without it', file=sys.stderr)
        result = subprocess.run(command)
        return result.returncode if result.returncode >= 0 else 128 - result.returncode

if __name__ == '__main__':
    raise SystemExit(main())
