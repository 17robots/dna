# DNA

A native modal editor prototype written in Dyn. The window shows your document;
line numbers and a slim status line provide orientation. Commands, search, files,
and buffer switching appear as keyboard-invoked popups.
No web runtime. [DESIGN.md](DESIGN.md) records the broader product direction.

## Install the prerelease with mise

The Linux x86-64 preview requires **glibc 2.43 or newer**, a system monospace
font, and desktop display libraries for GUI mode. It does not run on Ubuntu
24.04's glibc 2.39. See [PRERELEASE.md](PRERELEASE.md) before installing.
Preview.11 changes are recorded in [RELEASE_NOTES.md](RELEASE_NOTES.md).

```sh
mise use -g 'github:17robots/dna[prerelease=true,strip_components=1,bin_path=.]@0.1.0-preview.11'
dna path/to/file.dyn
dna path/to/project
```

Use `mise exec github:17robots/dna@0.1.0-preview.11 -- dna path/to/project`
if mise is not activated in your shell. The explicit `bin_path=.` selects the
archive's launcher, which loads its bundled libraries. The Dyn SDK is needed to
build DNA, but is not required to run this package. Language servers are
installed separately.

This uses [mise's GitHub backend](https://mise.jdx.dev/dev-tools/backends/github.html);
no separate mise plugin or registry entry is required.

### Desktop launchers

Packages from preview.9 on include `dna-install-desktop` and standard entries
under `share/applications`. Run the helper after extracting the package:

```sh
./dna-install-desktop
```

It registers **DNA** (`--gui`) and **DNA (Terminal)** (`--tui`, `Terminal=true`)
in `$XDG_DATA_HOME/applications`, defaulting to `~/.local/share/applications`.
The entries use the package launcher's absolute path; fuzzel and other desktop
menus need no mise environment or PATH changes. The terminal entry uses the
terminal configured by your desktop launcher. Run the helper again after moving
or upgrading the extracted package. Setup needs a POSIX shell and `awk`.

For mise releases that include the helper, add this to the existing DNA tool
section of your global mise config to refresh the entries after each install:

```toml
[tools."github:17robots/dna"]
# Keep your existing version, asset and checksum settings.
postinstall = '"$MISE_TOOL_INSTALL_PATH/dna-install-desktop"'
```

To register an older installation, such as preview.8, from this checkout:

```sh
./packaging/linux/dna-install-desktop --launcher "$(mise which dna)"
```

To remove the menu entries, delete `dna.desktop` and `dna-tui.desktop` from that
applications directory. Setup registers launchers; choose default file
associations separately in your desktop settings.

## Dyn SDK migration

Current source uses **Dyn 0.1.0-preview.30**, pinned with verified platform
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

See [SDK-MIGRATION-20261024.md](SDK-MIGRATION-20261024.md) for validation,
measurements, limits, and the preserved local baseline.

## Run

`dna --version` (or `dna version`) prints the application version and exits
without opening the editor. Use `dna -- version` to open a file named `version`.

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

## Settings and fonts

Copy [config.example.toml](config.example.toml) to `~/.config/dna/config.toml`.
`XDG_CONFIG_HOME` and `DNA_CONFIG` override this location. Config is loaded at
startup; `:config-reload` applies edits without restarting. `:config` opens an
existing config file. DNA does not create or overwrite your personal config.

### Modules and build profiles

DNA is built from module slots: **keymap** (`helix`, `vim`), **frontend** (`gui`,
`tui`), **explorer** (`buffer`, `tree`) and **picker** (`full`, `compact`,
`dropdown`). Choose them in config:

```toml
[modules]
keymap = "vim"
frontend = "auto"
explorer = "buffer"
picker = "full"
```

`:modules` lists the active module in each slot and what this build includes;
`:module keymap vim` (or `:keymap vim`) switches for the session. A module the
build leaves out falls back to the slot's default with a message, and `lock`
can pin any slot.

A build profile chooses which modules are compiled in. `just build` includes
everything; `just build-profile minimal` builds `build/dna-minimal` from
[profiles/minimal.toml](profiles/minimal.toml) (Helix keys only). Profiles are
files like:

```toml
keymaps = ["helix", "vim"]
frontends = ["gui", "tui"]
explorers = ["buffer"]
pickers = ["full"]
```

in `profiles/` or `~/.config/dna/profiles/`. `scripts/profile.py --keymaps helix
--name small` builds one without a file. Dyn has no conditional compilation, so
a profile build stages `src/` without the modules left out and puts stubs from
`modules/stubs/` in their place; a left-out module's code is not in the binary.
Helix keys, the editable explorer and the full picker are the shared base and
stay in every profile; a profile needs at least one frontend.

`just build-profile terminal` ([profiles/terminal.toml](profiles/terminal.toml))
builds `build/dna-terminal` with only the terminal frontend. The GUI backend
(`src/platform/gui.dyn`, `src/text/native.dyn`) is replaced by concrete native interface stubs and
the native library is built without GUI or Fontconfig code, so the binary links
no graphics libraries or Fontconfig and runs where there is no display or graphics stack (servers,
containers, SSH). It always starts in the terminal.

### Explorer and picker styles

`explorer = "buffer"` (the default) is the editable explorer described under
[Editable explorer](#editable-explorer). `explorer = "tree"` makes Space e
open the project as a collapsible tree, docked on the left (`[place.explorer]`
docks it elsewhere or floats it). A docked tree stays beside the panes after
focus returns to the editor; Space e or a click moves focus back to it.

| Key | Tree action |
| --- | --- |
| `j` `k` / arrows, `g` `G` (Vim: `gg` / `G` and counts), PageUp/PageDown, Ctrl+d/u | move |
| `/`, Enter; `n` / `N` | search visible filenames; confirm, then next / previous match |
| Enter | open a file, or fold/unfold a folder |
| `l` / Right | unfold, then step into a folder; open a file |
| `h` / Left | fold, or go to the parent folder |
| `-` / Backspace | make the root's parent the root |
| `.` | make the selected folder the root |
| `a` | new file beside the selection (inside it for a folder); end with `/` for a folder, and use `dir/sub/name` to create the folders on the way |
| `r` | rename (the prompt starts with the current name) |
| `c` / `m` | copy / move to a path relative to the entry's folder (`../x` works) |
| `d` | move to `.dna-trash` beside it, after confirmation |
| `R` | reload from disk |
| `e` | edit the selected folder as text in the editable explorer |
| Esc | back to the editor (a floating tree closes) |
| `q` / Escape | close the tree (Space e opens it again) |

Tree search jumps through visible rows without changing folder expansion; Escape
cancels an active query and restores the prior selection. While entering a query,
Up/Down and Ctrl-N/P/J/K browse matches without leaving search. Normal key overrides
also apply in the tree.

The tree opens on the current file, keeps open folders across reloads and
hides `.git`. While it is open it watches its root and every open folder, so
files created, renamed or deleted by anything (a shell, git, the editable
explorer) show up at once. It holds up to 4096 rows.

`picker = "full"` is the large picker with a preview. `compact` sizes file,
buffer and resource pickers like the command palette (query and matches only,
up to 12 rows). `dropdown` does the same but hangs pickers and the command
palette from the top edge of the window. `[place.picker]` and
`[place.palette]` still override where they go.
Picker rows fit the final placed height, and resizing keeps the selected match
visible even when the query and selection have not changed.

Launch with a file or directory: `./dna src/main.dyn` opens the file;
`./dna ./src` uses that directory as the project and opens the explorer.
Paths containing spaces must be quoted. Use `./dna -- --gui` to open a file
literally named `--gui`. The first path is used; `--gui` and `--tui` select
the frontend and may appear before or after it (before `--`).

### Terminal frontend

`dna --tui file` runs inside the terminal instead of opening a window; `--gui`
forces a window. Without a flag, `[modules] frontend` in the global config
decides: `gui`, `tui`, or `auto` (the default), which picks the terminal only
when there is no `WAYLAND_DISPLAY`/`DISPLAY` and DNA's input and output are a
terminal. The frontend is personal: a project `dna.toml` cannot set it.

The terminal frontend draws the same layout in character cells: panels get
box-drawing frames, colors use 24-bit SGR, and only changed cells are written.
It reads the kitty keyboard protocol when the terminal offers it (so Escape,
Ctrl+I and Tab stay distinct) and legacy sequences otherwise, SGR mouse
reports, and bracketed paste. Copying goes to the system clipboard through
OSC 52. Terminal panes work inside it. Leaving DNA (including through a crash
or a fatal signal) restores the terminal's screen, modes and cursor.

Motion is reduced and the font settings are ignored.

Colors are 24-bit when the terminal advertises it (`COLORTERM=truecolor` or
`24bit`, a `TERM` ending in `-direct`, or kitty, Alacritty, foot, WezTerm,
Ghostty and Contour by name) and the nearest of the xterm 256 otherwise;
`DNA_TRUECOLOR=1` or `0` overrides. Diagnostics are colored curly underlines
on terminals known to draw them (kitty, WezTerm, foot, Ghostty, Contour and VTE
ones) and plain underlines elsewhere; `DNA_UNDERCURL=1` or `0` overrides. Bold,
italic and underlined output from programs in terminal panes keeps its style.
A paste from the terminal arrives whole: a terminal pane receives it as a
bracketed paste, a document inserts it as is (no auto-pairs or indentation)
and nothing in it runs as a key. Shift, Alt and Ctrl held during a click
come from the terminal's mouse report, so Shift-click extends a selection.
`:suspend` (`:sus`, `:stop`, and Ctrl+Z with Vim keys) stops DNA as a shell
job; `fg` brings it back.

`:frontend tui` / `:frontend gui` (or `:module frontend tui`) moves the running
session to the other frontend: unsaved text, splits, cursors and filetypes are
saved to `$XDG_STATE_HOME/dna/handoff-PID.session`, DNA shuts down cleanly and
starts again on the other frontend, which restores the session and deletes the
file. Session values (`:set`, `:theme`, `:keymap`, `:module`, placement) come
along. Undo history starts fresh, and language servers restart. The switch is
refused when the target cannot work (no terminal on DNA's input and output, or
no `WAYLAND_DISPLAY`/`DISPLAY`), while terminal panes are open (their shells
cannot move), with staged explorer edits, or when `lock` pins `frontend`.
Changing `frontend` in the config applies at the next launch; it never pulls a
running editor into another place by itself.
If restoration fails, the handoff file is preserved and the error gives its path
for `:session-restore`. It is removed only after a successful handoff restore.

### Placement

Window popups (`palette`, `picker`, `dialog`, floating `explorer`, and popup
`terminal`) share a top-center anchor, six percent down the window. Pickers,
the command palette and key menus settle into their anchors from a small
centered opening shape. The editable explorer expands from its left edge. Click
bounds follow the painted frame; dismissal releases input immediately while
the editable explorer briefly retracts its retained visual layer. Completion and
hover remain near the caret, key menus keep
their contextual position, and a docked explorer stays docked. Each surface can
still override its placement:

```toml
[place.picker]
anchor = "top-right"   # top-left top top-right left center right bottom-left bottom bottom-right
width = 0.45           # 0–1 is a fraction of the window; above 1, logical pixels
height = 0.6

[place.explorer]
side = "left"          # dock: left right top bottom; the panes make room
size = 0.25

[place.completion]
mode = "cursor"        # next to the caret (completion and hover default to this)
```

`mode` is `float`, `dock` or `cursor`; `anchor` implies float and `side` implies
dock. `mode = "default"` returns the surface to its usual place; keys after it
in the section still apply. `margin` sets a float's distance from the window edge. A docked surface
takes its strip from the editor panes only while it is open, in the order listed
above. `:place picker top-right`, `:place explorer dock right 0.3`, `:place
terminal float bottom 0.9 0.35` and `:place hover default` change placement for the
session. With the mouse, drag a docked surface's inner edge to resize it, or
drag a floating panel by its top edge to move it (the pointer turns into
resize arrows or a move cursor over those handles); it settles at the nearest of
the nine anchors when released. Mouse and `:place` changes last for the
session. `lock = ["place"]` (or `"place.picker"`) pins placement, including
against the mouse.

### Project config (`dna.toml`)

A `dna.toml` in the project directory, or the nearest ancestor that has one,
applies over the global config with the same format; it reloads when edited and
when the project directory changes. Some keys never come from a project file:

- **Locked keys.** `lock = ["theme", "languages", "keys.normal"]` in the global
  file pins keys, whole sections, or `section.key` entries. Locks only live in the
  global file, and also refuse in-editor changes such as `:keymap`.
- **Personal keys.** Keymap, frontend, theme, font, font family, fallback font,
  font size and line height are yours; even a trusted `dna.toml` cannot set them.
- **Keys that run programs or load files** (`shell`, task commands, key
  bindings and language `server`/`formatter`/`auto_start`/`format_on_save`)
  wait for `:trust`. Trust stores a SHA-256 of the file
  in `$XDG_STATE_HOME/dna/trust` (default `~/.local/state/dna/trust`); any edit
  to `dna.toml` asks again.

`:config-sources` shows the global and project files, what is locked, which keys
came from the project, and which were ignored and why. An invalid `dna.toml`
keeps the global settings and reports the line. Command-line flags still win
for the launch they are given on.

Supported settings include `font_size` (8–72), `line_height` (1–3), `font` (font
file path), optional `fallback_font` for missing Unicode glyphs, `indent_width`
(1–16), `theme` (`charcoal`, `light`, or a theme file path), line-number/status options,
`reduced_motion`, `shell`, and `terminal_escape` (default `ctrl-backslash`).
In the GUI, `:font` opens a searchable list of installed monospace fonts; `:font /path/font.ttf`
applies an explicit file. Ctrl +/-/0 or `:zoom-in`, `:zoom-out`, `:zoom-reset`
change size; reset uses the configured size. Picker/zoom changes are temporary;
edit the config to persist them. `:set font_family` suggests installed family
names. In the TUI, the terminal emulator controls font family and size; `:font`
explains this instead of opening an ineffective picker.

GUI row spacing rounds up to a physical pixel and never falls below the primary
or configured fallback font's baseline plus descender height. This keeps status
labels and clipped menu rows legible at fractional scales; larger configured
line spacing is preserved.

This is a deliberately restricted TOML reader: flat assignments, decimal numbers,
booleans, quoted strings without escapes, full-line comments, and `[keys.normal]`
/ `[keys.space]` tables. Unknown/duplicate settings and invalid values report a
line number and preserve working settings. Up to 16 key overrides map key names
(single characters, F1–F12, `space`, `backslash`, optionally prefixed with
`ctrl-`, `alt-`, or `shift-`) to palette commands or the shared navigation actions
`move-up`, `move-down`, `move-left`, `move-right`, `page-up`, and `page-down`.
Navigation overrides work in documents and both explorers. Normal overrides do
not run while typing, selecting, completing a Vim prefix, or entering terminal text.

Layout files remain separate. Existing layout files containing font/display
settings remain compatible; loading one can override those settings until config
is reloaded. New layouts can omit `font_size` to preserve the current font size.

### Per-file rules and personal project settings

Indentation, whitespace cleanup and the formatter follow each file, including
files opened from another repository. The precedence is global configuration,
`.editorconfig`, the nearest `dna.toml` above the file, matching personal project
sections, then session `:set` values. Global locks apply throughout. Explicit
indentation takes priority over syntax-based indentation detection. Tab and
Helix/Vim indent commands use the resulting width and tab choice.

DNA reads `.editorconfig` files from the file's directory upward, stopping at
`root = true`, then applies them from outermost to nearest. Supported properties
are `indent_style`, `indent_size` (1–16 or `tab`), `tab_width` (1–16),
`trim_trailing_whitespace` and `insert_final_newline`. `unset` removes an inherited
EditorConfig value. Sections support wildcards, character classes, alternatives
and numeric ranges. Wildcard matching has a fixed work limit; patterns exceeding
it are treated as non-matches to keep input responsive. Encoding and
`end_of_line` conversion are not implemented;
existing line endings remain unchanged. `insert_final_newline = false` disables
adding a newline; it does not strip existing newlines.

Keep personal project choices in your global `config.toml`, without adding a
private file to every repository:

```toml
[project."~/work/api"]
theme = "nord"
font_size = 16
indent_width = 2
```

These sections accept top-level settings only. Paths are absolute or start with
`~/`; directory boundaries are respected, and matching sections apply in file
order. Personal choices need no trust because this is your global file. They
still respect global locks. Appearance follows the editor's project directory;
file rules follow each file. Shared `dna.toml` files cannot contain these sections.

`:config-sources` reports each file's effective rules and their sources. Saving
`.editorconfig` or `dna.toml` in DNA invalidates cached file rules. Use
`:config-reload` after externally changing rules for another repository or an
`.editorconfig`. Formatter commands still require trust when supplied by
`dna.toml`; they run from that file's project root (or its directory when no
`dna.toml` exists).

## Themes

Built-in themes: `charcoal` (default), `light`, `catppuccin-mocha`,
`catppuccin-latte`, `gruvbox-dark`, `gruvbox-light`, `nord`, `dracula`,
`tokyo-night`, `one-dark`, `solarized-dark`, `solarized-light`, `rose-pine`,
`rose-pine-moon`, `rose-pine-dawn`, `github-dark`, `github-light`, `ayu-dark`,
`ayu-mirage`, `ayu-light`, `monokai`, `kanagawa` and `everforest`. `:theme nord` switches immediately (the palette
suggests names as you type), `:themes` opens a searchable list, and `theme = "nord"` in `config.toml` keeps the choice. Each
built-in sets the editor, syntax, diagnostic and terminal ANSI colours, following
the upstream palette. `catppuccin-latte`, `gruvbox-light`, `solarized-light`,
`rose-pine-dawn`, `github-light` and `ayu-light` are light themes.

## Creating themes

Copy [themes/charcoal.toml](themes/charcoal.toml) or
[themes/light.toml](themes/light.toml), then edit the colours. Example:

```toml
base = "charcoal"
background = "#181818"
selection = "#354150"
syntax_keyword = "#AE9CBE"
terminal_red = "#B45F5F"
```

`base` names any built-in theme and supplies the colours (and italics) the file
does not set, so `base = "nord"` followed by one `background` line changes only
the background. Available UI roles are `background`,
`surface`, `border`, `line`, `text`, `muted`, `selection`, and `cursor`. Syntax roles
are `syntax_comment`, `syntax_string`, `syntax_keyword`, `syntax_function`,
`syntax_type`, and `syntax_constant`. ANSI roles are `terminal_black`, `terminal_red`,
`terminal_green`, `terminal_yellow`, `terminal_blue`, `terminal_magenta`,
`terminal_cyan`, `terminal_white`, and their `terminal_bright_*` variants.
Colours must be quoted six-digit `#RRGGBB` values; unknown or duplicate keys fail
validation. Full-line comments are supported.

`italic = "comment keyword"` lists the syntax roles drawn in italics (any of
`comment`, `string`, `keyword`, `function`, `type`, `constant`; default
`comment`, `""` for none). The terminal frontend draws them with the
terminal's italics; windows render with one font face and keep them upright.

Use `:theme /path/to/my-theme.toml` to apply or reload it without restarting.
`:theme` with no argument displays the selected built-in name or custom file path.
`:theme charcoal`, `:theme nord` and the other names switch back to a built-in. Invalid files
leave the current theme intact. To persist the choice, put
`theme = "~/.config/dna/themes/my-theme.toml"` in `config.toml`, then run
`:config-reload`. These shared roles colour the editor, popups, syntax, and
terminal; a theme change does not require reparsing your files.

## Project directory, terminals, and tasks

- `:pwd` shows the project directory.
- `:cd path` changes it, with `~`, relative paths, and Tab completion of directory
  prefixes. `:cd` goes home; `:cd -` returns to the previous directory. Open file
  buffers keep their absolute paths. Pending explorer edits block the change.
- `Space t` (Space, then lowercase t) or `:terminal` opens a shell in a bottom split using one quarter of the active view,
  or focuses its existing pane. `:terminal-new` creates another shell below the active view.
  `:terminal-split` places a hidden terminal in a vertical split; an already visible terminal is focused.
  Terminals also appear in the buffer picker.
- Shell input goes directly to a real PTY. `pwd`, `cd`, Git, and interactive
  programs use the configured shell (`SHELL`, falling back to `/bin/sh`). A shell's
  `cd` affects only that terminal. New terminals start in the editor project root.
- Escape twice within 500 ms enters terminal normal mode; Ctrl+backslash also works.
  The first Escape reaches the terminal program immediately; the second is consumed by DNA.
  Intervening keys/text or changing focus resets the sequence. `i` returns to shell input;
  Escape or `q` hides a command-output popup. `:` opens editor commands, Space opens
  its menu, and Ctrl+W opens the window menu in terminal normal mode.
  Dismissing a popup or closing a split preserves the shell.
- Shift+PageUp/PageDown scroll; normal-mode PageUp/PageDown browse scrollback. Drag to
  select output; Ctrl+Shift+C copies the selection (or screen), Ctrl+Shift+V pastes
  with bracketed-paste support. Navigation-mode `y` copies too.
- Interactive shell buffers close automatically when the shell exits (including `exit` or Ctrl+D).
  Its terminal panes are removed too. Hidden shells close without changing focus.
- Terminal input mode sends every key to the program (Ctrl+X to nano, Ctrl+W to the
  shell, q to htop); only Escape twice or Ctrl+backslash leaves it.
- In terminal normal mode, Ctrl+X or `:bd` closes a terminal buffer. Running processes require confirmation before
  termination; quitting the editor also checks running terminals.
- `:run <shell command>` runs an explicit command in a new terminal buffer. Optional
  `build_command`, `test_command`, and `run_command` settings back `:build`, `:test`,
  and `:run`. `:error-next` opens the next `path:line:` diagnostic from the latest
  terminal's captured output, resolving paths against its initial working directory.

The first terminal backend is Linux/POSIX. It uses libvterm for ANSI colours,
alternate-screen programs, Unicode cells, and resize handling. Scrollback is bounded
at 2,000 lines, screen size at 240×100 cells, and diagnostic capture at 64 KiB.
Mouse input currently selects output rather than being forwarded to applications.
Terminal defaults, selection, cursor, and ANSI colours follow the selected theme.
Applications emitting explicit truecolour RGB retain those colours.

## Language installation and highlighting

Typing keeps the last parsed colors on text that the revision journal proves
unchanged, including suffixes shifted by insertions/deletions. Edited bytes stay
plain until fresh highlighting arrives. If history is unavailable, rendering
falls back to plain text rather than using unrelated offsets. Structural syntax
operations still require the parser's current revision; provisional display
colors never authorize syntax selections or text objects.

Parser completion wakes schedule a full service pass before idle, so finished
colors appear without another keypress. GUI highlighting colors the existing
shaped glyphs once, preserving contextual shaping and avoiding normal-text
overdraw. Highlight queries complete on the worker thread with cooperative
yielding and cancellation; capture counts and elapsed time do not silently
publish a partially colored document as finished.


Nothing downloads on startup. `:languages` opens a searchable package manager in
both the GUI and TUI. Rows distinguish **grammar** packages from language
**servers**, grouped into **Installed** and **Available** sections. Use arrows or
`j`/`k` to select a package, `i` to install an available package, and `x` to uninstall
an installed package. **gg / Home** jumps to the first visible package;
**G / End** jumps to the last. These jumps also extend an active visual range;
**Shift+Home/End** starts and extends a range. Press **v** on a package to start visual selection; arrows
or `j`/`k` extend or shrink the highlighted range. **Shift+Up/Down** can also start
and extend a range. **v** or **Escape** finishes the range and keeps its marks;
`i`/`x`/`u` can act on it directly. Section headings are skipped when marking.
Starting visual mode replaces earlier marks with a fresh range; moving back
unselects packages outside it. The `>` marker identifies the focused row.
**Space** marks or unmarks individual packages; **q** clears all marks and exits visual selection without closing the menu (**c** also works).
When anything is marked, `i`, `x`, and `u` act only on eligible marked packages,
including marks hidden by filtering. Marks survive filtering, refreshing, and
reopening the menu. Successful operations clear their marks; failed operations
keep them for retry. Without marks, `i`/`x` act on the focused package and `u` updates all
installed grammars and managed servers, including packages hidden by the current filter. Updates use this DNA build's
pinned catalogue versions, not unverified upstream releases. `r` refreshes status.
Press `/` to filter; Enter or Escape finishes filtering and returns to package
commands. Escape again closes the manager. Enter on a package uses the same
install action as `i`. The editor stays usable while work runs; reopening
`:languages` shows progress. Failures stay in the menu with an option to view details; other
packages in a bulk update still run.
Incomplete packages remain available to install. The bundled
catalogue contains 55 languages: **Dyn, C, C++, C#, Python, JavaScript/JSX,
TypeScript, TSX, Rust, Go, Zig, Odin, Java, Kotlin, Scala, Dart,
Ruby, PHP, Lua, Haskell, OCaml, Elixir, Erlang, Gleam, Elm, Clojure,
Julia, R, GDScript, GLSL, Bash, Fish, Nushell, CSS, SCSS, HTML, XML, Svelte, Vue,
Markdown, Typst, JSON, TOML, YAML, INI, KDL, HCL/Terraform, Nix, Dockerfile, Make,
CMake, just, Protocol Buffers, GraphQL, and diff**. Package names use lowercase
identifiers (`cpp` for C++, `c_sharp` for C#, `javascript` for JavaScript/JSX,
`nu` for Nushell, `hcl` for HCL and Terraform). Swift, SQL, Perl and LaTeX are
missing because their grammar repositories do not commit a generated parser. These are syntax-highlighting
packages; language servers are listed under Language servers. `:language-install NAME` explicitly
downloads and builds a pinned grammar (for example, `:language-install json`).
Listings and installation progress/errors remain visible after the command finishes,
in navigation mode: Esc or `q` hides the popup; `:bd` closes its buffer. Then use
`:language-reload` to attach installed grammars to open files. The manager reloads
grammars automatically after successful changes.

Grammars live under `$XDG_CONFIG_HOME/dna/languages` (default
`~/.config/dna/languages`), overridable with `DNA_LANGUAGE_DIR`. Managed servers
live under its `.servers` directory. These paths follow DNA's config-directory
convention on the currently supported Linux build and survive mise upgrades.
Existing packages in the previous `~/.local/share/dna/languages` location are
left untouched: reinstall them through the menu to use the new location, or set
`DNA_LANGUAGE_DIR` to the old directory to keep using them. Uninstall removes the
active managed package; older versions retained by updates remain on disk.
The installer
checks the pinned archive SHA-256, compiles locally, validates the grammar ABI and
highlight query, and activates a complete version atomically. Installation uses the compiled Dyn helper plus `curl`, GNU `tar`,
`sha256sum`, `timeout`, and a C compiler; it runs outside the UI loop. No admin access or runtime Python is needed. Python scripts remain development
build/test tooling. The installer is built from [installer/main.dyn](installer/main.dyn).

Tree-sitter parsing and queries run on workers, using document snapshots and
revision checks; stale results are never painted onto newer text. Uninstalled
languages stay plain text. Parsing has a work deadline and updates the retained
syntax tree incrementally; hidden buffers defer parsing until displayed.
Language packages associate extensions, or exact file names such as
`Dockerfile`, `Makefile`, `CMakeLists.txt` and `justfile`, with a grammar, highlight
query, and default indent width. Set a buffer's language with `:filetype python` (aliases `:ft` and
`:set-language`). This works for unnamed buffers, updates highlighting and language
indent width, and survives saving under another extension. It applies to all views
of that buffer; other buffers keep their own settings. `:filetype text` disables
highlighting, `:filetype auto` restores extension detection, and `:filetype` shows
the current selection. An unavailable grammar is reported with its install command;
the choice is retained for `:language-reload`. Overrides last for the current session.
The status line displays the filetype.

The checked-in catalogue is [languages/registry.toml](languages/registry.toml).

Custom entries in `~/.config/dna/languages.toml` use the same fields as
[languages/registry.toml](languages/registry.toml): language name, HTTPS archive
URL, SHA-256, source subdirectory, query path, extensions, optional `filenames`,
and indent width. `highlights` selects a query from the grammar's subdirectory,
`highlights_root` one from the archive root (for repositories that keep queries
above the grammar), and `bundled_highlights` one of DNA's maintained files in
[languages/queries](languages/queries). Use exactly one. Queries may use the
standard predicates `#eq?`, `#match?`, `#any-of?`, `#contains?` (with `not-` and
`any-` forms) and Neovim's `#lua-match?`; directives such as `#set!` are ignored,
and a pattern with any other predicate is disabled on its own. Semantic tokens and
injected languages (code inside Markdown, scripts inside Svelte/Vue) are not
implemented.
Custom archives must have one top-level source directory; symlinks, hardlinks,
and special archive entries are rejected before extraction. Only install native
grammars you trust. The loader supports C scanners; C++ scanners fail
validation. Language servers are configured separately
from grammars (see below). Server installation, injected languages, and
syntax-aware text objects remain follow-up work.

## Keys

These are provisional, Helix-inspired controls, not full Helix or Vim compatibility.
Selection highlighting uses continuous row bands. Newlines within a larger selection
extend the band to the view edge, including blank lines; a lone selected newline
uses one cursor cell. Escape from insert mode stays on the current line, including
a new empty line created with `o`, `O`, or Enter. Selections span the bytes between anchor and cursor; `v` extends the selection
with movement, including the starting character. Escape leaves select mode while
keeping the selected range. The normal-mode block cursor stays on the last selected
character, so `x` never highlights the first character of the following line. Word motions retain the hovered character when starting from a single-character selection; counted motions retain their initial anchor for every cursor. Word motions select the traversed range; `c` replaces it in one undo group.
`i` inserts before a selection and `a` appends after it.

| Action | Keys |
| --- | --- |
| Insert / append after cursor / new line below | `i` / `a` / `o` |
| Insert at first nonblank / append at line end | `I` / `A`; applies to every cursor |
| Line start / first nonblank / last character | `gh` / `gs` / `gl`; Home / End also work |
| Leave insert/select mode; dismiss popup | Escape |
| Close highlighted buffer in the buffer picker | Ctrl+X; S saves, D discards, C/Escape cancels and preserves the buffer, filter, and selected row |
| Close active buffer outside the picker | Ctrl+X (normal or insert mode), with the same unsaved-change prompt |
| Move | Arrows; normal-mode `h j k l` |
| Additional cursor below / above | `C` / `Alt C` (up to 32; counts such as `3C` work) |
| Keep primary / remove primary cursor | `,` / `Alt ,` |
| Extend selection | Shift + arrows; normal-mode `v`, then movement |
| Word forward/backward/end | `w` / `b` / `e`; uppercase treats punctuation as part of a word |
| Repeat motion / select several lines | e.g. `3w`, `5j`, `3x` (counts up to 999) |
| Collapse selection / swap selection ends | `;` / `Alt ;` |
| Select line below / extend selection upward by a line | `x` / `X` |
| Shrink selection to the whole lines it covers | `Alt x` |
| Align selections to one column | `&` |
| Search for the selection (then `n` / `N`) | `*` |
| View: center / top / bottom / scroll a line | `z` then `z`/`c`, `t`, `b`, `k`/`j`; `Z` keeps the menu open |
| Next / previous diagnostic, first/last diagnostic, paragraph, add blank line | `]` / `[` then `d`, `D`, `p`, Space |
| Toggle line comments | `:comment` (Helix's `Ctrl C` / `Space c` keep DNA's copy / close buffer) |
| Keymap profile | `:keymap helix` or `:keymap vim`; `[modules] keymap` sets the default |
| Character find / till (reverse with Shift) | `f` / `t`, then a character; Escape cancels |
| Replace selected characters / replace with clipboard | `r`, then a character / `R` |
| Indent / unindent; join lines | `>` / `<`; `J` |
| Toggle / lower / upper ASCII case; trim selection | `~` / backtick / Alt-backtick; `_` |
| Select line / select all | `x` (repeat to extend) / `%` or `Ctrl A` |
| Insert at line start/end; new line above | `I` / `A` / `O` |
| Mouse selection | Click/drag; Shift-click extends; double-click word; triple-click line |
| Move by word with arrows | Ctrl + Left/Right; add Shift to extend |
| Line start/end; document start/end | Home/End; normal-mode `g g`/`Shift G` |
| Page / half-page movement | `Ctrl B` / `Ctrl F`; `Ctrl U` / `Ctrl D` |
| Move 20 lines up/down | Page Up/Page Down |
| Delete / change selection (or next character) | `d` / `c` |
| Undo / redo | `u` / `Shift U`; `Ctrl Z` / `Ctrl Shift Z` or `Ctrl Y` |
| Copy / paste after / paste before | `y` / `p` / `P`; `Ctrl C` copies and `Ctrl V` replaces |
| Search forward / backward; next/previous match | `/` / `?`; `n` / `Shift N` |
| Command palette | `:` or F1 in normal mode; `Ctrl P` |
| Shortcut guide | Space |
| Window menu | `Space w` or `Ctrl W` |
| Vertical / horizontal split of current buffer | `Space w v` / `Space w s`; `:vsplit` / `:hsplit` |
| New empty buffer in a vertical / horizontal split | `:vnew` / `:hnew` (`:new` aliases `:hnew`) |
| Focus window | `Space w h/j/k/l`; `Space w w` cycles; click a pane |
| Close window / keep only current | `Space w c` / `Space w o`; `:wclose` / `:only` |
| Buffer picker / next / previous | `Space b` / `Space n` / `Space p` |
| Go-to menu | `g` (Escape cancels) |
| Close current buffer | `Space c` or `:bd` |
| New empty buffer | `:enew` |
| Open / save | `Space f` / `:write` then Enter |
| Save and close buffer | `:x` / `:wq` |
| Save all / save all and exit | `:wa` / `:xa` |
| Directory buffer | `Space e`; `Ctrl E` |
| Font larger/smaller/reset | `Ctrl +` / `Ctrl -` / `Ctrl 0` |
| Close active buffer and its split | `:q` / `:quit` |
| Close shared buffer | `:bd` (prompts if dirty) |
| Quit whole editor | `:qa` / `:quit-all`, `Ctrl Q`, or close window |

The command palette supports descriptive names and short commands: `open`/`e`,
`write`/`w`, `quit`/`q`, `buffers`/`b`, `bn`, `bp`, `bd`, and `enew`. `:open path`
and `:write path` accept a literal path (including spaces) and expand `~/`.

Every command is in the palette under its name and its short forms, and every
option is too: typing part of an option's name (`scroll`, `keymap`) lists
**Set option** rows with the current value. After a command name, the palette
suggests its arguments as you type: files and folders for `:open`, `:write`,
`:cd` and sessions; themes, layouts, fonts, languages and installed plugins;
`:module` slots and names; `:place` surfaces, modes, anchors and sides; option
names and values for `:set`. **Tab** fills the selected command name or
suggestion (a folder fills and lists its contents). **Enter** fills it and
runs the command, but keeps the palette open after a folder or an option name,
and never replaces a free value you typed (a new file name, a number).

`:set KEY VALUE` changes any option for this session through the same parser
and checks as `config.toml` (`:set line_numbers false`, `:set font_size 18`,
`:set explorer tree`). `:set KEY?` describes an option and `:set KEY&` returns
it to the files' value. Session values apply over the global and project
config, survive config reloads, and respect `lock`; add them to `config.toml`
to keep them. `:theme`, `:keymap`, `:module` and placement changes (`:place` or
the mouse) are session values too, so `:config-reload` or a later `:set` keeps
them.

`:q` closes the focused split when another split shows the same file, preserving
the shared buffer and its unsaved edits. Otherwise it closes the active buffer
(prompting if dirty) and removes its split rather than filling it with another
file. Splits showing other files keep their buffers. `:bd` uses the same active
view behavior; closing a selected buffer in the buffer picker explicitly removes
that buffer and all its views. Use `:wclose` to close only a view in all cases.

Closing the last buffer follows `[files] close_last_buffer`: `"auto"` (the
default) quits in the terminal frontend, where an empty editor has nothing to
show, and keeps an empty buffer in a window; `"quit"` and `"keep"` pick one
behaviour everywhere. Unsaved text and running terminal panes still ask first.
`:quit-all` checks every dirty buffer and staged explorer edit before exiting.
`:x` saves modified text and closes the focused view; another view of the same
file keeps the saved buffer open. With no other view it closes the buffer too.
Clean buffers close directly. `:wa` saves
modified file buffers and restores focus; `:xa` saves them before exiting.
Unnamed modified buffers ask for a destination. Escape or a save/formatter error
stops the sequence and keeps remaining buffers open; earlier successful saves
remain on disk. Terminal buffers are skipped, with normal terminal confirmation
before exiting. Staged explorer changes must be previewed and written separately.

Multiple selections support character/word/line motion, `v`, `i`/`a`, typing,
backspace/delete, `d`/`c`, character find/replace, and clipboard paste. A batch edit
is capacity-checked before any text changes and undoes in one step. Overlapping
ranges merge for editing; each pane retains its own selection set. Multi-selection
clipboard copying joins selections in document order and retains the individual
fragments; pasting an unchanged clipboard into the same number of selections
distributes those fragments. Otherwise text repeats at every cursor.
Indentation, joining, ASCII case conversion, and open-line commands support
multiple selections. Overlapping edit ranges merge and edit once; one undo
restores the original selections. Counts work for indentation and open lines.
`(`/`)` rotate the primary selection in document order; `Alt-(`/`Alt-)` rotate
selected text, including unequal-length UTF-8 fragments. Content rotation rejects
overlapping ranges without mutation. Counts apply to both rotation commands.
Named registers, syntax-aware selections, and macros are not yet implemented.
The implementation queue and remaining compatibility work are tracked in
[IMPLEMENTATION.md](IMPLEMENTATION.md).
Command-key overrides are supported through config. Picker arrows also accept Ctrl-N/J and Ctrl-P/K; Ctrl-U clears a prompt.

Each document retains its text, undo history, cursor, selection, editing mode,
and scroll position when switched away. Opening another file preserves the
current buffer, including unsaved edits; reopening the same resolved path switches
to its existing buffer. Buffer search uses fuzzy path matching and marks the current and modified buffers.
Closing a modified buffer prompts for save/discard/cancel. Quit visits every dirty
buffer, including hidden ones; Escape cancels further closing. Confirmed discards
before cancellation remain discarded. Use `:session-save` and `:session-load` to persist the workspace across launches.

Splits form a nested layout of up to eight windows. Each window has its own cursor,
selection, scroll position, and editing mode. Opening a file or choosing a buffer
changes the focused window. Views of the same buffer share edits and undo history;
retained cursor positions follow insertions, deletions, and undo/redo. Closing a
window leaves its buffer open, including unsaved edits. Closing a buffer updates
all windows showing it. The focused window has an accent along its top edge.
Use `:resize 25` to give the focused side 25% of its parent split, `:equalize`
(or Space w =) to balance splits, and `:layout-save path.toml` to save their shape.

Line numbers are relative except for the current line, which shows its absolute
number. The status line shows mode, filename, modified state, buffer count,
line/column, and selected codepoints. Palette commands independently toggle line
numbers, relative numbering, the status line, and current-line highlighting.

In prompts, type and press Enter; Backspace edits the query. The command palette
is a compact panel near the bottom with up to four visible results. It filters
case-insensitively, prioritizes prefixes, and caches unchanged queries/text layouts;
arrows select a command. Document search accepts case-sensitive regular expressions and wraps. Insert-mode Tab inserts four spaces.

In the `:` command palette, Up/Down recalls the last 32 submitted commands
and restores the current draft when returning to the newest entry. Ctrl-n/p
and Ctrl-j/k continue to select palette suggestions. History lasts for the session.

## Vim keys

`[modules] keymap = "vim"` (or `:keymap vim` for the session) switches normal
mode to Vim's grammar: operator, then motion or text object, with counts on
either (`d3w`, `3dd`, `2d2w`). Insert mode keeps DNA's insert keys plus Vim's
Ctrl-w and Ctrl-u; Escape steps the cursor back one character. Space still
opens DNA's leader menu and `:` the command palette. Pending `g`, `z`, `Z`,
and operator text-object prefixes show guides for the available Vim commands;
keys and clickable guide entries follow the same Vim dispatch.

| Kind | Keys |
| --- | --- |
| Motions | `h j k l`, arrows, `w W b B e E ge gE`, `0 ^ $ g_ |`, `gg G` (`5G`), `H M L`, `{ }`, `%` (and `50%`), `f F t T ; ,`, `n N`, `* #`, `+ - _ Enter` |
| Operators | `d c y > <`, `g~ gu gU`; doubled for lines (`dd cc yy >> << guu`) |
| Text objects | `iw aw iW aW ip ap`, `i( a( ib ab i[ a[ i{ a{ iB aB i< a<`, quotes `i" a" i' a'` and backticks |
| Editing | `x X D C s S Y`, `p P` (lines below/above), `r{c}` (`r` Enter splits), `J`, `~`, `i a I A o O` with counts (`3ihi<Esc>`, `3o`), Ctrl-a / Ctrl-x |
| Undo, repeat | `u`, Ctrl-r, `.` (with a new count: `3.`) |
| Visual | `v V` Ctrl-v; motions and text objects extend; `d x c s y > < ~ u U J r p P o`, `D X Y C S R` for lines, block `I A`, `gv` |
| Registers | `"a`–`"z`, `"_` (black hole); the unnamed register is the system clipboard |
| Macros | `q{a-z}` records, `q` stops, `@{a-z}` and `@@` replay |
| Search | `/` and `?` (PCRE), `n N`, `* #` |
| View | Ctrl-d Ctrl-u Ctrl-f Ctrl-b, Ctrl-e Ctrl-y, `zz zt zb` |
| Language server | `K` hover, `gd gy gr gi` (definition, type, references, implementation) |
| Buffers, files | `gt gT`, `ZZ` (`:x`), `ZQ` (`:qa`), `:w :q :wq :x :wa :qa`, `:e path` |
| Ex | `:42`, `:[range]s/pattern/replacement/[gi]` with ranges `%`, `N,M`, `.`, `'<,'>`; `&` is the match, `\r` a line break |

Ctrl-o / Ctrl-i walk the jump list (recorded by `gg`, `G`, searches and LSP
goto). Not yet: marks (`m`, `` ` ``, `'`), Replace mode (`R`), `gq`, `=`, sentence and tag objects, `.` after a
visual-mode change, `gJ` (joins with spaces like `J`), and capture groups in `:s` (patterns are PCRE, so write `a|b`,
not `a\|b`). Ctrl-x closes the buffer only in the Helix keymap.

## Editable explorer

`Space e` opens an editable directory popup that works like mini.files. It
starts as one column on the current folder, with a preview of the selected
entry beside it. With Helix keys, `l` (or Enter, or Right) on a folder walks into it and keeps
the folder you came from as a column on the left, so the explorer grows as you
go deeper; on a file it opens it. `h` (or Backspace, or Left) walks back out.
When columns no longer fit, the oldest drop off the left. `q` or Escape (in
normal mode) closes it; staged edits stay until applied or discarded. Every
explorer closes the same way, and a cancelled file prompt returns to the
explorer that opened it.

The explorer follows the selected Helix or Vim keymap, with its own editing
state. In Vim mode, Enter opens the selected entry, Backspace or `-` moves to
the parent, and `h/l` move within filenames. Operators, counts, and visual
selections work on the filename buffer;
`ZZ` previews its staged changes. Explorer navigation and file previews remain
explicit.

The column you are in is an editable buffer and shares the document editing
keys: `j/k`, `w/b/e`, motion counts, `i`, `a`, `o`, `v`, `x`, `d`, `c`,
`u`/`Shift U`, and clipboard commands.
Apply or discard pending edits before navigating to another directory.

The editable area contains filenames only. The gutter uses the same numbering as
file buffers: the current line is absolute, other lines relative. It follows the
same line-number settings. File identities stay internal and follow edits and
undo/redo; copying a row copies only its filename.

Edit a filename to stage a rename. Add a filename on a new line to stage an empty
file. Delete an entire existing row (`x`, then `d`) to stage a move to `.dna-trash`.
New directory rows end in `/`. Existing directory names cannot be edited;
folder renaming is not supported yet. Deleting a directory row stages a move of
the entire folder and its contents to `.dna-trash`, just like file deletion. Control characters in names are unsupported.
Joining two existing rows is ambiguous and blocks applying until undone.

For example, changing:

```text
notes.txt
old.txt
```

to:

```text
journal.txt
new.txt
```

stages a rename, a new file, and a move of `old.txt` to trash. **Nothing on disk
changes while you type.** Escape leaves insert/select mode; another Escape hides
the explorer while keeping its draft and undo history.

Add a new line ending in `/`, such as `assets/`, to stage a new folder.
Names are relative to the current directory; nested paths are not supported.
The preview labels folder creation separately from file creation.

Inside the explorer, `:write` shows the complete operation count and a scrollable
preview. Enter applies; Escape returns to editing without applying. `:undo`,
`:redo`, `:refresh`, `:discard`, and `:quit` are explorer commands; `:quit` hides the
popup and retains its draft. The palette also exposes **Write explorer changes**,
**Discard explorer edits**, and **Refresh explorer** outside this context. Discard
requires confirmation; application quit checks pending explorer edits as well.

Apply rechecks source identity, directory identity, existing destinations, and
unsaved affected file buffers. Renames update open-buffer paths. Existing targets
and trash collisions are refused; swaps/cycles and overwriting destinations must
be split into separate operations. Deleted files can be restored manually from
`.dna-trash`. File operations are not text undo and a batch is not atomic: on a
partial failure, DNA reports how many operations completed, keeps the draft for
reference, and requires discard/refresh before another attempt. The filesystem
is not locked against concurrent changes. Explorer drafts live only in memory
and do not yet have crash recovery.

The older individual create/rename/trash commands remain in the palette and
refuse to run while a directory draft is pending.

## Layout files

Use **Load layout file** in the palette, or the built-in compact/wide commands.
Examples are in `layouts/`. The current layout implementation controls popup
size, font size, document chrome, and relative split trees. Arbitrary buffer roles remain future work.
The command palette uses content-sized height. File/buffer pickers use 90% of
the window width and 88% of its available height, with a preview pane on wide
windows and a full-width results list on narrower ones. These pickers, key menus,
and the editable explorer have their own sizing rather than the generic popup
fractions. File previews read only the first 256 KiB of a file; buffer
previews include unsaved edits. Preview work is cached by selection.

`Space` and `g` open bordered key-hint menus at the lower right. Normal-mode
`Space` works in both file buffers and the explorer. `Space o` is deliberately
unbound and leaves the menu open; Escape returns to the originating buffer.
`Space g` opens the go-to menu.

```ini
popup_width = 0.64
popup_height = 0.56
font_size = 20
line_numbers = 1
relative_numbers = 1
status_line = 1
highlight_line = 1
reduced_motion = 0
```

Popup dimensions are fractions of the window, between 0.25 and 1.0. Font size
is 12–36. Chrome switches use 0/1 and default to enabled.

Cursor movement eases over 70 ms, scrolling over 110 ms, and popups fade in/out
over 90 ms. Editing and popup input are immediate. New movement interrupts the
current transition; large jumps start near the destination. DNA schedules frames
only while transitions are active and returns to its idle wait afterward.

Set `reduced_motion=1` in a layout to turn all transitions off. To start without
animations, use `DNA_REDUCED_MOTION=1 dyn run src`. Loading a layout applies its
own reduced-motion setting (default `0`).
`layouts/minimal.dna-layout` hides the gutter, status line, and line highlight. Blank lines and whole-line `#` comments are accepted. Duplicate/unknown
keys and invalid values are rejected before anything changes. Popups expand when
needed for readable content, capped by the window. Switching layouts preserves
text, selections, and undo history. Use `:layout-save path.toml` to persist the current split arrangement and chrome settings.

## Saving and recovery

Saving writes a sibling temporary file, flushes it, then renames it over the
original. Existing file permission bits are preserved. A content check refuses
to overwrite a file changed externally; Save As only creates new destinations.
Opening another file or creating a new buffer retains unsaved edits in its original
buffer. Close and quit offer save/discard/cancel. The palette also provides an explicit discard
confirmation. Symlink files are refused; open their targets explicitly.

Changed named and unnamed buffers share one background session recovery writer.
Every 500 ms, changed workspace state is copied into a bounded queue;
file creation, writes, and flushes run on the worker. The original files are never
autosaved. Use `:recoveries` after a crash, restore the session, then save normally.
Legacy `<filename>.dna-recovery` files can still be restored when opening a file;
new sessions no longer create these duplicate sidecars. Save failures leave the
in-memory document available.

This is still a prototype: content checking is not a filesystem lock, and saving
replaces the inode (hard links, ownership, ACLs, and extended attributes are not
preserved). Rename durability across power loss is not guaranteed. Recovery is
not a replacement for backups or version control.

## Current limits

- Open-document storage grows with available memory; there is no fixed buffer-count limit.
  Each document supports up to **268,435,455 UTF-8 bytes**; NUL/binary files are
  refused. Unused text, line-index, and undo pages are not eagerly touched.
- Up to 64 undo states within a 4 MiB changed-byte budget per document; large replacements retain
  fewer states. Insert runs group until movement/mode changes.
- Movement/deletion follows Unicode grapheme clusters, including combining marks,
  emoji ZWJ sequences, and flags. IME preedit UI and comprehensive bidirectional
  text still need work. Tabs and wide glyphs render correctly; vertical movement
  currently follows grapheme columns rather than visual tab stops. Vertical
  movement remembers the desired column across shorter lines, including in
  selection mode. Horizontal movement and text edits reset that preference.
- Keyboard and mouse selection with cursor-following scrolling; no wheel scrolling yet.
- Word classes distinguish whitespace, identifier text, and punctuation. Non-ASCII
  categories distinguish letters/marks/numbers from separators and punctuation;
  full linguistic Unicode word segmentation is not implemented.
- Directory listings and staged batches support at most 256 entries/operations.
  Explorer listings remain limited to 65,535 bytes and allocates its own undo arena.
- Tree-sitter highlighting, LSP, command-key overrides and a Vim keymap profile
  are available (see Vim keys for its gaps). A TUI and SSH remain unimplemented. An experimental process-based plugin
  API and persistent sessions are available.
- Linux remains the primary platform. Native macOS builds run in CI. Windows
  adapters and build tooling are implemented, with native qualification in progress;
  Windows ARM64 currently has compile checks only.

## Project tools, sessions, and extensions

- **Global search:** `Space /` or `:search-global <regex>`. Type to restart the
  background search; arrows/Page Up/Page Down choose a result, Enter opens its
  file and selects the match. Searches saved files under `:pwd`, with Unicode
  regex and multiline anchors. Locations use byte columns. Hidden entries,
  `build`, `target`, and `node_modules` are skipped; symlinks are not followed.
  Limits: 1,024 results, 20,000 entries, 16 levels, five seconds, and the editable
  file-size limit. Partial/invalid results are labelled; this is not gitignore-aware.
  Plain printable ASCII patterns without regex syntax use a cancellable byte-search
  path after the first checked match validates UTF-8. Other patterns use PCRE2.
  File reads and binary scans check cancellation at bounded intervals.
- **Project replacement:** finish a search, Escape, then
  `:replace-preview literal replacement`. The preview lists affected files/counts.
  Enter applies to undoable buffers; Escape cancels. Save each with `:write`.
  Dirty buffers, changed files, partial searches, zero-width matches, and more
  than 16 affected files are rejected. Replacement text is literal, not `$1` expansion.
- **Build/test results:** `:errors` opens a filtered diagnostics picker from the
  latest task terminal. `:error-next` and `:error-prev` navigate `path:line:column`
  output relative to that task's starting directory.
- **Discovery:** `:themes`, `:layouts`, and `:settings` are searchable pickers.
  Custom theme/layout files live beside config.toml in `themes/` and `layouts/`.
  Settings opens the selected key in an existing config; reload with `:config-reload`.
- **Relative layouts:** `tree = "v70(f,h50(f,f))"` means a 70/30 vertical split,
  with the right side split horizontally 50/50. `f` is a view, `v` is vertical,
  `h` is horizontal; ratios are 10–90%. Loading reuses current views in order;
  extra leaves show the active buffer. `tree = "f"` returns to one view.
  Use `:layout path.toml` or `:layouts`, and `:layout-save path.toml`.
- **Sessions:** `:session-save [path]` / `:session-load [path]`; default is
  `config.toml.session` beside your config (its parent must exist). Snapshots
  include text, saved baselines, unnamed buffers, filetypes, project directory,
  split ratios, and primary cursors. Restore refuses dirty buffers and running
  terminals. Terminal panes restore as empty buffers, not running processes.
  Named text comes from the snapshot; save-conflict checks still protect external
  disk changes. Undo history, secondary cursors, explorer staging, and plugins
  are not restored.
- **Crash recovery:** every 500 ms, changed workspace state is queued to
  a background writer under the config directory's `recovery/`. `:recoveries`
  lists snapshots left after a crash; Enter restores one. Each editor instance
  owns a private snapshot and deletes it on clean exit. `DNA_RECOVERY=0` disables
  this facility; `:plugin-log` also reports background recovery failures.
  Up to five seconds of recent work can be absent after a crash.
- **Plugins:** see [PLUGINS.md](PLUGINS.md) for the separate-process protocol,
  local install/update commands, permission review, and the working Dyn example.

Terminal normal mode supports single-line j/k, Page Up/Down or Ctrl-B/F,
Ctrl-U/D half pages, gg/Home for oldest output, G/End for newest, and i to resume
input. Mouse-reporting terminal apps receive clicks/drags in input mode; hold
Shift for local text selection. Clicking another pane changes focus.

## Local Linux preview package

```sh
just smoke
just package
# Extract build/packages/dna-preview-linux-x86_64.tar.gz anywhere, then:
./dna-preview-linux-x86_64/dna [file]
```

The archive includes the editor, native adapter, language installer, linked
non-glibc libraries, theme/layout examples, dependency metadata, licenses, and
checksums. No Dyn SDK or Python is needed to run it. Add the extracted directory
to PATH for the `dna` launcher; keep its bin/lib/share directories together.
The launcher supplies its own library search path. A system monospace font,
compatible glibc, display backend, and graphics drivers are still required.
`build-info.json` records the build inputs; the archive envelope is deterministic
for identical input binaries. Fully reproducible compiler/system builds and
cross-distribution compatibility are not claimed. Packaging does not upload,
tag, or publish anything. Platform ports remain separate work.

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
[IMPLEMENTATION.md](IMPLEMENTATION.md#local-editor-comparison-2026-10-04), including
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

## Go-to menu

In normal mode, `g` opens a compact menu without moving the cursor:

- `g g`: file start; `g e`: file end (`G` still works). `3gg` or `3G` goes to line 3.
- `g s`: first non-whitespace character on the current line.
- `g h` / `g l`: current line start/end.
- `g t` / `g c` / `g b`: top, center, or bottom of the visible screen.
- `g a`: last active buffer; `g f`: open the file path under the cursor or in the selection.
- `g n` / `g p`: next/previous buffer.
- `g d` / `g r` / `g y` / `g i`: definition, references, type definition, implementation.

Pickers are on `Space f` (files) and `Space b` (buffers).

The same menu works in the editable explorer; line/file jumps operate on its
draft. Escape returns to the originating buffer. `:goto` also opens the menu.

## Select matches within a selection

Select a region with `v` and movement, `x` for lines, or `%` for the whole file.
Press `s`, type a regular expression, and press Enter. Each match **inside the
original selection** becomes a separate selection/cursor. For example, `%`, `s`,
`name`, Enter, `c`, then `value` replaces every `name` in the document together.
With a smaller region selected, matches outside it remain untouched.

The bottom prompt previews matches while typing. Escape restores the original
selections and scroll position. Invalid patterns, no matches, and more than 32
resulting selections leave the original selections intact; edit the pattern or
cancel. `S` splits the selected region around matches (for example `\s+` splits
on whitespace). Both commands work across existing selections and explorer drafts.
`/` and `?` search the document; in visual mode they extend from the existing
anchor. `n` / `N` repeat forward/backward. These differ from `s`, which creates
separate selections within the region. Regex syntax comes from PCRE2 with UTF-8
and Unicode character classes enabled. Work/depth/memory limits stop overly
expensive expressions; byte-level `\C` is disabled to protect UTF-8 boundaries.

## Match menu and text objects

Press `m` in normal or select mode for the key guide. `mi` and `ma` open a second
guide listing the available objects. These commands also work in the explorer.

| Keys | Action |
| --- | --- |
| `miw` / `maw` | Select inside / around a word |
| `miW` / `maW` | Select a WORD (includes punctuation) |
| `mip` / `map` | Select inside / around a paragraph |
| `mi(` / `ma(` | Select inside / around parentheses |
| `mi[` / `ma[`; `mi{` / `ma{` | Brackets and braces |
| `mi"` / `ma"`; single quote or backtick | Quoted text |
| `mim` / `mam` | Nearest enclosing bracket or quote pair |
| `mm` | Move to the matching bracket; extend in select mode |
| `ms(` | Surround each selection with parentheses |
| `mr([` | Replace surrounding parentheses with brackets |
| `md(` | Remove surrounding parentheses |

Closing bracket keys are accepted too. Counts such as `2mi(`, `2mr([`, and `2md(`
address outer pairs; word/paragraph objects also accept counts. Surround changes
apply to multiple selections in one undo group. Escape cancels any unfinished
sequence, including after the old delimiter in `mr`. If any selection lacks its
requested pair, the whole operation leaves text and selections unchanged.

Pair matching is lexical: it handles nested brackets and escaped quotes. For
recognized file types it skips the language's line comments and C-style block
comments where supported, including nested block comments for Rust, Swift, and
Kotlin. Plain text and explorer buffers do not guess comment syntax. Raw strings,
interpolation, and language-specific block comments outside these forms are not
parsed. Angle brackets
are supported explicitly (`mi<`, etc.) but excluded from automatic nearest-pair
matching so comparison operators do not interfere with parentheses. Surround
characters are single printable ASCII characters. Nesting is bounded at 256 pairs.
Crossing surround ranges and edits exceeding document capacity are rejected.
Function/type/argument/comment/test objects need syntax-tree support and currently
show an explicit unavailable message rather than guessing a selection.

Performance notes: document line indexes let viewport and gutter lookup skip preceding text.
Each split retains its viewport layout; cursor-only redraws reuse caret-line shaping.
Recovery snapshots allocate only their encoded size and cursor-only movement does not
reserialize buffer contents. Undo stores changed-byte deltas within 64 states / 4 MiB, reusing discarded redo storage;
checkpointing an unchanged revision skips text comparison, and bulk copies/moves use libc.
Terminal/plugin readiness and syntax/search completion wake the native event loop instead of polling at 60 Hz.
A 500 ms fallback handles maintenance and notification failure; animation frames run only while active.

Terminal normal mode uses a stable, read-only snapshot of retained scrollback and the current screen. `h/j/k/l`, `w/b/e`,
`v`, `x`, line boundaries, and `y` use editor movement/selection rules. PageUp/PageDown
browse scrollback; `gg`/`ge` jump to oldest/latest output; `gh`/`gl`/`gs` move within a line.
`i` resumes the live terminal. The themed cursor uses the editor's smooth movement,
with a bar in input mode and a block in normal mode; reduced-motion settings apply.

Rendering caches are owned by each pane: viewport text, caret-line geometry, and
up to 128 syntax spans. Unchanged redraws reuse shaping; long-line rendering
submits only glyphs intersecting the viewport. Selection character counts are
cached until the selection or document changes. Terminal input/normal mode is
independent for each terminal. Review keeps up to 2,000 history rows within the
256 KiB review-text limit, dropping oldest rows when necessary.

`just bench-buffer` measures beginning/middle/end edits near the current file
size limit. `just smoke` includes long-line rendering, interrupted saves, recovery
failure/retry, terminal scrollback, and repeated worker lifecycle checks.

## Language servers

Opening a saved `.dyn` file automatically starts `dyn lsp` from PATH. The compiler
includes this server; no separate package or syntax grammar is required. Set
`auto_start = false` in `[languages.dyn]` to disable this. `:server-start dyn`
starts it manually; `:lsp-log` shows startup failures. An explicit `server`
override retains the normal opt-in `auto_start` setting.

Other languages start a default server when its program is on PATH and you have
not configured one: rust-analyzer, gopls, zls, ols, clangd (C/C++), pyright,
typescript-language-server (JavaScript, TypeScript, TSX), lua-language-server,
jdtls, kotlin-language-server, csharp-ls, haskell-language-server, ocamllsp,
elixir-ls, erlang_ls, `gleam lsp`, elm-language-server, clojure-lsp, ruby-lsp,
intelephense, metals, `dart language-server`, nil, bash-language-server,
fish-lsp, `nu --lsp`, yaml/json/html/css language servers, marksman, taplo,
docker-langserver, cmake-language-server, tinymist, terraform-ls, svelteserver,
vue-language-server, glsl_analyzer and lemminx. Nothing installs on its own.
A configured `server`, or `auto_start = false`, in `[languages.NAME]` takes
precedence; `[lsp] default_servers = false` turns all defaults off.

To start a server explicitly instead:

```text
:filetype dyn
:lsp-start dyn dyn lsp
```

The filetype override is useful when no grammar is installed. Syntax packages and
language servers are independent. Copy [lsp.example.json](lsp.example.json) beside
config.toml as `lsp.json`, remove servers you do not use, and run `:lsp-config` to
start configured servers. Values are shell commands you trust; the project
folder is their working directory. Other servers do not start merely by opening a project unless you configure `auto_start = true`.

| Feature | Shortcut / command |
| --- | --- |
| Completion | Ctrl-Space / `:complete` |
| Hover | Space-k / `:hover` |
| Definition / references | `gd` / `gr`, or `:definition` / `:references` |
| Rename | `:rename-symbol new_name` |
| Code actions | `:code-actions` |
| Diagnostics | Underlined ranges; mouse hover or `Space-k` shows the error; `:diagnostics` lists all |
| Server lifecycle | `:lsp-restart`, `:lsp-stop`, `:lsp-log` |

Errors are underlined in red and warnings in amber. Hover the marked text for 350 ms to read its message without opening a popup buffer; `Space-k`/`:hover` shows the diagnostic at the cursor and otherwise requests symbol information. The current line's message also appears in the status line. Decorations disappear immediately when their document revision becomes stale. Themes can override `diagnostic_error` and `diagnostic_warning`.

Results use arrows and Enter; Escape cancels. LSP snippets support numbered placeholders, nested defaults, linked fields, and a final cursor position. Tab moves forward, Shift-Tab moves backward, and Escape leaves snippet mode. Variables, choices, transforms, and unsupported or oversized syntax are rejected without changing the buffer. Rename, additional completion edits,
and code-action edits show a preview. Enter changes buffers without saving them;
`u` undoes each buffer's edit. Applying edits preserves selections and split-view
positions by line and column, clamped to grapheme boundaries; it does not track
semantic token identity when a formatter rearranges text. Stale versions,
overlapping edits, invalid UTF-16
positions, and changed files are rejected before text mutation. Code-action
resolution and explicit server commands are supported; command-requested edits
still require preview approval. Ordinary server commands may have their own
side effects outside the editor.

The client uses bounded asynchronous stdio JSON-RPC, UTF-16 positions, full or
full-range incremental synchronization, negotiated save notifications, and
request deadlines. Limits: 8 servers, 128 results/diagnostics, 16 edited files,
8 MiB transport messages. Snippets, semantic tokens, dynamic registration,
resource create/rename/delete edits, and remote document URIs are not supported.
The protocol reference is the [LSP 3.17 specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/).

## External changes and clipboard

A background worker checks open files every 250 ms. Clean buffers reload changed
text; dirty buffers retain local edits and show a disk-change indicator. `:reload`
opens a conflict prompt: R discards local edits and reloads, S offers Save As,
and K/Escape keeps the buffer. Deleted, unreadable, oversized, and invalid files
never replace buffer contents. Existing save-conflict checks remain active.

Yanking multiple selections records individual fragments. When the unchanged
clipboard is pasted into the same number of selections, each gets its matching
fragment in document order. Otherwise the clipboard text repeats at each cursor.
Overlapping fragment destinations are rejected without partial edits.

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

## Explorer columns and icons

The editable explorer uses a mini.files-inspired parent/current/preview layout on
wide windows. Its default frame matches the full picker and stays fixed while
folders open and close. Columns share the available width; the oldest ancestor
columns disappear first, and narrow windows hide the preview when it cannot fit.
Folders sort before files, then names sort by UTF-8 byte order. Enter opens the
selected entry; Backspace goes to the parent and reselects the directory you came
from. `h`/`l` retain Helix filename movement.

File and folder icons are drawn natively in a separate gutter, with file-type
colors from the theme. GUI icons work with ordinary fonts; TUI icons use Nerd
Font file/folder glyphs. Ghostty includes these symbols; other terminals may
need a Nerd Font selected in their settings. Icons
never enter selections, clipboard text, undo history, or staged filenames.
`explorer_icons = false` hides them in both frontends. Folder rows retain their `/`
suffix. The columns you walked through and the preview are read-only context;
only the current column is editable (`explorer_columns = false` hides the
walked-through columns). Navigation still requires applying or discarding staged
changes, and `:write` still opens a preview before touching files.

```toml
explorer_icons = true
explorer_columns = true
explorer_preview = true
```

These options appear in `:settings` and reload with `:config-reload`. File previews
read at most 8 KiB; directory context shows at most 64 entries. Previews are cached
until the selected row, draft, or listing changes. Symlinks and special files do
not get file-content previews. This adds column navigation and decoration, not
mini.files' full cross-directory copy/move or LSP-aware filesystem operations.

File, buffer, font, and settings pickers support single-click selection and double-click activation. Clicks in the preview/header do not activate entries; `[mouse] enabled = false` disables mouse interaction, including terminals.

### Sectioned settings and formatting

`config.example.toml` lists implemented settings with defaults. Existing flat
keys still work; section aliases and flat keys cannot both set the same option.
Unknown keys, duplicates, and out-of-range values reject the whole reload.
`:settings` lists controls; selecting a scalar or common font/theme/task setting shows its default,
configured value, source, and description. View settings also show current overrides. The key-binding sections list custom overrides; language sections show effective values and inheritance. The picker includes configured languages and the active buffer's filetype. Font inspection shows the actual loaded font file, including temporary font-picker changes. Changes reload through filesystem notifications (one-second fallback when unavailable); disable `[files] reload_config`
to use only `:config-reload`. Invalid files preserve the previous settings. Font names use `[editor] font_family`; an explicit
`font` path takes priority. The default font size is 16 with 1.25 line spacing.

Per-language sections such as `[languages.dyn]` can override `indent_width` and
`insert_tabs`, associate comma-separated `extensions` (including the dot), and
set a trusted `server` command with optional `auto_start = true`. Explicit
`:filetype` choices take priority over extension detection. These settings do
not install the server by themselves.

Set a language's `formatter` to a command that reads the document from stdin and
writes the formatted UTF-8 document to stdout. `:format` runs it asynchronously;
`:format-cancel` stops it. `format_on_save = true` waits for successful formatting
before writing. Timeout, invalid output, and stale results leave the file
unsaved. Switching buffers also discards the result. Formatting is undoable and preserves multiple selections. The formatter shares the configured
LSP timeout and the editor's 256 MiB text limit. Save cleanup has separate
`[files] trim_trailing_whitespace` and `final_newline` switches, both off by default. Cleanup preserves selections and split positions by line and column, clamping positions inside removed whitespace. A missing final newline follows the first existing line ending (LF or CRLF), defaulting to LF for single-line files. Formatter results also retain all selections by line and column; they do not track tokens through reordered lines.

DNA is licensed under the [MIT License](LICENSE), copyright 2026 Matthew Dray.
Bundled dependencies retain their own licenses.

### Managed servers and language features

`:languages` manages both grammar and server packages. `:server-install python`
remains available to install pinned Pyright into DNA's language config directory;
`:server-start python` connects it. Managed servers are discovered automatically
for matching buffers, respecting `default_servers` and per-language `auto_start`
settings. Dyn's server ships with the Dyn compiler and is not a separate managed
package. `:server-update python` activates a
new copy of the version pinned in this DNA build's catalog. Prior installations
remain on disk. A failed download/install leaves the active version intact.
Node/npm and `timeout` must be on PATH. npm lifecycle scripts are disabled; these
servers run as your user after you start them. Nothing installs at startup.

The initial managed catalog covers TypeScript, TSX, JavaScript, Python, Bash,
YAML, JSON, HTML, and CSS. Other servers can use `:lsp-start FILETYPE COMMAND` or
per-language `server` settings. Basic extension detection works without installed
grammars. Catalog installation follows the upstream instructions for
[TypeScript](https://github.com/typescript-language-server/typescript-language-server),
[Pyright](https://github.com/microsoft/pyright/blob/main/docs/installation.md), and
[YAML](https://github.com/redhat-developer/yaml-language-server).

`:signature-help` shows the active function signature. `:lsp-format` previews
server formatting edits; Enter applies, Escape cancels. `:diagnostic-next` and
`:diagnostic-prev` wrap through current diagnostics. Language edit previews now
show bounded before/after line hunks and explicitly mark truncation. Completion
suggestions are enabled by default; set `[lsp] automatic_completion = false` to disable them.
Language servers supply snippets using [LSP snippet syntax](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#snippet_syntax).
DNA supports up to 31 explicit tabstops and nesting depth 16; repeated defaults,
mirrors of nested placeholders, variables, choices, and transforms are not yet supported.
Custom snippet files are not yet supported.
For local compiler development, `DNA_DYN_LSP="/path/to/dyn lsp"` overrides the
built-in Dyn server command. An explicit `[languages.dyn] server` takes precedence.

Completion defaults to a 25 ms typing pause; `[lsp] completion_delay_ms` accepts
10–2000 ms. Server-advertised trigger characters request completion immediately,
including Unicode triggers, and include the trigger context in the LSP request.
The configured pause still applies to ordinary typing. Explicit settings retain
their value. Document sync and diagnostic mouse hover default to 50 ms.
Cursor and scroll transitions default to 35 ms; popup transitions use 40 ms.
Panel scrolling and sheet transitions use the configured duration directly.
Language-server computation adds to the request delay.
`:lsp-log` shows the active server command, configured delays, and request-to-response
time. Complete candidate lists filter locally, including backspace, without
repeating server analysis. Requests remain usable while only word characters are
appended at their cursor; other edits still reject stale responses.
If an automatic request takes more than 20 ms, DNA can show matching words from a
bounded region of the current file. These entries say “word from file” and insert
plain text; function signatures and snippets arrive with the server response.
No matches hide the list; backspace can restore cached matches immediately.
The completion menu opens with up to eight rows, sized to the initial result set
and the available space beside the caret. Its width and row capacity can grow
within a completion session, but filtering does not shrink them. The menu anchors
to the word's start and retains its above/below placement while typing. Kind
badges distinguish functions, variables, types and other suggestions; signatures
remain secondary to labels. Same-named overloads have independent clickable rows.
Arrows select, Enter or Tab accepts, and Escape dismisses immediately and returns
to normal mode in either keymap.
Enter also dismisses an empty result popup without inserting text. Dismissal
cancels pending completion refreshes, so late replies cannot reopen it.
Hover, cursor diagnostics, signatures, and completion appear beside the cursor
inside its pane. Hover flips above the cursor near the bottom edge; Up/Down scroll
long hover text and Escape dismisses it.

Sessions now preserve multiple selections in buffers and individual split views.
The reader still accepts older version-1 sessions. IME composition is kept out of
the document until committed and appears as underlined preedit text; the native
candidate window is positioned near the editing area. Complex mixed-direction
text and real desktop IME behavior still need broader manual coverage.

Linux CI is prepared in `.github/workflows/ci.yml`: pinned compiler download,
checks, package verification, and downloadable workflow artifact. CI uses Arch libraries, and
the archive records its glibc requirement. It is not a claim of compatibility
with every Linux distribution.

See [PRERELEASE.md](PRERELEASE.md) for the prerelease audit, package requirements,
and known limitations.

### Build memory limits

`just build`, `just test`, and the compiler invocations in the smoke/package
scripts use `scripts/compile.py`. It serializes compiler invocations, defaults to
one frontend worker, and caps the compiler/linker process tree at 2 GiB with no
swap when a user systemd manager is available. Without systemd it applies an
inherited 2 GiB address-space limit instead. Exceeding the limit fails the build;
it never retries without the limit. `DNA_BUILD_MEMORY_MB` can select 32–4096 MiB.
Direct `dyn build` commands do not use this wrapper.

Settings use ordinary Dyn assignment. Preview 7 lowers large record copies and
literal assignments through memory intrinsics. Older previews could expand
these into enormous LLVM values; keep the build memory guard enabled.

### Registers, macros, and syntax navigation

Use `"a` through `"z` before a yank, delete, or paste to select a named
register. Named text registers are separate from the system clipboard, retain
multiple selection fragments, and allocate exactly what they hold.
The register choice applies to the next yank/paste operation; Escape cancels it.

`Q` starts/stops recording and `q` replays. Prefix either with `"a`–`"z`
to use a named macro. `REC` appears in the status line while recording.
Macros replay the normal input handlers, including UTF-8 insertion and undo.
Each macro holds at most 1024 events, each text event at most 64 bytes; exceeding
a recording limit discards that recording. Counted replay is capped at 10000
events, and recursive replay is disabled. Replay yields after 64 events or
2 ms between events; Escape cancels pending replay. These are session-local macros.

With a grammar installed, `Alt-o` expands to a parent syntax node, `Alt-i`
selects its first named child, and `Alt-p`/`Alt-n` select sibling nodes.
Selections use the current parsed revision; a pending parse never blocks input.
`gy` and `gi` request type definitions and implementations from the language
server. Support depends on the server.

Language packages may also contain `textobjects.scm` with predicate-free
Tree-sitter captures named `function.inside`/`function.around`, `class`,
`parameter`, or `comment` with the same suffixes. `mi`/`ma` followed by
`f`, `t`, `a`, or `c` selects those objects. Captures run on the syntax worker,
with bounded storage and work. Dyn ships a starter query; reinstall the Dyn
syntax package with `:language-install dyn`, then `:language-reload` to get it.
Other language packages need their own queries. Missing or stale results leave
all selections unchanged.

Selection normalization includes `Alt--` (merge all), `Alt-_` (merge touching or
overlapping selections), and `Alt-:` (make selections forward). `_` trims every
selection, retaining its direction.

`K` keeps selections matching a regex; `Alt-K` removes matching selections.
Both preview changes and restore the original selection set on Escape.
Enter also closes an empty or unmatched search without changing selections;
invalid patterns remain open for correction. Project-search dismissal cancels
outstanding worker work; completed results remain available for replacement.
Hover is available through `Space-k` or `:hover`.

### Track redraws

From the DNA checkout, choose a new trace filename and launch normally:

```sh
DNA_RENDER_TRACE=/tmp/dna-frames-1.jsonl dyn run src/
```

Use the editor, then exit normally to flush the final records and summary. Existing
trace files are never overwritten; choose a different filename for each run.
Inspect the result with:

```sh
python3 scripts/render_report.py /tmp/dna-frames-1.jsonl
python3 scripts/render_report.py /tmp/dna-frames-1.jsonl --json
```

Every presented frame records its cause(s), relative timestamp, number of events
since the previous frame, last event kind, draw wall time, pane-render/setup time,
native present time, document/palette text updates, popup type, and animation state.
Causes include input, window events, animation, diagnostic hover, configuration,
syntax, LSP, plugins, disk updates, formatting, search, macros, and terminals.
Direct draws outside the event loop are marked `explicit`. Multiple causes may
share a frame. Counts of document/palette updates cover those caches, not every
native text operation. No file contents, filenames, or typed text are recorded.

Input-bearing frames also record the time from event dequeue to present return,
for both the earliest and latest event coalesced into the frame. The report shows
p50/p95/p99 and worst-case latency and draw time using bounded histograms (bucket
width at most 1.6%). Animation intervals longer than 1.5 known display periods
are counted as late submissions. These measurements exclude OS input queueing,
GPU completion, compositor presentation and physical display scanout; they are
not hardware input-to-photon or exact missed-refresh measurements.

Tracing is off by default. Enabled tracing uses a fixed 16 KiB buffer and caps
output at 64 MiB; after that, frame totals continue and the final summary marks
truncation. Buffered records flush while idle and on normal shutdown. A crash or
forced kill can lose the pending buffer and final summary. Write failures print a
warning. The report reads logs with bounded memory and highlights slow frames.
Timing excludes trace serialization/writes, and `present_us` measures the native
call—not GPU completion or compositor latency. Compare normal runs separately
because tracing itself adds work.

Shutdown records named `shutdown_search`, `shutdown_languages`,
`shutdown_format`, `shutdown_plugins`, `shutdown_recovery`, `shutdown_tree`,
`shutdown_disk`, `shutdown_lsp`, `shutdown_syntax`, and `shutdown_terminals`
identify service cleanup and join delays.

The same trace also records main-thread operation wall/CPU time, whole-process CPU
(including concurrent workers), wakeup reasons and requested deadlines, recovery
copy sizes, UI text-cache hits/updates/creations, and selected arena allocation
sizes/lifetimes. The report ranks operation CPU costs and shows whole-run CPU as a
percentage of one core. Nested operation phases are not additive; process CPU
within a phase can include unrelated worker activity. These measurements include
DNA's workers, but do not attribute CPU to each individual worker thread or to
external language-server/plugin processes.

Arena accounting covers document storage (including bounded undo history), reusable
LSP receive arenas and transferred results, recovery encoding, and UI text storage.
Native tracing also counts syntax-adapter, search-result, terminal, disk-worker,
and Tree-sitter allocations, with live/peak bytes and maximum released lifetime.
Text layouts report object counts because native text/GPU allocation sizes are opaque.
These are requested/reserved sizes, not RSS; native profiling headers, allocator
bookkeeping, other native GUI allocations, plugins, and temporary session-reader arenas
are not included. Native allocation instrumentation is enabled only when
`DNA_RENDER_TRACE` is set at process startup. Large one-off receive/encoding
arenas are released above 2 MiB; smaller ones are reused. Recovery's worker also
reuses completed buffers up to 2 MiB, preserving its private snapshot copy while
writing. The UI cache holds at most 128 text layouts, with fixed byte storage;
font changes clear it. Trace summary counters remain available when detail hits
the size cap, but per-operation detail after truncation is unavailable.

Idle scheduling follows configuration, recovery, hover, completion, animation,
LSP, and plugin deadlines. Worker readiness uses existing notifications; polling
remains a fallback when notification setup fails. Linux file monitoring watches parent directories with inotify, including atomic
replacement. A control pipe wakes registration/shutdown. Unavailable watches use a
250 ms fallback; working watches reconcile every 30 seconds for filesystems that
can miss remote changes. Configuration reload uses the same parent-directory notification approach, with
a 30-second reconciliation and one-second fallback if watching or notifications
are unavailable. Disabling config reload and having no pending work removes the UI's old
fixed 500 ms wakeup.


### Performance and ownership maintenance

Ready input is handled and painted before background maintenance. Maintenance
keeps its ordered service phases, yields to queued input between phases, and
checks a 2 ms cooperative budget. One phase progresses after each input paint
so sustained input cannot starve services; a single phase can exceed the budget
while completing its own transaction. Input event order is preserved.

Disk registrations, filetype resolution, and language-server document updates
use maintained worksets. Buffer observers only mark work after complete edits;
load, save, undo/redo and compound edits participate. Recovery checks compare a
workspace generation instead of scanning every buffer while idle. Visible
syntax work is bounded by pane count, and terminal polling follows terminal
owners rather than all file buffers. Full session capture and native disk audits
after filesystem events still perform the necessary workspace-wide work.

Cursor position and selection highlights update immediately. Optional cursor
trails are decorative; scrolling retargets without moving away from its new
target or overshooting. Popup hit geometry follows its painted frame.
Split and docked explorer edges settle spatially using RAD-style exponential
motion: the new pane grows from its shared boundary while the existing pane
shrinks, and closing expands the surviving pane. Code stays fully opaque;
there is no whole-document fade or background flash. Painted rectangles and
pointer hit targets agree during motion, while keyboard navigation and caret
scroll targets use the final layout. Further input finishes existing geometry
motion immediately. Startup, window resizing, divider dragging, reduced motion,
disabled popup transitions, zero duration and the terminal frontend remain
immediate. The default response is `1 - 2^(-70 * dt_seconds)`; popup duration
scales its speed. Unchanged redraws do not restart motion, and settled panels
stop requesting animation frames.
Pickers, the command palette, floating explorers and key menus share the same
spatial settling response. Their selected row stays visible during opening,
and typing or navigation finishes the opening motion immediately. Floating
explorer columns retain their set while the outer frame settles. Popup opacity
remains a short decoration; other popups dismiss immediately.
The editable explorer opens from its left edge and retracts on dismissal. The
closing layer is decorative: the explorer releases input immediately, and further
input finishes its exit. File text stays stationary when switching buffers.
Parent and directory-preview panes retain the editable listing’s padding, row
height, line-number gutter, directory markers and text contrast. Their headers
identify their parent or preview role; numbering follows the editor settings.
Existing explorer columns stay anchored on the left during folder navigation.
New columns grow on the right; outgoing right columns retract while retaining
a bounded snapshot of their text. Further input finishes the motion immediately.
Page scrolling and cursor-jump decoration continue across unchanged targets;
small navigation steps still land immediately. Presentation pacing uses the
current frame's animation state. When a native display mode is unavailable,
timer-only animation uses a conservative 60 Hz fallback; synchronized animation
continues to follow the display. Input frames retain immediate presentation.
Per-pane caret geometry and unchanged visible line layouts are reused with
font, revision, viewport, identity and journal invalidation checks.

DNA still draws the entire screen whenever a frame is needed. There is no retained
UI tree diff or partial-pane framebuffer. Cached text layouts avoid shaping the
same text again; events and background work determine when a full draw is needed.
The optional native rasterizer clips triangle work to each triangle’s bounding
box, preserving the same edge coverage and alpha blend rules.

UI label lookup uses collision chains with a shared least-recently-used pool;
colliding labels can use free entries rather than evicting each other from a small
fixed bucket. This caches text shaping, not screen regions.

The cache budgets are explicit: 256 UI layouts, 128 syntax-span layouts per pane,
15 pane records and a target of two inactive syntax parsers. Open documents use
a growable directory of stable owners; growth preserves file and asynchronous
request identities. File watching, language-server tracking, recovery, and buffer
picker results grow with that directory. Sessions with more than 16 slots use
format 3; formats 1 and 2 remain readable.
Parser eviction uses one background disposal slot so switching files does not
wait for tree destruction. While that slot is busy, further eviction waits;
parsers remain bounded by the document slots plus one retiring parser. Shutdown
joins disposal before releasing editor state.
Closed panes release their text layouts on the next draw. Evicting an inactive
syntax parser preserves the document and undo history; syntax rebuilds on revisit.
Terminal history retains its existing 2,000-row limit (240 columns). Rows allocate
only their stored width as history grows; resizing preserves older rows and pads
missing columns when read. Terminal review snapshots remain limited by document capacity. Search results remain
limited to 1,024 rows. No automatic eviction discards open text or unsaved edits.
File-picker traversal runs on a cancellable background worker. Directory watches
refresh cached results without losing the selected filename; incomplete watch
coverage uses periodic refresh. Syntax buffers shrink after eight consecutive
small revisions. Undo checkpoints and incremental LSP updates use changed ranges
to avoid repeated full-document scans and copies. Saved and checkpoint baselines
borrow unchanged prefixes and suffixes from current text; only the original bytes
inside the changed range need separate storage. Distant edits can expand that
range. Session/recovery encoding reads the saved baseline as three spans without
materializing another full copy; session bytes and save-conflict checks retain
their existing behavior. Buffer consumers use `saved_parts`/`saved_equal`, or
`saved_text`/`checkpoint_text` when a contiguous baseline is required. Those
borrowed views expire on mutation, save, checkpoint, undo/redo or reload.
Incremental LSP shadows also use sparse small pages, so a small document does
not commit a huge page merely because its maximum capacity is reserved.
Line indexes normally use blocks of 256 two-byte offsets plus a fixed four-byte
base, roughly halving index residency. Long spans and edits exceeding a block's
headroom widen the index to four-byte absolute offsets before changing it; load
and undo rebuilds can compact it again. Ordinary insert/delete updates shift
packed offsets in place. The sparse virtual reservation remains unchanged.
Dirty text equality is cached by document revision and saved-baseline epoch;
explorer row identities are checked independently.
Numeric line jumps read the line index directly. Bulk indentation rewrites the
selected text once and updates line offsets, preserving marks, explorer identities
and undo behavior. Syntax workers transfer owned text and color buffers instead
of copying between worker stages. Document revision ranges bypass full-text diff
scans only when they match the retained parse; missing or stale ranges fall back
to comparison. Published results still require the current document revision.

`src/documents.dyn` owns document allocation/release; `src/lifecycle.dyn` coordinates
subsystem cleanup. Session switching is in `src/session.dyn`. Command metadata in
`src/commands.dyn` supplies palette labels, exact aliases and Space-menu bindings;
argument/context handling remains with its owning subsystem.

Full editor smoke tests now live in `tests/editor/`. `just smoke` stages current
production sources with the test startup adapter and builds separate
`build/dna-smoke-debug` and `build/dna-smoke-release` executables under the same
compiler memory limit. `DYN_EDITOR_SMOKE=1` on the normal binary only validates
startup, one full presentation, and shutdown; it does not run the behavioral suite.

Run `just soak` for repeated native resource lifecycle checks. Syntax lifecycle
checks require the JSON test grammar and verify completed parsing, stale
revisions, and cancellation at teardown. Retained render traces can be inspected
with `scripts/render_report.py`; trace timings end at native present return,
not compositor completion or physical display scanout.
