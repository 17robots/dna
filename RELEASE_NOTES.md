# DNA 0.1.0-preview.16

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.35 compiler, SDK and runtime.

## Changes

- Updated the compiler, SDK and runtime to Dyn 0.1.0-preview.35, which adds
  faster decimal formatting, quotient/remainder reuse for runtime divisors and
  propagation of uniform arguments into private functions. No source changes
  were needed.
- Updated verified SDK pins for Linux, macOS and Windows and the Linux CI
  compiler download.

## Compatibility

Configuration, document and session formats are unchanged from preview.15.
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
