#!/usr/bin/env python3
"""Replay gg/ge on smoke.dyn; bound shaping work during jump animation."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
probe = ROOT / "build/jump-latency.so"
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'jump_latency', str(probe)], check=True)
with tempfile.TemporaryDirectory(prefix="dna-jump-") as temporary:
    directory = Path(temporary)
    fixture = directory / "smoke.dyn"
    shutil.copyfile(ROOT / "tests/editor/smoke.dyn", fixture)
    env = dict(os.environ, SDL_VIDEODRIVER=os.environ.get("SDL_VIDEODRIVER", "dummy"),
               DNA_CONFIG=str(directory / "config.toml"),
               DNA_LANGUAGE_DIR=os.environ.get("DNA_LANGUAGE_DIR", str(ROOT / "build/test-languages")),
               LD_LIBRARY_PATH=str(ROOT / "build/deps/install/lib"), LD_PRELOAD=str(probe))
    lines = fixture.read_text().splitlines()
    env["DNA_JUMP_TOP"] = lines[0]
    # Lines are shaped one per text object: mark the bottom with the file's
    # last line that is long and appears once.
    env["DNA_JUMP_BOTTOM"] = next(line for line in reversed(lines) if len(line) > 20 and lines.count(line) == 1)
    env.pop("DYN_EDITOR_SMOKE", None)
    for mode in ("debug", "release"):
        print(f"jump regression: {mode}, {env['SDL_VIDEODRIVER']}", flush=True)
        subprocess.run([str(ROOT / f"build/dna-{mode}"), str(fixture)], cwd=directory,
                       env=env, check=True, timeout=20)
