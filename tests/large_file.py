#!/usr/bin/env python3
"""Real terminal regression for editing and saving beyond a giant line's start."""
import argparse
import hashlib
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from benchmark_editors import Session

parser = argparse.ArgumentParser()
parser.add_argument("--mib", type=int, default=64)
parser.add_argument("--binary", type=Path, action="append")
args = parser.parse_args()
assert args.mib >= 2
binaries = args.binary or [ROOT / "build/dna-debug", ROOT / "build/dna-release"]
size = args.mib * 1024 * 1024

with tempfile.TemporaryDirectory(prefix="dna-long-line-") as temporary:
    root = Path(temporary)
    config = root / "dna.toml"
    config.write_text('reduced_motion = true\n[modules]\nkeymap = "vim"\n')
    env = dict(os.environ, DNA_CONFIG=str(config), DNA_DEFAULT_SERVERS="0",
               DNA_RECOVERY="0", HOME=str(root), XDG_CONFIG_HOME=str(root / "config"),
               XDG_STATE_HOME=str(root / "state"), TERM="xterm-256color",
               LD_LIBRARY_PATH=str(ROOT / "build/deps/install/lib"))
    chunk = b"a" * (1024 * 1024)
    for binary in binaries:
        source = root / "long.txt"
        expected = hashlib.sha256()
        with source.open("wb") as stream:
            for data in (b"HEADMARK",):
                stream.write(data)
                expected.update(data)
            remaining = size - 16
            while remaining:
                data = chunk[:min(remaining, len(chunk))]
                stream.write(data)
                expected.update(data)
                remaining -= len(data)
            stream.write(b"TAILMARK")
            expected.update(b"TAILMARKZ")
        session = Session([str(binary.resolve()), "--tui", str(source)], env, str(root))
        try:
            session.wait(lambda: "HEADMARK" in session.text(), timeout=20)
            for key in (b"$", b"A"):
                os.write(session.fd, key)
                session.settle(.03)
            session.wait(lambda: "INSERT" in session.text(), timeout=10)
            os.write(session.fd, b"Z")
            session.wait(lambda: "RKZ" in session.text(), timeout=10)
            os.write(session.fd, b"\x1b")
            session.wait(lambda: "NORMAL" in session.text(), timeout=10)
            os.write(session.fd, b":")
            session.wait(lambda: ">" in session.text(), timeout=10)
            os.write(session.fd, b"w")
            session.wait(lambda: "> w" in session.text(), timeout=10)
            os.write(session.fd, b"\r")
            # Keep draining the PTY while save completion runs.
            session.wait(lambda: source.stat().st_size == size + 1, timeout=20)
            with source.open("rb") as stream:
                assert hashlib.file_digest(stream, "sha256").digest() == expected.digest()
            assert not list(root.glob("*.tmp"))
            # The first atomic save unlinks the mapped origin. Its metadata
            # change must not make a second save reject unchanged mapped text.
            os.write(session.fd, b"A")
            session.wait(lambda: "INSERT" in session.text(), timeout=10)
            os.write(session.fd, b"Q")
            session.wait(lambda: "RKZQ" in session.text(), timeout=10)
            os.write(session.fd, b"\x1b")
            session.wait(lambda: "NORMAL" in session.text(), timeout=10)
            os.write(session.fd, b":")
            session.wait(lambda: ">" in session.text(), timeout=10)
            os.write(session.fd, b"w")
            session.wait(lambda: "> w" in session.text(), timeout=10)
            os.write(session.fd, b"\r")
            session.wait(lambda: source.stat().st_size == size + 2, timeout=20)
            expected.update(b"Q")
            with source.open("rb") as stream:
                assert hashlib.file_digest(stream, "sha256").digest() == expected.digest()
            print(f"PASS {args.mib} MiB single line: open, end motion, visible insertion and byte-exact save ({binary.name})", flush=True)
        finally:
            session.close()
