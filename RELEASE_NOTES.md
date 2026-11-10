# DNA 0.1.0-preview.14

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.32 compiler, SDK and runtime.

## Changes

- Built with Dyn 0.1.0-preview.32. Measured with preview.31 against preview.13 on the same
  machine: editing in 1 MB to 100 MB files responds 1.1 to 1.3 times faster
  (median insert, backspace and paging latency), core buffer edits are about
  1.6 times faster, and the release binary is about 4% smaller. Startup time
  and memory use are unchanged.
- The GUI builds its text table on first use instead of at startup, and
  NVIDIA-only machines select the NVIDIA EGL vendor directly.
- Internal: the source follows the preview.32 language and standard library
  (one `{ value, failure }` result shape, `#slice`, parenthesized bit tests,
  one generics spelling, `f64` float literals).
  No change to configuration or behavior.

## Compatibility

Unchanged from preview.13. The application target remains Linux x86-64 and
needs compatible host glibc, a monospace font, and desktop libraries/graphics
drivers for GUI operation. See the archive's `build-info.json` for its minimum
glibc version. Both GUI and TUI are included. macOS and Windows ports now
build and pass CI, but editor releases for them are not available yet.

## Qualification

Release gates are formatting, the complete Linux smoke suite, deterministic
archive verification, extracted dependency resolution without checkout paths,
and extracted GUI startup.

Back up important files before trying this experimental preview. Broader desktop,
IME and sustained workload testing remains outstanding. See `PRERELEASE.md`.
