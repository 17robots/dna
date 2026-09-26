#!/usr/bin/env python3
"""Exercise the native UI with isolated real-file fixtures."""
import os
from pathlib import Path
import subprocess
import tempfile
import sys as _sys
_sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'scripts'))
from dyn_path import with_real_dyn
ROOT = Path(__file__).resolve().parents[1]
for mode in os.environ.get("DNA_SMOKE_MODES", "debug release").split():
    with tempfile.TemporaryDirectory(prefix="dna-ui-") as directory:
        fixtures = Path(directory)
        (fixtures / "explorer").mkdir()
        (fixtures / "explorer" / "keep").mkdir()
        (fixtures / "explorer" / "keep" / "child.txt").write_text("child contents")
        (fixtures / "explorer" / "alpha.txt").write_text("alpha contents")
        (fixtures / "explorer" / "delete.txt").write_text("recover me")
        (fixtures / "real-platform").mkdir()
        for source_file in (ROOT / "src/platform").glob("*.dyn"):
            (fixtures / "real-platform" / source_file.name).write_text(source_file.read_text())
        (fixtures / "subdir").mkdir()
        (fixtures / "subdir" / "other.txt").write_text("other file\n")
        (fixtures / "input.txt").write_text("first\nsecond\n")
        (fixtures / "test.dna-layout").write_text("popup_width=0.8\npopup_height=0.7\nfont_size=22\nreduced_motion=1\n")
        # Tests use the dyn on PATH, never a personal DNA_DYN_LSP override.
        base_env = {key: value for key, value in os.environ.items() if key != 'DNA_DYN_LSP'}
        env = with_real_dyn(dict(base_env, DNA_TEST_LSP="python3 " + str(ROOT / "tests/fake_lsp.py"), DYN_EDITOR_SMOKE="1", DNA_WORKFLOW_TEST=directory, DNA_TEST_PLUGIN=str(ROOT/"examples/plugins/uppercase/plugin.json"), XDG_CONFIG_HOME=str(fixtures / "config"), XDG_STATE_HOME=str(fixtures / "state"), DNA_CONFIG=str(fixtures / "startup-config.toml"), DNA_LANGUAGE_DIR=str(fixtures / "languages")))
        if (ROOT / "build/test-languages/python/parser.so").exists() and (ROOT / "build/test-languages/json/parser.so").exists():
            env["DNA_TEST_LANGUAGE_DIR"] = str(ROOT / "build/test-languages")
        env.setdefault("SDL_VIDEODRIVER", "dummy")
        subprocess.run([str(ROOT / "build" / f"dna-smoke-{mode}")], env=env, check=True, timeout=20)
        assert (fixtures / "save-first.txt").read_text() == "Afirst"
        assert (fixtures / "save-second.txt").read_text() == "Bsecond"
        assert (fixtures / "save-unnamed.txt").read_text() == "unnamed"
        assert (fixtures / "picker-save.txt").read_text() == "picker saved edits"
        assert (fixtures / "ctrl-x-save.txt").read_text() == "saved on close"
        assert (fixtures / "input.txt").read_text() == "edited first\nsecond\n"
        assert (fixtures / ".dna-trash" / "renamed.txt").is_file()
        assert not (fixtures / "created.txt").exists()
        assert not (fixtures / "renamed.txt").exists()
        assert (fixtures / "explorer" / "renamed.txt").read_text() == "alpha contents"
        assert (fixtures / "explorer" / ".dna-trash" / "delete.txt").read_text() == "recover me"
        assert (fixtures / "explorer" / "created.txt").read_text() == ""
        assert (fixtures / "explorer" / "new-folder").is_dir()
        assert not (fixtures / "explorer" / "keep").exists()
        assert (fixtures / "explorer" / ".dna-trash" / "keep" / "child.txt").read_text() == "child contents"
        assert (fixtures / "explorer" / "collision.txt").read_text() == "external"
        assert not (fixtures / "accidental.txt").exists()
        print(f"PASS native workflow ({mode}, {env['SDL_VIDEODRIVER']})", flush=True)
