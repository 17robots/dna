set shell := ["bash", "-euo", "pipefail", "-c"]
export DYN := env("DYN", "dyn")
export DYN_LIBRARY_PATH := justfile_directory() / "build/deps/install/lib"
export LD_LIBRARY_PATH := justfile_directory() / "build/deps/install/lib"
# Tests never start language servers found on the developer's PATH.
export DNA_DEFAULT_SERVERS := "0"
# Tests use the dyn on PATH, not a personal DNA_DYN_LSP override.
export DNA_DYN_LSP := ""
deps:
    python3 scripts/deps.py
build mode="debug": deps
    mkdir -p build
    python3 scripts/compile.py "$DYN" build src --{{mode}} --output build/dna-{{mode}} --link "$PWD/build/deps/install/lib/libSDL3_ttf.so" --link "$(python3 scripts/runpath.py)" --link "--version-script=$PWD/build/deps/hide-runtime.map"
# Build a module profile: profiles/NAME.toml or ~/.config/dna/profiles/NAME.toml,
# into build/dna-NAME. Example: just build-profile minimal
build-profile name="full" mode="release": deps
    python3 scripts/profile.py {{name}} {{mode}}
run file="": (build "debug")
    env -u DNA_DEFAULT_SERVERS ./build/dna-debug {{quote(file)}}
test:
    python3 scripts/test.py
smoke: deps test
    python3 tests/build_guard.py
    python3 tests/benchmark_cleanup.py
    python3 tests/dyn_support.py
    python3 tests/native_foundation.py
    python3 tests/static_native.py
    python3 tests/process_transport.py
    mkdir -p build
    python3 tests/native_abi.py
    python3 tests/platform_abi.py
    just build debug
    just build release
    python3 scripts/compile.py "$DYN" build examples/plugins/uppercase --debug --output examples/plugins/uppercase/uppercase
    python3 scripts/build_smoke.py
    python3 scripts/smoke.py
    python3 tests/launch.py
    python3 tests/input_save.py
    python3 tests/redraw_idle.py
    python3 tests/redraw_coalesce.py
    python3 tests/render_trace.py
    python3 tests/idle_budget.py
    python3 tests/config_notify.py
    python3 tests/diagnostic_render.py
    python3 tests/language_popups.py
    DNA_POPUP_SNIPPET=1 python3 tests/language_popups.py
    DNA_POPUP_EXAMPLE_CONFIG=1 DNA_POPUP_SETTLE=1 python3 tests/language_popups.py
    DNA_POPUP_PLATFORM=1 DNA_POPUP_DELAY=1 python3 tests/language_popups.py
    DNA_POPUP_PLATFORM=1 DNA_POPUP_INSIDE=1 DNA_POPUP_KEY_DELAY_MS=100 python3 tests/language_popups.py
    python3 tests/explorer_view.py
    python3 tests/tui_render.py
    python3 tests/tui_render.py debug
    DNA_EXPLORER_MODE=release python3 tests/explorer_view.py
    python3 scripts/latency.py
    python3 tests/jump_latency.py
    python3 tests/workflow_performance.py
    DNA_PERF_MODE=debug python3 tests/workflow_performance.py
    DNA_PERF_COMBINED=1 python3 tests/workflow_performance.py
    DNA_PERF_COMBINED=1 DNA_PERF_REAL_SYNTAX=1 python3 tests/workflow_performance.py
    python3 scripts/benchmark_editors.py --editors dna --dna build/dna-release --bytes 5280000 --samples 5 --repeats 1 --max-dna-pss-kib 131072 --output build/document-memory-gate.json
    python3 tests/document_memory.py
    python3 tests/terminal_review.py
    python3 tests/terminal_boundaries.py
    python3 tests/rpc.py
    python3 tests/jobs.py
    python3 tests/server_install.py
    python3 tests/disk.py
    python3 tests/disk_idle.py
    python3 tests/syntax_selection.py
    python3 tests/syntax_retire.py
    python3 tests/native.py
    python3 tests/project_search.py
    python3 tests/recovery_faults.py
    python3 tests/save_failures.py
    python3 tests/resource_cycles.py
    python3 tests/native_memory.py
    python3 tests/syntax_memory.py
    python3 tests/thread_join.py
    python3 tests/picker_index.py
    python3 tests/syntax_faults.py
    python3 tests/render_cache.py
    python3 tests/recovery.py
    python3 tests/plugins.py
    python3 scripts/native_test.py notifications build/notifications --executable
    ./build/notifications
    python3 scripts/native_test.py terminal_apps build/terminal-apps --executable
    SDL_VIDEODRIVER=dummy ./build/terminal-apps
    python3 scripts/native_test.py terminal_render build/terminal-render --executable
    SDL_VIDEODRIVER=dummy ./build/terminal-render
    python3 scripts/native_test.py input_events build/input-events.so
    DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/input-events.so" timeout 20 ./build/dna-debug
    DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/input-events.so" timeout 20 ./build/dna-release

    python3 scripts/native_test.py palette_view build/palette-view.so
    DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/palette-view.so" timeout 20 ./build/dna-debug README.md
    DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/palette-view.so" timeout 20 ./build/dna-release README.md
    DNA_UI_MENUS=1 DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/palette-view.so" timeout 20 ./build/dna-debug README.md
    DNA_UI_MENUS=1 DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/palette-view.so" timeout 20 ./build/dna-release README.md
    cp README.md build/dialog-fixture.md
    DNA_UI_DIALOGS=1 DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/palette-view.so" timeout 20 ./build/dna-debug build/dialog-fixture.md
    DNA_UI_DIALOGS=1 DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/palette-view.so" timeout 20 ./build/dna-release build/dialog-fixture.md
    DNA_UI_PANES=1 DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/palette-view.so" timeout 20 ./build/dna-debug README.md
    DNA_UI_PANES=1 DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/palette-view.so" timeout 20 ./build/dna-release README.md
    # Binaries find their bundled libraries without LD_LIBRARY_PATH (RPATH $ORIGIN).
    readelf -d build/dna-release | grep -q 'ORIGIN/deps/install/lib'
    # The Dyn runtime's byte-loop memcpy/memmove/memset stay local to DNA.
    ! nm -D --defined-only build/dna-release | grep -wE 'memcpy|memmove|memset'
    cd /tmp && env -u LD_LIBRARY_PATH -u DYN_LIBRARY_PATH DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="{{justfile_directory()}}/build/palette-view.so" timeout 20 "{{justfile_directory()}}/build/dna-release" "{{justfile_directory()}}/README.md"
    # Runs where SDL is not installed: hide system SDL libraries in a sandbox.
    if command -v bwrap >/dev/null; then hide=""; for f in /usr/lib/libSDL3*.so* /usr/lib64/libSDL3*.so* /usr/lib/x86_64-linux-gnu/libSDL3*.so*; do [ -f "$f" ] && [ ! -L "$f" ] && hide="$hide --bind /dev/null $f"; done; bwrap --ro-bind / / $hide --dev /dev --proc /proc --tmpfs /tmp --bind "$PWD/build" "$PWD/build" env -u LD_LIBRARY_PATH -u DYN_LIBRARY_PATH DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/palette-view.so" timeout 20 "$PWD/build/dna-release" "$PWD/README.md"; fi

    # A direct `dyn build` (mise.toml's library path) links SDL, SDL_ttf and the
    # native library statically: it needs none of them and no build directory.
    env -u LD_LIBRARY_PATH DYN_LIBRARY_PATH="$PWD/build/deps/static:$PWD/build/deps/install/lib" python3 scripts/compile.py "$DYN" build src --release --no-cache --output build/dna-standalone
    ! readelf -d build/dna-standalone | grep -E 'NEEDED.*(SDL3|dna_native)'
    ! nm -D --defined-only build/dna-standalone | grep -wE 'memcpy|memmove|memset'
    if command -v bwrap >/dev/null; then hide=""; for f in /usr/lib/libSDL3*.so* /usr/lib64/libSDL3*.so* /usr/lib/x86_64-linux-gnu/libSDL3*.so*; do [ -f "$f" ] && [ ! -L "$f" ] && hide="$hide --bind /dev/null $f"; done; status=0; bwrap --ro-bind / / $hide --tmpfs /run --ro-bind "$PWD/build/dna-standalone" /run/dna-standalone --tmpfs "$PWD/build" --dev /dev --proc /proc --tmpfs /tmp env -i HOME=/tmp PATH=/usr/bin DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy timeout 4 /run/dna-standalone "$PWD/README.md" || status=$?; [ "$status" = 124 ]; fi

    # Module profiles: the minimal build leaves Vim out and still runs.
    python3 scripts/profile.py minimal release
    ! nm build/dna-minimal | grep -qE "vim_word_forward|tree_reload"
    status=0; DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy timeout 4 ./build/dna-minimal README.md || status=$?; [ "$status" = 124 ]
    # The terminal profile links no SDL, SDL_ttf or GUI code, and runs the TUI checks.
    python3 scripts/profile.py terminal release
    ! readelf -d build/dna-terminal | grep -E 'NEEDED.*(SDL|fontconfig)'
    ! nm build/dna-terminal | grep -qE ' (SDL|TTF)_'
    python3 tests/tui_render.py terminal

    python3 scripts/native_test.py match_input build/match-input.so
    DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/match-input.so" timeout 20 ./build/dna-debug
    DNA_RECOVERY=0 SDL_VIDEODRIVER=dummy LD_PRELOAD="$PWD/build/match-input.so" timeout 20 ./build/dna-release

# Exercise the user's direct command without inheriting this recipe's paths.
smoke-direct: deps
    env -u DYN_LIBRARY_PATH -u LD_LIBRARY_PATH SDL_VIDEODRIVER=dummy DYN_EDITOR_SMOKE=1 mise exec -- python3 scripts/compile.py "$DYN" run src --no-cache
    DNA_POPUP_PLATFORM=1 DNA_POPUP_RUN=1 python3 tests/language_popups.py

# Local Linux archive only. No tags, upload, or publication.
package: (build "release")
    python3 scripts/compile.py "$DYN" build examples/plugins/uppercase --release --output examples/plugins/uppercase/uppercase
    python3 scripts/package.py

# Compare contiguous-buffer edit costs before changing storage.
bench-buffer:
    python3 tests/buffer_performance.py

# Longer repeated workflows. SDL_VIDEODRIVER=wayland selects a real desktop.
soak:
    DNA_PERF_ROUNDS=20 python3 tests/workflow_performance.py
    DNA_PERF_ROUNDS=4 DNA_PERF_COMBINED=1 DNA_PERF_REAL_SYNTAX=1 python3 tests/workflow_performance.py
    DNA_RESOURCE_CYCLES=300 python3 tests/native_memory.py
    python3 tests/redraw_idle.py
    python3 tests/disk_idle.py

# Seeded random input through the real event loop, sandboxed with bwrap.
# Arguments: first seed, run count, events per run. DNA_FUZZ_FOCUS=explorer,
# session or completion mixes scripted workflows in; DNA_FUZZ_MODE=release
# fuzzes the release build; DNA_FUZZ_GDB=<seconds> prints stacks for hangs.
# DNA_FUZZ_VIM=1 uses the Vim keymap profile; DNA_FUZZ_PLACE=1 docks and floats
# surfaces; DNA_FUZZ_TREE=1 uses the tree explorer; DNA_FUZZ_PICKER=compact or
# dropdown uses a slim picker.
fuzz first="1" runs="20" events="3000": (build "debug")
    python3 tests/fuzz_input.py {{first}} {{runs}} {{events}}

# Random terminal input (keys, escape sequences, mouse, pastes, resizes) for
# dna --tui through a pty, sandboxed with bwrap. DNA_FUZZ_MODE=release too.
fuzz-tui first="1" runs="20" chunks="600": (build "debug")
    python3 tests/fuzz_tui.py {{first}} {{runs}} {{chunks}}
