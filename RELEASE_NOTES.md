# DNA 0.1.0-preview.17

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.36 compiler, SDK and runtime.

## Changes

- Updated the compiler, SDK and runtime to Dyn 0.1.0-preview.36, the
  standardization release: `Type{}` literals only, no shadowing, `for x, i`
  index loops, text `case`, `{value, failure}` results with `io.Failure`,
  sticky void writers and debug overflow checks on by default.
- Ported production sources, examples, the installer and host tests to the
  new language and std names.
- Hashes (FNV, git gutter baselines, disk fingerprints) and the LSP escape
  scan now wrap explicitly with `math.wrapping_*`, so debug builds keep
  overflow checks on everywhere else.
- Updated verified SDK pins for Linux, macOS and Windows and the Linux CI
  compiler download.

## Compatibility

Configuration, document and session formats are unchanged from preview.16.
Plugins written in Dyn must be ported to Dyn preview 36; see the Dyn
`docs/migrations/standard-20261113.md` guide and `tools/migrate-standard.py`.
The application package remains Linux x86-64 and requires compatible host
glibc, a monospace font, and desktop libraries/graphics drivers for GUI use.
See the archive's `build-info.json` for its minimum glibc version. Both GUI
and TUI are included. macOS and Windows source builds remain available;
editor release packages for those platforms are not available yet.

## Qualification

Release gates are formatting, the complete Linux smoke suite, deterministic
archive verification, extracted dependency resolution without checkout paths,
and extracted GUI startup.

See `PRERELEASE.md` for the experimental preview's remaining limitations.
