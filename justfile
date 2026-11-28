set shell := ["bash", "-euo", "pipefail", "-c"]
export DYN := `python3 scripts/dyn_path.py`
export DYN_LIBRARY_PATH := justfile_directory() / "build/deps/install/lib"
export LD_LIBRARY_PATH := justfile_directory() / "build/deps/install/lib"
# Tests never start language servers found on the developer's PATH.
export DNA_DEFAULT_SERVERS := "0"
# Tests use the dyn on PATH, not a personal DNA_DYN_LSP override.
export DNA_DYN_LSP := ""
deps:
    python3 scripts/deps.py
# Native Linux GUI; select Wayland in a Wayland session, otherwise X11.
build mode="debug": deps
    python3 scripts/build_native.py --mode {{mode}} --output build/dna-{{mode}}
# Build a module profile: profiles/NAME.toml or ~/.config/dna/profiles/NAME.toml,
# into build/dna-NAME. Example: just build-profile minimal
build-profile name="full" mode="release": deps
    python3 scripts/profile.py {{name}} {{mode}}
run file="": (build "debug")
    env -u DNA_DEFAULT_SERVERS ./build/dna-debug {{quote(file)}}
run-release file="": (build "release")
    env -u DNA_DEFAULT_SERVERS ./build/dna-release {{quote(file)}}
# List one-off probe and investigation output in build/; --delete removes it.
clean-scratch *flags:
    python3 scripts/clean_scratch.py {{flags}}
# dyn fmt skips nested module directories, so visit each one.
fmt:
    find src tests examples modules -name '*.dyn' -printf '%h\n' | sort -u | xargs -n1 "$DYN" fmt
fmt-check:
    find src tests examples modules -name '*.dyn' -printf '%h\n' | sort -u | xargs -n1 "$DYN" fmt --check
# The step lists live in tests/run.py. DNA_TEST_JOBS=1 runs them one at a time;
# DNA_TEST_ONLY=buffer_close,jobs runs only those. Tests never see your desktop
# display (tests/private_display.py), so native window tests skip locally.
test:
    python3 tests/run.py test
# Checks never read your own config, trust store or recovery files: a personal
# setting such as frontend = "tui" must not change what they exercise.
smoke:
    rm -rf build/test-home && mkdir -p build/test-home/config build/test-home/state
    XDG_CONFIG_HOME="$PWD/build/test-home/config" XDG_STATE_HOME="$PWD/build/test-home/state" just _smoke
_smoke: deps
    python3 tests/run.py smoke

# Compile the same native production sources used by direct dyn run/build.
smoke-direct: deps
    DYN_LIBRARY_PATH="$PWD/build/deps/static:$PWD/build/deps/install/lib" python3 scripts/compile.py "$DYN" build src --release --output build/dna-direct --link "$(python3 scripts/runpath.py)"
    python3 tests/native_only.py --binary build/dna-direct
    DYN_EDITOR_SMOKE=1 DNA_RECOVERY=0 ./build/dna-direct

# Local Linux archive only. No tags, upload, or publication.
package: (build "release")
    python3 scripts/build_native.py --backend wayland --release
    python3 scripts/build_native.py --backend x11 --release
    python3 scripts/compile.py "$DYN" build examples/plugins/uppercase --release --output examples/plugins/uppercase/uppercase
    python3 scripts/package.py

# Compare contiguous-buffer edit costs before changing storage.
bench-buffer:
    python3 tests/buffer_performance.py

# Repeated native service ownership and terminal event-loop checks.
soak: deps
    DNA_RESOURCE_CYCLES=300 python3 tests/native_memory.py
    python3 tests/disk_idle.py
    python3 tests/resource_cycles.py

# Random terminal input (keys, escape sequences, mouse, pastes, resizes) for
# dna --tui through a pty, sandboxed with bwrap. DNA_FUZZ_MODE=release too.
fuzz-tui first="1" runs="20" chunks="600": (build "debug")
    python3 tests/fuzz_tui.py {{first}} {{runs}} {{chunks}}

# Warm native CPU rendering only; run without concurrent builds/benchmarks.
bench-native-frames:
    python3 scripts/benchmark_native_frames.py --scenario picker
