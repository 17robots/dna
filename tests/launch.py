#!/usr/bin/env python3
"""Check real launch arguments using the native UI smoke adapter."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="dna-launch-") as temporary:
    root = Path(temporary)
    project = root / "project with spaces"
    project.mkdir()
    (project / "example.dyn").write_text("fn main() {}\n")
    (root / "--gui").write_text("literal flag filename\n")
    (root / "alias").symlink_to(project, target_is_directory=True)
    config = root / "config.toml"
    config.write_text("reduced_motion = true\n")
    cases = [
        ([str(project / "example.dyn")], "file", project / "example.dyn"),
        (["project with spaces/example.dyn", "--gui"], "file", project / "example.dyn"),
        (["--gui", "project with spaces/new.dyn"], "error", project / "new.dyn"),
        (["--", "--gui"], "file", root / "--gui"),
        ([str(project)], "directory", project),
        (["project with spaces/", "--gui"], "directory", project),
        (["--gui", "alias"], "directory", project),
        (["."], "directory", root),
    ]
    for mode in os.environ.get("DNA_SMOKE_MODES", "debug release").split():
        for explorer in ("buffer", "tree"):
            config.write_text(f'reduced_motion = true\n[modules]\nexplorer = "{explorer}"\n')
            for arguments, kind, expected in cases:
                env = dict(os.environ, DYN_EDITOR_SMOKE="1", DNA_DEFAULT_SERVERS="0",
                           DNA_LAUNCH_EXPECT=str(expected), DNA_LAUNCH_KIND=kind,
                           DNA_CONFIG=str(config), DNA_RECOVERY="0",
                           XDG_CONFIG_HOME=str(root / "config"), XDG_STATE_HOME=str(root / "state"))
                env.setdefault("SDL_VIDEODRIVER", "dummy")
                subprocess.run([str(ROOT / f"build/dna-smoke-{mode}"), *arguments],
                               cwd=root, env=env, check=True, timeout=15)
        print(f"PASS launch arguments ({mode}, {len(cases) * 2} cases)", flush=True)
