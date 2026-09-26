#!/usr/bin/env python3
"""Replay search/open/edit; bound resident memory and submitted rendering work."""
import os
import signal
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
probe = ROOT / "build/workflow-performance.so"
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'workflow_performance', str(probe)], check=True)
with tempfile.TemporaryDirectory(prefix="dna-workflow-") as temporary:
    directory = Path(temporary)
    for index in range(12):
        row = f'{{"name":"needle-{index:02}","value":123,"active":true}}'
        (directory / f"{index:02}.json").write_text("[\n" + ",\n".join([row] * 1000) + "\n]")
    env = dict(
        os.environ, SDL_VIDEODRIVER=os.environ.get("SDL_VIDEODRIVER", "dummy"),
        DNA_CONFIG=str(directory / ".config/config.toml"),
        DNA_LANGUAGE_DIR=os.environ.get("DNA_LANGUAGE_DIR", str(ROOT / "build/test-languages")),
        LD_PRELOAD=str(probe), LD_LIBRARY_PATH=str(ROOT / "build/deps/install/lib"),
    )
    env.pop("DYN_EDITOR_SMOKE", None)
    binary = Path(os.environ.get("DNA_PERF_BINARY", str(ROOT / f"build/dna-{os.environ.get('DNA_PERF_MODE', 'release')}")))
    run = subprocess.Popen([str(binary)], cwd=directory, env=env, start_new_session=True)
    try:
        code = run.wait(timeout=45 * int(os.environ.get("DNA_PERF_ROUNDS", "2")))
        assert code == 0, f"editor exit status: {code}"
    finally:
        if run.poll() is None: run.kill()
        # Terminal workers start their own sessions. The probe closes them before
        # exiting; the group cleanup covers other inherited subprocesses.
        try: os.killpg(run.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        run.wait()

    # Pixel-equivalence catches misplaced overlays (bearings, Unicode, tabs).
    fixture = directory / "render.json"
    fixture.write_text('{\n\t"name": "hello é中 é world",\n\t"numbers": [1, 2, 30, 400],\n\t"flag": true\n}\n')
    for zoom in (False, True):
        captures = []
        for reference in (False, True):
            capture = directory / f"syntax-{zoom}-{reference}.bmp"
            visual_env = dict(env, DNA_PERF_CAPTURE=str(capture), DNA_REDUCED_MOTION="1", SDL_VIDEODRIVER="dummy")
            visual_env.pop("DNA_RENDER_TRACE", None)
            visual_env.pop("DNA_PERF_REFERENCE", None)
            visual_env.pop("DNA_PERF_ZOOM", None)
            if reference:
                visual_env["DNA_PERF_REFERENCE"] = "1"
            if zoom:
                visual_env["DNA_PERF_ZOOM"] = "1"
            subprocess.run([str(binary), str(fixture)], cwd=directory, env=visual_env, timeout=10, check=True)
            captures.append(capture.read_bytes())
        assert captures[0] == captures[1], "syntax spans differ from full-document reference rendering"
    print("PASS syntax rendering: Unicode, tabs, glyph bearings, cached font resize", flush=True)
