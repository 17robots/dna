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
# dyn fmt skips nested module directories, so visit each one.
fmt:
    find src tests examples -name '*.dyn' -printf '%h\n' | sort -u | xargs -n1 "$DYN" fmt
fmt-check:
    find src tests examples -name '*.dyn' -printf '%h\n' | sort -u | xargs -n1 "$DYN" fmt --check
test:
    python3 tests/sdk_requirements.py
    python3 tests/migrate_casts.py
    python3 tests/host_environment.py
    python3 tests/json_scratch.py
    python3 tests/owned_arena.py
    python3 scripts/test.py
# Checks never read your own config, trust store or recovery files: a personal
# setting such as frontend = "tui" must not change what they exercise.
smoke:
    rm -rf build/test-home && mkdir -p build/test-home/config build/test-home/state
    XDG_CONFIG_HOME="$PWD/build/test-home/config" XDG_STATE_HOME="$PWD/build/test-home/state" just _smoke
_smoke: deps test
    python3 scripts/test_host.py
    python3 scripts/test_host.py filesystem
    python3 tests/build_guard.py
    python3 tests/benchmark_cleanup.py
    python3 tests/render_report_latency.py
    python3 tests/static_native.py
    python3 tests/dyn_support.py
    python3 tests/native_fonts.py
    python3 tests/clipboard_deadline.py
    python3 tests/native_foundation.py
    python3 tests/native_triangle_bounds.py
    python3 tests/native_bitmap_raster.py
    python3 tests/native_fill_spans.py
    python3 tests/native_texture_raster.py
    python3 tests/native_present_reuse.py
    python3 tests/native_typing_frames.py
    python3 tests/native_syntax_pending_frames.py
    python3 tests/native_syntax_single_pass.py
    python3 tests/native_syntax_settled_frames.py
    python3 tests/native_syntax_idle.py
    python3 tests/native_frame_sequence.py
    python3 tests/ui_text_working_set.py
    python3 tests/native_sync.py
    python3 tests/native_clock.py
    python3 tests/tui_storage.py
    python3 tests/line_layout_reuse.py
    python3 tests/motion_policy.py
    python3 tests/surface_entrance_policy.py
    python3 tests/popup_surface_policy.py
    python3 tests/popup_surface_motion.py
    python3 tests/surface_entrance.py
    python3 tests/entrance_command_text.py
    python3 tests/native_draw_opacity.py
    python3 tests/completion_escape.py
    python3 tests/completion_window.py
    python3 tests/buffer_close.py
    python3 tests/presentation_policy.py
    python3 tests/status_focus.py
    python3 tests/status_file_motion.py
    python3 tests/explorer_column_motion.py
    python3 tests/explorer_column_native.py
    python3 tests/explorer_window_motion.py
    python3 tests/theme_contrast.py
    python3 tests/typography_metrics.py
    python3 tests/picker_viewport.py
    python3 tests/tree_search_navigation.py
    python3 tests/background_worksets.py --expect bounded
    python3 tests/process_transport.py
    python3 tests/process_close.py
    python3 tests/native_abi.py
    python3 tests/terminal_review.py
    python3 tests/terminal_boundaries.py
    python3 tests/terminal_workset.py --expect-bounded
    python3 tests/rpc.py
    python3 tests/jobs.py
    python3 tests/server_install.py
    python3 tests/disk.py
    python3 tests/native_disk_dynamic.py
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
    python3 tests/syntax_changes.py
    python3 tests/syntax_consistency.py
    python3 tests/syntax_dyn_fullfile.py
    python3 tests/thread_join.py
    python3 tests/picker_index.py
    python3 tests/picker_responsiveness.py
    python3 tests/picker_progress.py
    python3 tests/syntax_faults.py
    python3 tests/recovery.py
    python3 tests/plugins.py
    python3 tests/lsp_storage.py
    python3 tests/lsp_workset.py
    just build debug
    just build release
    python3 tests/tui_usability.py
    python3 tests/version.py --binary build/dna-debug --binary build/dna-release
    python3 scripts/build_native.py --backend wayland --release
    python3 scripts/build_native.py --backend x11 --release
    python3 scripts/compile.py "$DYN" build examples/plugins/uppercase --debug --output examples/plugins/uppercase/uppercase
    python3 scripts/build_smoke.py
    DNA_SMOKE_TIMEOUT_SECONDS="${DNA_SMOKE_TIMEOUT_SECONDS:-90}" python3 scripts/smoke.py
    python3 tests/launch.py
    DNA_NATIVE_BACKEND=wayland python3 tests/native_platform.py
    python3 tests/native_shaping.py
    python3 tests/native_selection.py
    python3 scripts/profile.py minimal release
    python3 scripts/profile.py terminal release
    python3 tests/native_only.py --binary build/dna-debug --binary build/dna-release --binary build/dna-minimal --binary build/dna-terminal
    python3 tests/version.py --binary build/dna-minimal --binary build/dna-terminal
    python3 tests/tui_render.py terminal

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
