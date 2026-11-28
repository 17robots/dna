# Building and running from source

## Dyn SDK migration

DNA pins one Dyn preview at a time and ports in batches; see
[dyn-versions.md](dyn-versions.md).

Current source uses **Dyn 0.1.0-preview.37**, pinned with verified platform
checksums in `mise.toml`. Its installed SDK includes the required `std/ui/box`,
native window bridge sources, and runtime objects; a sibling checkout is optional.

```sh
mise install
mise exec -- dyn --version
mise exec -- just run
# Build and run the optimized editor instead:
mise exec -- just run-release
```

For compiler development, set `DYN` to your matching compiler executable and
`DYN_SDK` to its source SDK directory. Leave both unset to use the installed SDK.

To build and open an isolated local preview:

```sh
python3 scripts/preview_sdk.py
# Or open another file with the same compiler and language server:
python3 scripts/preview_sdk.py path/to/file.dyn
```

The helper rebuilds native adapters and the editor with the matching runtime,
uses separate settings/state under `build/sdk-preview`, and opens the real GUI.
The helper uses `DYN` when set and otherwise the selected compiler. It rejects SDKs missing the
required UI modules before building dependencies.
The example in `examples/sdk-preview` also compiles and runs with that SDK.

Source now uses `#cast(type, value)`, function-value types, arena-first SDK
producers, current result fields, and JSON missing-value stubs. Required arena
allocations panic; bounded DNA adapters still return their existing capacity
failures. Owned arenas use pointer handles and chained blocks. Sparse document/App storage
stays explicitly uninitialized, with its existing initialization and reclamation
contracts. Document and configuration formats are unchanged. Sessions with more than 16
slots use format 3; older formats remain readable, but older DNA releases cannot
read format 3. Keep a separate session file when testing or rolling back.

See [SDK-MIGRATION-20261024.md](history/sdk-migration-20261024.md) for validation,
measurements, limits, and the preserved local baseline.

### Native macOS and Windows source builds

Native source builds use the pinned Dyn SDK. Install the platform providers
listed in [native CI](../.github/workflows/native-ports.yml). macOS uses Homebrew;
Windows x64 uses native Python, the Windows SDK, and MSYS2 UCRT64. On macOS, run
`python3 scripts/build_native.py --mode release` to build the Cocoa editor.

On Windows, run from PowerShell after installing the UCRT64 providers:

```powershell
$env:DNA_WINDOWS_PREFIX = 'C:/msys64/ucrt64'
mise exec -- python scripts/build_native.py --mode release --output build/dna.exe
.\build\dna.exe --gui
```

Keep the generated adjacent DLLs, ConPTY host, licenses, language helper and
`share/dna` data with the executable when moving it. Grammar builds and managed
language-server installation also require the configured MSYS2 tools. Windows
recovery flushes each atomic rename so it survives power loss as well as
process crashes.

## Tests

`just test` runs the fast checks and `just smoke` runs the full Linux suite.
Both call `tests/run.py`, which holds the step lists. Steps run in parallel
inside each stage, using half the CPUs; the build stage runs first, one build at
a time, because the editor checks use its binaries. Checks that measure time or
bounded memory run one at a time after the parallel group.

- `DNA_TEST_JOBS=1` runs every step in order.
- `DNA_TEST_ONLY=buffer_close,jobs` runs only those steps (builds still run).
- `DNA_TEST_TIMES=times.txt` appends each step's seconds to the file.

Tests never see your desktop display. `tests/private_display.py` removes
`DISPLAY`, `WAYLAND_DISPLAY`, `WAYLAND_SOCKET` and `NIRI_SOCKET` before a test
starts, so checks that need a native window print SKIP locally. Test windows on
a live Wayland session have crashed `xwayland-satellite` and closed every X
application with it. CI runs the window checks in a private headless weston and
sets `DNA_TEST_DISPLAY=private`; do the same to run them locally.

## Run

`dna --version` (or `dna version`) prints the application version and exits
without opening the editor. `dna --help` (or `-h`) prints usage. Any other
argument starting with `-` is rejected with exit status 2; use `dna --
version` or `dna -- -name` to open a file with such a name. Startup problems
the user can fix (no terminal for `--tui`, no display, no font) print a
`dna:` message and exit with status 1 instead of panicking.

`just build`, `just run`, and `just run-release` now use the native Linux GUI:
Dyn `std/ui` windowing/rendering and native HarfBuzz/FreeType/FriBidi text.
Wayland is selected when `WAYLAND_DISPLAY` is set; otherwise X11 is used.
These binaries do not link SDL or SDL_ttf. Dyn preview.28 or newer is required. To explicitly select a backend, run
`python3 scripts/build_native.py --backend wayland --release` (or `x11`).
The GUI draws rectangles, selections, triangles, and text directly through
OpenGL 3.3. Glyph masks use a bounded 1 MiB atlas; vertices use a fixed-size
batch buffer. It does not allocate or upload a full-window CPU framebuffer.
Popup targets also render directly into GPU framebuffer textures, using
premultiplied alpha for transparent composition. Normal drawing retains no
CPU popup image and performs no popup readback/upload. A temporary CPU backup
preserves live textures only when recreating the renderer. Set `DNA_RENDERER=software` to use
the previous full-frame software renderer for comparison or troubleshooting.
Both paths retain the same HarfBuzz/FreeType/FriBidi shaping and font metrics.
Font files use a single bounded owned allocation, preserving their bytes if the
file is later replaced or truncated. Large icon fonts still retain their file
contents for shaping and glyph rasterization.

Native runtime libraries remain under `build/native-wayland` or `build/native-gui`;
keep these directories with the local build.

All GUI builds, including module profiles and direct `dyn build src` / `dyn run src`,
use the native implementation. The SDL compatibility backend and dependency
builder have been removed. Direct source builds select Wayland; use the build
helper's `--backend x11` option for X11.

Requirements: Linux x86-64, Dyn preview.28 or newer, Wayland/EGL or X11,
FreeType, HarfBuzz, FriBidi, PCRE2, utf8proc, libvterm, Tree-sitter (0.25+), and Fontconfig development libraries, CMake, Python 3.12+, a C compiler,
GNU binutils (`nm`, `ar`, `objcopy`), and `just`. Native dependencies are built locally with `just deps`; graphics and text
providers come from the selected SDK and system packages.
All DNA-owned editor code and native adapters are written in Dyn, including
PTY/libvterm integration, Tree-sitter workers, filesystem operations, search,
synchronization and memory accounting. Native test executables and interposers
are also Dyn. External libraries and the Dyn runtime retain their own implementation
languages; this is not a dependency-free build. The C compiler builds external
dependencies and generated header ABI probes, and links Dyn objects.
The helper does not install system packages. After changing native dependencies,
use the selected compiler with `--no-cache` for a direct static rebuild;
external archive changes need an explicit rebuild.
`just build` uses the freshly rebuilt shared adapter. Regex selection uses the system PCRE2 library
(`libpcre2-dev` on Debian/Ubuntu, `pcre2-devel` on Fedora, `pcre2` on Arch).

Use the installed compiler and SDK selected above for this working source.
For daily development, `just run` uses
cached debug builds and the 2 GiB memory guard. `dyn run src/` also reuses
unchanged modules. Build times depend on the machine, dependencies and cache;
use the measurements below for the workflow you want to compare.

```sh
just run                 # empty buffer
just run README.md       # open an existing file
```

With mise activated in your shell, direct Dyn commands work too:

```sh
just deps                # once after cloning, builds native support and the window bridge
mise trust               # trust this repository's mise.toml
# Let the shell refresh its environment (or leave and re-enter the directory).
dyn run src
```

`mise.toml` supplies the local native-library search paths for both the compiler
and runtime. Without shell activation, use `mise exec -- dyn run src` instead.
No SDL libraries are built or linked. Direct builds use the native support
archive and shared SDK window bridge. Keep `build/deps/install/lib` available at
runtime (mise supplies its library path); packaged builds carry their native
libraries beside the executable.

Start in normal mode. Press `i` to type, Escape to return to normal mode,
`:write` then Enter to save, and `:` for searchable commands. Space opens a shortcut guide;
Ctrl shortcuts remain alternatives. An unnamed
buffer prompts for a new destination when saved. File paths in Open/Save As
are relative to the current project directory (`:pwd`, changed with `:cd`); directory-buffer create
and rename operations use the directory being displayed.

The file picker (`Space f` or `:open`) shows a flat list of files beneath
the working directory. Type a filename fragment or fuzzy query; nested results
show their relative paths. Arrows select, Page Up/Down pages through results, Enter opens, and Tab fills the selected
path. A literal directory prefix (including `~/` or an absolute path) narrows the
search root. Directories never become selectable explorer rows. Use `Space e`
for the separate editable explorer, or `:open path` for an explicit file path.

The file index is cached while the picker is open and refreshed on reopening.
It skips hidden entries, `build`, `target`, and `node_modules`, and does not follow
symlinks. It currently indexes up to 2,048 files, visits 8,192 entries, and descends
12 directory levels; limits and read errors are shown. Up to 128 matches are
listed. This is a bounded built-in scan, not a gitignore-aware project index.
No shell expansion of environment variables or globs is performed.

Text uses antialiased fonts, 1.5× line spacing, and display-aware scaling. Zed Mono
is preferred, with Noto Sans Mono as fallback. Choose a font with
`DNA_FONT=/absolute/path/font.ttf just run`. No fonts are bundled.
