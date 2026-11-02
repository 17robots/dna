# DNA 0.1.0-preview.12

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.30 compiler, SDK and runtime.

## Changes

- `:languages` shows one row per language, grouped into Installed and
  Available, with syntax and server status on each row. A details pane shows
  the language's files, where its grammar came from, the server command and
  where it was found, why a server failed, and what `i` would install. `/` also
  filters by file extension, `R` starts or restarts a server and `l` shows its
  log.
- A crashed language server now shows one line with its last error instead of
  a popup of raw output.
- The file tree works like NERDTree. `Space e` closes it from anywhere and
  opens it when closed, `Space E` focuses it, and `[explorer] close_on_open`
  closes it after opening a file.
- In the command palette the arrow keys move through suggestions. Up at the top
  of the list steps into command history.
- New editing features: text objects, document and workspace symbol pickers,
  a git change gutter and Vim marks.
- Large files: language-server messages of 16 MiB and more are prepared off the
  main thread, so typing in a 40 MiB file no longer freezes. Text objects and
  syntax selection work above 16 MiB, and recovery covers edits up to 4 GiB.
- Fix text typed in the same input read as `O` or `:` being dropped, which
  affected fast pastes and quick `:w`.
- Fix `maf` and other text objects failing after the first 1,024 in a file.

## Compatibility

Unchanged from preview.11. The application target remains Linux x86-64 and
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
