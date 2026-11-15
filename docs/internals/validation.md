# Validation and checks

## Checks and ownership

```sh
just smoke  # modules, native UI, PTY and optional grammar checks, debug and release
# Enable the offline grammar checks after this explicit download/build:
DNA_LANGUAGE_DIR="$PWD/build/test-languages" mise exec -- ./build/deps/install/bin/dna-language install dyn
# Exercise the real desktop driver with isolated test files too:
LD_LIBRARY_PATH="$PWD/build/deps/install/lib" python3 scripts/smoke.py
# Only when an isolated nested compositor throttles hidden windows:
# DNA_SMOKE_TIMEOUT_SECONDS=90 ... python3 scripts/smoke.py
```

Tests cover UTF-8 edits, selections, bounded undo/redo, search, capacity rollback,
file conflicts, permission preservation, recovery, symlink/FIFO rejection, layout
validation, multi-buffer undo/view restoration, close/quit cancellation, path
completion, staged explorer edits, preview cancellation, external-source/destination
changes, palette caching, and the native open/edit/save/create/rename/trash workflow. Synthetic native input exercises the actual event loop. Native platform tests
check pixel output, event translation, texture ownership and renderer recreation.
Direct GPU tests compare pixels against the software reference, allowing one
8-bit rounding step, and exercise batching, atlas eviction, failed texture
allocation/retry, framebuffer failure/retry, CPU-free popup targets, atlas
rollover ordering, cold/warm glyph batching and renderer recreation on Wayland
and X11.
Editor frame tests use test-only GPU readback for typing, syntax and motion.
Text tests check shaping, selection, UTF-8 source offsets and lifetime.
Physical keyboard and IME testing
remain separate.

The document owns its text, saved/checkpoint baselines, line index, and bounded undo deltas in an arena.
Unused text and undo capacity is reserved without eagerly initializing its pages.
Pane typography metadata is allocated when a pane is drawn and released when
the pane closes or becomes a split branch. Font changes invalidate existing
caches without allocating unused pane slots.
File/prompt/event bytes are copied before their source expires. Temporary file
reads use a rewindable scratch arena. Native text objects die before their font,
engine, and renderer. Queued events are processed in bounded batches before drawing, and unchanged
window titles are not resubmitted. Idle waits do not redraw. Trailing spaces
and indentation retain their layout width, including in cursor/selection geometry.
The editing, file, and layout modules are independent of the GUI backend.

Non-colocated jj, local only. No remote or publication. The project name DNA is
provisional; the extension architecture in DESIGN.md is not implemented yet.

## Rendering and latency checks

Native CPU rendering can be measured with `just bench-native-frames`, or
`python3 scripts/benchmark_native_frames.py --scenario document`. The isolated
probe draws production code at 960×640, 1920×1080 and 2560×1440; it excludes file
scanning, GPU work, presentation and physical input/display latency. Use a quiet
machine; `--cpu N` pins the measured child and `--budget-ms N` applies an optional
local p95 budget. Native raster tests compare exact pixels against frozen
references. Textures reuse storage between same-size frames; opaque fills and
one-to-one texture spans use bulk transfers. UI text layouts use a bounded
256-entry cache so common document gutters and picker labels fit together.
The file picker retains same-root rows while refreshing and publishes growing
cold-scan prefixes; generation checks still reject stale roots.


Reproducible local comparisons with Neovim, Helix, and Neovide are recorded in
[IMPLEMENTATION.md](../implementation.md#local-editor-comparison-2026-10-04), including
median/p95/worst timings, retained memory, completion scheduling, and measurement
limits. The benchmark scripts isolate their configurations and temporary files.

The default palette is neutral charcoal with restrained blue selection/cursor
accents. Semantic colors live in `src/theme.dyn`; built-in and custom theme files
can be selected with `:theme`.

Document and explorer rendering shape only the visible complete lines. Selections
are clipped to that range. Very long individual lines still require full-line
layout; this is not a large-file editor yet.

`tests/editor/render_reuse_smoke.dyn` checks unchanged multi-pane work and
invalidation; `edit_visibility_smoke.dyn` checks first-frame caret visibility.
The old SDL interposition timing drivers have been retired. Saved comparisons
in dated reports describe their original backend and are historical evidence,
not native performance claims. Native desktop input/display latency still needs
separate measurement; present-return traces do not include compositor scanout.

## Expanded validation

The file limit is 256 MiB minus one byte. Files of 16 MiB and more open as plain
text: syntax highlighting and language servers are skipped, and crash recovery
reloads them from disk rather than snapshotting their text (unsaved edits to a
large file are not crash-recoverable; save them). Tests cover full-capacity
loads and edits, highlighting near 1 MB, large Unicode selections, file I/O,
undo, search limits, and recovery. Document storage is reserved address space
that opts out of transparent huge pages, so a small file costs only its pages.

Native validation uses a real Wayland or X11 session. `just smoke` runs the
editor workflow and service ownership checks; `just soak` repeats native
resource checks. `just bench-buffer` measures the document engine independently
of the GUI. `python3 tests/package.py` verifies deterministic archive checksums
and relocated native startup on the current desktop; it does not qualify every
Linux distribution or physical display latency.
