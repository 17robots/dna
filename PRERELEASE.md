# DNA experimental prerelease

This preview is intended for early testing. It is not a claim of daily-driver
reliability or compatibility with every Linux distribution.

## Known limitations

- The packaged target is Linux x86-64. Check `build-info.json` for the required
  glibc version. The October 5 audit build requires glibc 2.43; it is not
  compatible with Ubuntu 24.04's glibc 2.39. Display/graphics-driver libraries and a monospace font are
  supplied by the host. Other operating systems are not covered by this build.
- Language servers are separate installations. Dyn semantic completion can take
  hundreds of milliseconds in large projects. DNA shows matching file words
  first and filters cached results locally; these plain-word suggestions do not
  include the signatures or snippets supplied later by the server.
- Completion reserves eight rows, clipped to the pane; unused rows remain empty.
- Limits include 16 buffers, 8 views, and 268,435,455 text bytes per buffer.
  Large-file support does not imply every operation has constant latency.
- Complex mixed-direction text, desktop IME integration, and different GPU,
  display, and terminal combinations need broader real-world coverage.
- Recovery is asynchronous. A crash may lose edits newer than the last completed
  recovery snapshot. It does not replace explicit saves or backups.
- Opening a nonexistent file from the command line reports an error. File
  symlinks are rejected by the file loader; directory symlinks are supported.
- Plugin permission checks are not an operating-system sandbox.

## macOS and Windows release status

DNA does not yet have a native macOS or Windows release. The pinned Dyn SDK
provides macOS ARM64 and Windows x86-64 compilers, but compiler availability
alone does not make DNA portable. The current blockers are in this repository:

- `src/native/dyn/notify.dyn` uses Linux epoll and eventfd; `disk.dyn` uses
  inotify. Other platforms need readiness and file-change implementations.
- `tty.dyn`, `process.dyn`, and `sync.dyn` assume Linux/glibc structures,
  constants, signals, and process behavior. `tests/native_abi.py` explicitly
  checks those Linux layouts. Each port needs its own ABI checks and terminal,
  subprocess, thread, and shutdown tests.
- `recovery.dyn` binds glibc's `__errno_location`. Recovery and save paths need
  platform-specific error handling and filesystem validation.
- `scripts/deps.py` and `scripts/package.py` produce ELF shared libraries,
  GNU linker scripts, and Linux runtime paths. macOS needs Mach-O dependency
  packaging; Windows needs PE/DLL packaging and a portable build wrapper
  (`scripts/compile.py` currently imports Unix-only Python modules).
- `src/syntax.dyn` and `installer/main.dyn` call Linux syscall 79 directly
  for the working directory; these calls need a portable replacement.
- The language installer uses POSIX shell commands, symlinks, executable mode
  bits, and `parser.so`. Config paths, managed executables, parser loading,
  install/update/uninstall, and bundled tools need platform-specific validation.

Port the native boundary first, then build on native CI runners and test GUI,
TUI, editing, save/recovery, language management, and relocation of the extracted
archive. Publish platform assets only after those checks pass. Adding a CI
matrix alone would produce failing builds, not usable releases.

## Launch

```
./dna path/to/file.dyn
./dna path/to/project
./dna --tui path/to/project
```

Directory launches set the project directory and open the configured explorer.
Quote paths containing spaces; use `--` before a path that matches an option.

## Validation — October 5, 2026

Passed checks:

- Debug/release unit and native UI suites: Vim/Helix pair selections (including
  the reported `vi{` case), undo/redo, Unicode, completion/snippets, launch
  arguments, unsaved-buffer prompts, and session restoration.
- External-file reload and dirty-buffer conflict protection; disk watcher
  replacement/deletion and polling fallback.
- Partial-write failure and interrupted-save tests preserved original files.
  Recovery setup/flush failures, retries, and interrupted replacement preserved
  the last complete record; abrupt process exit left a recoverable snapshot.
- GUI input fuzzing: seeds 301–304, 1,000 events each, separately for Helix and
  Vim (8,000 events total). TUI fuzzing: seeds 301–303, 300 chunks each.
- Resource lifecycle tests: 60 cycles with no descriptor/thread growth; native
  allocation accounting and worker shutdown checks passed.
- Extracted archive startup, presentation, and shutdown with an isolated HOME
  and no development library paths, on the host with dummy and Wayland backends.
- Clean Arch container startup: extracted package and one host font only, no
  SDK, repository mount, network, or writable root filesystem. This is a
  headless startup check, not a cross-machine desktop interaction test.
- Repeated packaging produced identical archives; extracted checksums passed.

Reproduction commands (from the repository, with the pinned SDK):

```
mise exec -- just smoke
mise exec -- env DYN_LIBRARY_PATH="$PWD/build/deps/install/lib" python3 tests/fuzz_input.py 301 4 1000
mise exec -- env DYN_LIBRARY_PATH="$PWD/build/deps/install/lib" DNA_FUZZ_VIM=1 python3 tests/fuzz_input.py 301 4 1000
mise exec -- python3 tests/fuzz_tui.py 301 3 300
mise exec -- env DNA_PACKAGE_IMAGE=docker.io/library/archlinux:base python3 tests/package.py
```

The container check requires the image already present locally. Logs from this
run are under `build/prerelease-*.log`; the exact container image ID and archive
hash are in `build/packages/container-check.json`.

## Release assessment

Suitable for an explicitly experimental preview on compatible Linux systems.
A general Linux release needs a build against an older supported glibc baseline
and testing on those target distributions. Broader desktop/IME testing and
sustained use on different projects remain outstanding. The local checks do not
establish that every edit is crash-safe or that memory cannot grow in other
workloads. The first release is `v0.1.0-preview.1`; it is explicitly marked as a prerelease.

## Preview 2

`v0.1.0-preview.2` fixes TUI syntax colors disappearing in splits and beside
docked explorers by aligning their geometry to terminal cells. Both explorer
styles now draw file/folder glyphs in the TUI. Ghostty includes Nerd Font
symbols; other terminals may need a Nerd Font configured.

GUI font-family suggestions now contain family names instead of paths. TUI
`:font` explains that the terminal owns font family and size.

Regression checks cover odd terminal dimensions, nested splits, resizing, all
four dock sides, explorer icon toggles, and font suggestions. Full TUI tests
passed for the normal release and terminal-only build; debug/release native UI
checks passed. Platform and glibc requirements remain unchanged.
