#!/usr/bin/env python3
"""Exercise the native UI with isolated real-file fixtures."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
for mode in ("debug", "release"):
    with tempfile.TemporaryDirectory(prefix="dna-ui-") as directory:
        fixtures = Path(directory)
        (fixtures / "explorer").mkdir()
        (fixtures / "explorer" / "keep").mkdir()
        (fixtures / "explorer" / "alpha.txt").write_text("alpha contents")
        (fixtures / "explorer" / "delete.txt").write_text("recover me")
        (fixtures / "subdir").mkdir()
        (fixtures / "subdir" / "other.txt").write_text("other file\n")
        (fixtures / "input.txt").write_text("first\nsecond\n")
        (fixtures / "test.dna-layout").write_text("popup_width=0.8\npopup_height=0.7\nfont_size=22\n")
        env = dict(os.environ, DYN_EDITOR_SMOKE="1", DNA_WORKFLOW_TEST=directory)
        env.setdefault("SDL_VIDEODRIVER", "dummy")
        subprocess.run([str(ROOT / "build" / f"dna-{mode}")], env=env, check=True, timeout=20)
        assert (fixtures / "input.txt").read_text() == "edited first\nsecond\n"
        assert (fixtures / ".dna-trash" / "renamed.txt").is_file()
        assert not (fixtures / "created.txt").exists()
        assert not (fixtures / "renamed.txt").exists()
        assert (fixtures / "explorer" / "renamed.txt").read_text() == "alpha contents"
        assert (fixtures / "explorer" / ".dna-trash" / "delete.txt").read_text() == "recover me"
        assert (fixtures / "explorer" / "created.txt").read_text() == ""
        assert (fixtures / "explorer" / "collision.txt").read_text() == "external"
        assert not (fixtures / "accidental.txt").exists()
        print(f"PASS native workflow ({mode}, {env['SDL_VIDEODRIVER']})", flush=True)
