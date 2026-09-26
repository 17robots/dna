#!/usr/bin/env python3
"""Stage production modules under Dyn's entry root; never maintain test copies."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get("DYN", "dyn")
for suite in ("buffer", "files", "layout"):
    stage = ROOT / "build" / f"test-{suite}"
    stage.mkdir(parents=True, exist_ok=True)
    for module in ("buffer", "files", "layout"):
        shutil.copytree(ROOT / "src" / module, stage / module, dirs_exist_ok=True)
    source = (ROOT / "tests" / suite / "main.dyn").read_text()
    (stage / "main.dyn").write_text(source.replace('../../src/', './'))
    for mode in ("debug", "release"):
        binary = stage / f"test-{mode}"
        subprocess.run([DYN, "build", str(stage), f"--{mode}", "--no-cache", "--output", str(binary)], check=True)
        with tempfile.TemporaryDirectory(prefix="dna-tests-") as temporary:
            fixtures = Path(temporary)
            (fixtures / "link.txt").symlink_to("sample.txt")
            os.mkfifo(fixtures / "pipe.txt")
            (fixtures / "binary.txt").write_bytes(b"bad\0text")
            (fixtures / "large.txt").write_bytes(b"x" * 65536)
            subprocess.run([str(binary)], cwd=temporary, check=True, timeout=20)
        print(f"PASS {suite} ({mode})", flush=True)
