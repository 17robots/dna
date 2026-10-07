#!/usr/bin/env python3
"""Seeded random-input fuzzing through the real event loop, inside bwrap.

The root filesystem is read-only and networking is disabled; only a per-run
scratch directory is writable. Usage: fuzz_input.py [first_seed] [runs] [events]
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
first = int(sys.argv[1]) if len(sys.argv) > 1 else 1
runs = int(sys.argv[2]) if len(sys.argv) > 2 else 20
events = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
mode = os.environ.get("DNA_FUZZ_MODE", "debug")
library = ROOT / "build" / "fuzz-input.so"
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'fuzz_input', str(library)], check=True)
lib = ROOT / "build/deps/install/lib"
# The real Dyn language server starts for main.dyn when dyn is on PATH.
dyn_bin = str(Path(subprocess.check_output(["mise", "which", "dyn"], cwd=ROOT, text=True).strip()).parent)
failures = 0
for seed in range(first, first + runs):
    with tempfile.TemporaryDirectory(prefix="dna-fuzz-") as directory:
        work = Path(directory)
        (work / "home").mkdir()
        (work / "project" / "sub").mkdir(parents=True)
        (work / "project" / "notes.txt").write_text("alpha beta\n\ngamma\tdelta é中😀\n" * 20)
        (work / "project" / "main.dyn").write_text("fn helper(value: i32) i32 {\n  return value\n}\nfn main() {\n  _ = helper(2)\n}\n")
        (work / "project" / "sub" / "data.json").write_text('{"a": [1, 2, {"b": "c"}]}\n')
        # The sandbox makes a real shell safe: only the scratch directory is writable.
        # DNA_FUZZ_VIM=1 fuzzes the Vim keymap profile.
        vim = '[modules]\nkeymap = "vim"\n' if os.environ.get("DNA_FUZZ_VIM") else ''
        # DNA_FUZZ_PLACE=1 docks the explorer and terminal and floats the rest.
        if os.environ.get("DNA_FUZZ_PLACE"):
            vim += ('[place.explorer]\nside = "left"\nsize = 0.3\n[place.terminal]\nside = "bottom"\nsize = 0.4\n'
                    '[place.picker]\nanchor = "top-right"\nwidth = 0.4\n[place.palette]\nanchor = "bottom"\n'
                    '[place.menu]\nanchor = "center"\n[place.dialog]\nanchor = "top-left"\n[place.completion]\nanchor = "right"\n')
        # DNA_FUZZ_TREE=1 uses the tree explorer; DNA_FUZZ_PICKER=compact|dropdown a slim picker.
        modules = ''
        if os.environ.get("DNA_FUZZ_TREE"):
            modules += 'explorer = "tree"\n'
        if os.environ.get("DNA_FUZZ_PICKER"):
            modules += f'picker = "{os.environ["DNA_FUZZ_PICKER"]}"\n'
        if modules:
            vim += '[modules]\n' + modules
        (work / "config.toml").write_text('shell = "/bin/sh"\nbuild_command = "true"\ntest_command = "true"\nrun_command = "true"\n' + vim)
        trace = work / "trace.txt"
        env = {
            "PATH": dyn_bin + ":/usr/bin:/bin", "DNA_DEFAULT_SERVERS": "0", "HOME": str(work / "home"), "XDG_CONFIG_HOME": str(work / "home"),
            "XDG_DATA_HOME": str(work / "home"), "DNA_CONFIG": str(work / "config.toml"), "DNA_RECOVERY": "0",
            "SDL_VIDEODRIVER": "dummy", "LD_LIBRARY_PATH": str(lib), "LD_PRELOAD": str(library),
            "DNA_FUZZ_SEED": str(seed), "DNA_FUZZ_EVENTS": str(events), "DNA_FUZZ_TRACE": str(trace),
            "DNA_LANGUAGE_DIR": str(ROOT / "build/test-languages"),
            "DNA_FUZZ_FOCUS": os.environ.get("DNA_FUZZ_FOCUS", ""),
        }
        command = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
                   "--bind", str(work), str(work), "--unshare-net", "--die-with-parent", "--chdir", str(work / "project"),
                   str(ROOT / "build" / f"dna-{mode}"), "main.dyn" if os.environ.get("DNA_FUZZ_FOCUS") == "completion" else ("notes.txt", "main.dyn", "sub/data.json")[seed % 3]]
        hang = os.environ.get("DNA_FUZZ_GDB")
        if hang:
            # Interrupt a hung run after N seconds and print every thread's stack.
            split = command.index(str(ROOT / "build" / f"dna-{mode}"))
            command = command[:split] + ["timeout", "-s", "INT", "--kill-after=20", hang, "gdb", "-q", "-batch", "-ex", "set startup-with-shell off", "-ex", "handle SIGPIPE nostop noprint", "-ex", "run", "-ex", "bt 40", "-ex", "kill", "--args"] + command[split:]
        try:
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=120)
            code, output = result.returncode, result.stderr + result.stdout
        except subprocess.TimeoutExpired as error:
            code, output = "timeout", (error.stderr or b"").decode(errors="replace") if isinstance(error.stderr, bytes) else (error.stderr or "")
        if os.environ.get("DNA_FUZZ_KEEP") and trace.exists():
            (ROOT / "build" / f"fuzz-trace-{seed}.txt").write_text(trace.read_text())
        if os.environ.get("DNA_FUZZ_KEEP"):
            tree = sorted(str(path.relative_to(work / "project")) for path in (work / "project").rglob("*"))
            (ROOT / "build" / f"fuzz-tree-{seed}.txt").write_text("\n".join(tree) + "\n")
        if code != 0:
            failures += 1
            kept = ROOT / "build" / f"fuzz-failure-{seed}.txt"
            kept.write_text(output + "\n--- trace ---\n" + (trace.read_text() if trace.exists() else ""))
            head = "\n".join(line for line in output.splitlines() if line.strip())[:600]
            print(f"FAIL seed {seed} ({code}): {head}\n  trace: {kept}", flush=True)
focus = os.environ.get("DNA_FUZZ_FOCUS") or "random"
print(f"fuzz: {runs - failures}/{runs} seeds clean, {events} events each ({mode}, {focus})")
sys.exit(1 if failures else 0)
