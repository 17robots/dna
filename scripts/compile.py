#!/usr/bin/env python3
"""Serialize compiler invocations and contain compiler/linker memory usage.

Build-time helper only; not shipped as part of the editor runtime.
"""
import fcntl
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: compile.py COMPILER [ARGS...]')
    memory_mb = int(os.environ.get('DNA_BUILD_MEMORY_MB', '2048'))
    if not 32 <= memory_mb <= 4096:
        raise SystemExit('DNA_BUILD_MEMORY_MB must be between 32 and 4096')
    command = sys.argv[1:]
    executable = shutil.which(command[0])
    if not executable:
        raise SystemExit(f'Compiler not found: {command[0]}')
    # A mise shim would re-apply mise.toml's environment, whose
    # DYN_LIBRARY_PATH selects static libraries for direct `dyn build` runs.
    # Recipes set their own path, so call the real compiler behind the shim.
    if Path(executable).resolve().name == 'mise':
        sys.path.insert(0, str(ROOT / 'scripts'))
        from dyn_path import real_dyn
        executable = str(real_dyn() or executable)
    command[0] = executable
    if len(command) > 1 and command[1] in ('build', 'run') and '--jobs' not in command:
        command.extend(['--jobs', '1'])
    (ROOT / 'build').mkdir(exist_ok=True)
    with (ROOT / 'build/.compiler.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        systemd = shutil.which('systemd-run') and shutil.which('systemctl')
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
            # Non-systemd Linux/CI: one compiler worker and an inherited address
            # space limit. This may reject a build earlier than an RSS cap.
            limit = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        print(f'DNA compiler limit: {memory_mb} MiB; serialized build', file=sys.stderr, flush=True)
        result = subprocess.run(command)
        return result.returncode if result.returncode >= 0 else 128 - result.returncode

if __name__ == '__main__':
    raise SystemExit(main())
