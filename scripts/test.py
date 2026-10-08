#!/usr/bin/env python3
"""Stage production modules under Dyn's entry root; never maintain test copies."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DYN = os.environ.get("DYN", "dyn")
for suite in ("objects", "buffer", "files", "layout", "motion", "pattern", "settings", "workspace", "lsp", "servers"):
    stage = ROOT / "build" / f"test-{suite}"
    stage.mkdir(parents=True, exist_ok=True)
    for module in ("host", "filesystem", "buffer", "files", "layout", "motion", "pattern", "settings", "workspace", "lsp", "servers"):
        shutil.copytree(ROOT / "src" / module, stage / module, dirs_exist_ok=True)
    source = (ROOT / "tests" / suite / "main.dyn").read_text()
    (stage / "main.dyn").write_text(source.replace('../../src/', './'))
    for mode in ("debug", "release"):
        binary = stage / f"test-{mode}"
        subprocess.run(["python3", str(ROOT / "scripts/compile.py"), DYN, "build", str(stage), f"--{mode}", "--no-cache", "--output", str(binary)], check=True)
        with tempfile.TemporaryDirectory(prefix="dna-tests-") as temporary:
            fixtures = Path(temporary)
            (fixtures / "link.txt").symlink_to("sample.txt")
            os.mkfifo(fixtures / "pipe.txt")
            (fixtures / "binary.txt").write_bytes(b"bad\0text")
            # One byte past buffer.Capacity; sparse, so creating it is free.
            with open(fixtures / "large.txt", "wb") as large:
                large.truncate(268435456)
            # The debug buffer suite takes ~8 s locally; shared CI runners
            # are several times slower, so allow a wide margin.
            subprocess.run([str(binary)], cwd=temporary, check=True, timeout=60)
        print(f"PASS {suite} ({mode})", flush=True)
