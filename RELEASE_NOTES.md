# DNA 0.1.0-preview.9

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.29 compiler, SDK and runtime.

## Changes

- Draw the native GUI through a GPU presenter with one glyph atlas and
  framebuffer-backed popups. Set `DNA_RENDERER=software` for the software
  presenter.
- Lower idle memory. Panes allocate storage only when used, fonts under
  `/usr/share/fonts` and `/usr/lib/fonts` are mapped read-only instead of
  copied, and Dyn preview.29 sizes file reads exactly and keeps small arenas
  off transparent huge pages. On the reference machine, idle private memory
  fell from 43.8 MiB to 30.0 MiB with an 8 MB Nerd Font.
- Install desktop entries for the GUI and TUI with `dna-install-desktop`.
- Pin verified Dyn preview.29 packages in mise and CI.

## Compatibility

Unchanged from preview.8. The application target remains Linux x86-64 and
needs compatible host glibc, a monospace font, and desktop libraries/graphics
drivers for GUI operation. Fonts outside the system font directories are still
copied into memory, so later changes to those files cannot fault the editor.

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
