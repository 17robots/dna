# DNA 0.1.0-preview.8

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.28 compiler, SDK and runtime.

## Changes

- Add `dna --version` and `dna version`, available without a display or terminal.
- Replace the SDL GUI and text backends with Dyn's native Wayland/X11 windowing,
  rendering, font discovery and HarfBuzz/FreeType/FriBidi text layout.
- Use shared persistent UI boxes for identities, layout, hit testing and owned
  frame text; retain DNA's configurable editor geometry and motion.
- Improve native input, clipboard handling, popup geometry and render reuse.
- Grow the document directory beyond 16 buffers while preserving stable owners,
  asynchronous identities and bounded allocation-failure behavior.
- Reduce idle work and reuse text, syntax and terminal storage, with regression
  checks for resource lifetimes, rendering and editing workflows.
- Pin verified Dyn preview.28 packages in mise and CI. Installed SDK builds no
  longer require a sibling compiler checkout or its private test harness.
- Include both Wayland and X11 GUI binaries in the Linux archive; the launcher
  selects Wayland when WAYLAND_DISPLAY is set, otherwise X11. Both support TUI.

## Compatibility

The application target remains Linux x86-64. The archive includes native
libraries but requires compatible host glibc, a monospace font, and desktop
libraries/graphics drivers for GUI operation. `build-info.json` records the
archive's actual minimum glibc version. Windows/macOS host and cross-object
checks do not qualify a full editor release on those platforms.

Configuration and document formats remain compatible. Sessions above 16 slots
use format 3; formats 1 and 2 remain readable. Older DNA releases cannot read
format 3. Use a separate session file when testing or rolling back.

## Qualification

Release gates are formatting, the complete Linux smoke suite, deterministic
archive verification, extracted dependency resolution without checkout paths,
and extracted GUI startup. Clipboard waits honor SDK completion with a 30-second
application limit. Current evidence and any remaining limitations are
recorded in `build/release-*.log` and `build/release-readiness.json`. Static reviews
are scoped checks, not an exhaustive correctness or security audit.

Back up important files before trying this experimental preview. Broader desktop,
IME and sustained workload testing remains outstanding; no physical input-to-
display latency or universal performance claim is made. See `PRERELEASE.md`.
