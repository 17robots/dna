#!/usr/bin/env python3
"""Check viewport work and measure individual input updates on a 50 KB file."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
probe = ROOT / "build" / "input-latency.so"
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'input_latency', str(probe)], check=True)
with tempfile.TemporaryDirectory(prefix="dna-latency-") as directory:
    fixture = Path(directory) / "large.txt"
    fixture.write_text("This is a line of text to edit in the document.\n" * 1100)
    for mode in ("debug", "release"):
        for moving in (False, True):
            env = dict(os.environ, LD_PRELOAD=str(probe))
            env.update(DNA_CONFIG=str(Path(directory) / "none"), DNA_RECOVERY="0")
            env.setdefault("SDL_VIDEODRIVER", "dummy")
            env.pop("DYN_EDITOR_SMOKE", None)
            env.pop("DNA_LATENCY_MOVE", None)
            if moving:
                env["DNA_LATENCY_MOVE"] = "1"
            print(f"{mode}, {env['SDL_VIDEODRIVER']}", flush=True)
            subprocess.run([str(ROOT / "build" / f"dna-{mode}"), str(fixture)],
                           env=env, check=True, timeout=20)

animation_probe = ROOT / "build" / "animations.so"
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'animations', str(animation_probe)], check=True)
with tempfile.TemporaryDirectory(prefix="dna-animation-") as directory:
    fixture = Path(directory) / "scroll.txt"
    fixture.write_text("Cursor and scrolling fixture.\n" * 100)
    for mode in ("debug", "release"):
        for reduced in (False, True):
            env = dict(os.environ, LD_PRELOAD=str(animation_probe))
            env.update(DNA_CONFIG=str(Path(directory) / "none"), DNA_RECOVERY="0")
            env.setdefault("SDL_VIDEODRIVER", "dummy")
            env.pop("DYN_EDITOR_SMOKE", None)
            env.pop("DNA_REDUCED_MOTION", None)
            if reduced:
                env["DNA_REDUCED_MOTION"] = "1"
            subprocess.run([str(ROOT / "build" / f"dna-{mode}"), str(fixture)], env=env, check=True, timeout=10)

selection_probe = ROOT / "build" / "selection-render.so"
subprocess.run(['python3', str(ROOT/'scripts/native_test.py'), 'selection_render', str(selection_probe)], check=True)
with tempfile.TemporaryDirectory(prefix="dna-selection-") as directory:
    fixture = Path(directory) / "selection.txt"
    fixture.write_text("aé中  \n\nlast")
    for mode in ("debug", "release"):
        env = dict(os.environ, LD_PRELOAD=str(selection_probe), DNA_REDUCED_MOTION="1")
        env.update(DNA_CONFIG=str(Path(directory) / "none"), DNA_RECOVERY="0")
        env.setdefault("SDL_VIDEODRIVER", "dummy")
        env.pop("DYN_EDITOR_SMOKE", None)
        subprocess.run([str(ROOT / "build" / f"dna-{mode}"), str(fixture)], env=env, check=True, timeout=10)

        env["DNA_LINE_SELECT"] = "1"
        subprocess.run([str(ROOT / "build" / f"dna-{mode}"), str(fixture)], env=env, check=True, timeout=10)
        env.pop("DNA_LINE_SELECT", None)
        env["DNA_MULTI_SELECT"] = "1"
        subprocess.run([str(ROOT / "build" / f"dna-{mode}"), str(fixture)], env=env, check=True, timeout=10)

        env.pop("DNA_MULTI_SELECT", None)
        for selection_case in ("DNA_NEWLINE_SELECT", "DNA_BLANK_SELECT", "DNA_EOL_SELECT"):
            env[selection_case] = "1"
            subprocess.run([str(ROOT / "build" / f"dna-{mode}"), str(fixture)], env=env, check=True, timeout=10)
            env.pop(selection_case)
