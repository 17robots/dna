# DNA 0.1.0-preview.10

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.30 compiler, SDK and runtime.

## Changes

- Sharper text. Glyph coverage was blended linearly, which thinned
  antialiased edges and washed out light text on dark themes. Coverage is now
  gamma-corrected once per cached glyph; shapes and spacing are unchanged.
- Helix keymap additions: `Alt-.` repeats the last `f`/`t` motion; `Ctrl-a`,
  `:increment` and `:decrement` change numbers in every selection; `|`, `Alt-|`,
  `!` and `Alt-!` pipe selections through the shell (`:pipe`, `:pipe-to`,
  `:insert-output`, `:append-output`); `*` searches whole words and `Alt-*`
  the exact text; `Alt-J` joins lines and selects the spaces; `Alt-a` and
  `Alt-I` select all syntax siblings or children; registers `_`, `+`, `*`,
  `"` and read-only `/`, `%`, `#`, `.`.
- Jump list: `Ctrl-o` goes back, `Ctrl-i` or `Tab` forward, `Ctrl-s` saves the
  position. `gg`, `ge`, `G`, searches, language-server goto and the
  diagnostics list record jumps, and saved positions follow edits.
- **Breaking:** `Ctrl-O` (open) and `Ctrl-S` (save) are removed. Use `Space f`
  or `:open`, and `:w`.
- Vim `*` matches whole words.
- Dyn preview.30 underlines unknown types without the preceding `: `.
- Internal cleanup: shared selection helpers, direct per-pane text caches and
  frame requests separated from tracing.

## Compatibility

Unchanged from preview.9. The application target remains Linux x86-64 and
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
