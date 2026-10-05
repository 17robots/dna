# DNA

A native modal editor prototype written in Dyn. The window shows your document;
line numbers and a slim status line provide orientation. Commands, search, files,
and buffer switching appear as keyboard-invoked popups.
No web runtime. [DESIGN.md](DESIGN.md) records the broader product direction.

## Install the prerelease with mise

The Linux x86-64 preview requires **glibc 2.43 or newer**, a system monospace
font, and desktop display libraries for GUI mode. It does not run on Ubuntu
24.04's glibc 2.39. See [PRERELEASE.md](PRERELEASE.md) before installing.

```sh
mise use -g 'github:17robots/dna[prerelease=true,strip_components=1,bin_path=.]@0.1.0-preview.2'
dna path/to/file.dyn
dna path/to/project
```

Use `mise exec github:17robots/dna@0.1.0-preview.2 -- dna path/to/project`
if mise is not activated in your shell. The explicit `bin_path=.` selects the
archive's launcher, which loads its bundled libraries. The Dyn SDK is needed to
build DNA, but is not required to run this package. Language servers are
installed separately.

This uses [mise's GitHub backend](https://mise.jdx.dev/dev-tools/backends/github.html);
no separate mise plugin or registry entry is required.

## Dyn SDK migration

DNA now targets Dyn 0.1.0-preview.17. Run `mise install`, then `just deps` to
rebuild native adapters and the language installer with the matching runtime.
Existing language installations have independent pins: run
`build/deps/install/bin/dna-language install dyn`, then `:language-reload` in an
open editor. The registry pins the allocator-capable grammar and DNA bundles
its matching highlight query, including `Allocator`, `#allocator`, `#AllocResult`
and all typed allocation forms.

Allocation calls preserve their earlier failure policy: required allocations use
`_or_panic`, and recoverable scratch allocations still check their result. Arena
ownership transfers use `mem.arena_take`; allocator handles are created only
at the destination owner. Sparse document/App storage stays explicitly
uninitialized, with the existing initialization and page-reclamation contracts.
No generic allocator replaces concrete arenas that need reset, rewind or release.

The [SDK migration guide](https://github.com/17robots/dyn/blob/v0.1.0-preview.17/docs/migrations/0.1.0-preview.17.md)
links the preview 16 allocation changes. To roll this migration back, revert its
source, SDK and grammar/query changes together and rebuild the native adapters;
document, session and configuration formats are unchanged.

## Run

Requirements: Linux x86-64, a working Dyn SDK, SDL3 development/runtime libraries,
FreeType, HarfBuzz, PCRE2, utf8proc, libvterm, Tree-sitter (0.25+), and Fontconfig development libraries, CMake, Python 3.12+, a C compiler,
and `just`. Tested with Dyn 0.1.0-preview.17, SDL 3.4.16 and SDL_ttf 3.2.2.
`just build` downloads and builds pinned SDL_ttf into ignored `build/deps`.
The build applies a small fix to avoid repeatedly shaping remaining lines when
wrapping is disabled; its fingerprint also upgrades existing local builds.
All DNA-owned editor code and native adapters are written in Dyn, including
PTY/libvterm integration, Tree-sitter workers, filesystem operations, search,
synchronization and memory accounting. Native test executables and interposers
are also Dyn. External libraries and the Dyn runtime retain their own implementation
languages; this is not a dependency-free build. The C compiler builds external
dependencies and generated header ABI probes, and links Dyn objects.
The helper does not install system packages. After changing native dependencies,
use `dyn build src --release --no-cache` for a direct static rebuild: the pinned
SDK does not invalidate its executable cache when an external archive changes.
`just build` uses the freshly rebuilt shared adapter. Regex selection uses the system PCRE2 library
(`libpcre2-dev` on Debian/Ubuntu, `pcre2-devel` on Fedora, `pcre2` on Arch).

Use the tested **Dyn 0.1.0-preview.17** version pinned in `mise.toml`. For daily development, `just run` uses
cached debug builds and the 2 GiB memory guard. `dyn run src/` also reuses
unchanged modules. Preview 7 fixes cache lookup through PATH and large aggregate
code generation; this editor's full release build now completes in about seven
seconds on the development machine.

To measure compilation plus editor startup through the first rendered frame:
`mise exec -- python3 scripts/compile.py python3 tests/startup_latency.py dyn run src/ --timings`.
This runs three times with SDL's dummy driver and closes each editor normally;
it measures CPU startup, not desktop GPU/display latency.

```sh
just run                 # empty buffer
just run README.md       # open an existing file
```

With mise activated in your shell, direct Dyn commands work too:

```sh
just deps                # once after cloning, builds the local font library
mise trust               # trust this repository's mise.toml
# Let the shell refresh its environment (or leave and re-enter the directory).
dyn run src
```

`mise.toml` supplies the local native-library search paths for both the compiler
and runtime. Without shell activation, use `mise exec -- dyn run src` instead.
The SDL_ttf dependency is declared in the font bindings; no manual `--link` flag
is needed with this environment. `just smoke-direct` checks this direct-run path
without inheriting the library paths from `just`.

Direct `dyn build src` and `dyn run src` link SDL3, SDL_ttf and DNA's native
library statically (through linker scripts in `build/deps/static`), so the
resulting binary starts from any directory, without `LD_LIBRARY_PATH` and without
SDL installed. It still uses the system FreeType, HarfBuzz, Fontconfig, libvterm,
Tree-sitter, PCRE2 and utf8proc. `just build` keeps shared libraries so the test
harness can intercept SDL calls; `just smoke` checks the standalone binary in a
sandbox that hides the build directory and system SDL.

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
keymap = "vim"        # also [editor] vim_keys = true
frontend = "auto"
explorer = "buffer"
picker = "full"
```

`keymap` and `[editor] vim_keys` are the same choice; a file that sets both to
different values is reported as invalid at the second one.
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
(`src/platform/sdl.dyn`, `src/text/ttf.dyn`) is replaced by generated stubs and
the native library is built without SDL or Fontconfig, so the binary links
none of SDL, SDL_ttf or Fontconfig and runs where there is no display or graphics stack (servers,
containers, SSH). It always starts in the terminal.

### Explorer and picker styles

`explorer = "buffer"` (the default) is the editable explorer described under
[Editable explorer](#editable-explorer). `explorer = "tree"` makes Space e
open the project as a collapsible tree, docked on the left (`[place.explorer]`
docks it elsewhere or floats it). A docked tree stays beside the panes after
focus returns to the editor; Space e or a click moves focus back to it.

| Key | Tree action |
| --- | --- |
| `j` `k` / arrows, `g` `G`, PageUp/PageDown, Ctrl+d/u | move |
| Enter | open a file, or fold/unfold a folder |
| `l` / Right | unfold, then step into a folder; open a file |
| `h` / Left | fold, or go to the parent folder |
| `-` / Backspace | make the root's parent the root |
| `.` | make the selected folder the root |
| `r` | reload from disk |
| `e` | edit the selected folder in the editable explorer (create, rename, trash) |
| Esc | back to the editor (a floating tree closes) |
| `q` | close the tree |

The tree opens on the current file, keeps open folders across reloads and
hides `.git`. While it is open it watches its root and every open folder, so
files created, renamed or deleted by anything (a shell, git, the editable
explorer) show up at once. It holds up to 4096 rows.

`picker = "full"` is the large picker with a preview. `compact` sizes file,
buffer and resource pickers like the command palette (query and matches only,
up to 12 rows). `dropdown` does the same but hangs pickers and the command
palette from the top edge of the window. `[place.picker]` and
`[place.palette]` still override where they go.

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

Each surface (`palette`, `picker`, `menu`, `dialog`, `explorer`, `terminal`,
`completion`, `hover`) keeps its usual place unless configured:

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

This is a deliberately restricted TOML reader: flat assignments, decimal numbers,
booleans, quoted strings without escapes, full-line comments, and `[keys.normal]`
/ `[keys.space]` tables. Unknown/duplicate settings and invalid values report a
line number and preserve working settings. Up to 16 key overrides map key names
(single characters, F1–F12, `space`, `backslash`, optionally prefixed with
`ctrl-`, `alt-`, or `shift-`) to palette commands. Normal overrides do not run
while typing, selecting, or entering text into a terminal. This does not add a Vim
editing engine; Helix-inspired editing remains the implemented mode.

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

Nothing downloads on startup. `:languages` opens a report with separate
**Installed languages** and **Available to install** sections, including explicit
empty states. Incomplete packages remain available to install. The bundled
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
`:language-reload` to attach installed grammars to open files.

Grammars live under `$XDG_DATA_HOME/dna/languages` (default
`~/.local/share/dna/languages`), overridable with `DNA_LANGUAGE_DIR`. The installer
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
| Keymap profile | `:keymap helix` or `:keymap vim`; `[editor] vim_keys` sets the default |
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
| Open / save | `Space f` / `:write` then Enter; `Ctrl O` / `Ctrl S` |
| Save and close buffer | `:x` / `:wq` |
| Save all / save all and exit | `:wa` / `:xa` |
| Directory buffer | `Space e`; `Ctrl E` |
| Font larger/smaller/reset | `Ctrl +` / `Ctrl -` / `Ctrl 0` |
| Close active view | `:q` / `:quit` |
| Close shared buffer | `:bd` (prompts if dirty) |
| Quit whole editor | `:qa` / `:quit-all`, `Ctrl Q`, or close window |

The command palette supports descriptive names and short commands: `open`/`e`,
`write`/`w`, `quit`/`q`, `buffers`/`b`, `bn`, `bp`, `bd`, and `enew`. `:open path`
and `:write path` accept a literal path (including spaces) and expand `~/`.

Every command is in the palette under its name and its short forms, and every
option is too: typing part of an option's name (`scroll`, `vim_keys`) lists
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

`:q` closes the focused split when multiple views are open, preserving buffers
and unsaved edits, including the same file in another split. With one view, it
closes the current buffer (prompting if dirty). The final buffer becomes an empty
scratch buffer; `:q` on that final empty scratch view exits the editor.
`:bd` closes the shared buffer across views.
`:quit-all` checks every dirty buffer and staged explorer edit before exiting.
`:x` saves and closes the active buffer, including its other views. `:wa` saves
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

## Vim keys

`[editor] vim_keys = true` (or `:keymap vim` for the session) switches normal
mode to Vim's grammar: operator, then motion or text object, with counts on
either (`d3w`, `3dd`, `2d2w`). Insert mode keeps DNA's insert keys plus Vim's
Ctrl-w and Ctrl-u; Escape steps the cursor back one character. Space still
opens DNA's leader menu and `:` the command palette.

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

Not yet: marks (`m`, `` ` ``, `'`), the jump list (Ctrl-o / Ctrl-i keep DNA's
meaning), Replace mode (`R`), `gq`, `=`, sentence and tag objects, `.` after a
visual-mode change, `gJ` (joins with spaces like `J`), and capture groups in `:s` (patterns are PCRE, so write `a|b`,
not `a\|b`). Ctrl-x closes the buffer only in the Helix keymap.

## Editable explorer

`Space e` opens an editable directory popup. It shares the document editing keys:
`h/j/k/l`, `w/b/e`, motion counts, `i`, `a`, `o`, `v`, `x`, `d`, `c`, `u`/`Shift U`, and clipboard commands.
Enter in normal mode opens the current row; Backspace goes to its parent.
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

- Up to **16 open documents**, each up to **1,048,575 UTF-8 bytes**; NUL/binary files
  are refused. Document storage is bounded; unused text, line-index, and undo pages are not eagerly touched.
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
- File operations currently target Linux x86-64. Windows/macOS are not supported
  by this prototype yet, despite the portable SDL rendering layer.

## Project tools, sessions, and extensions

- **Global search:** `Space /` or `:search-global <regex>`. Type to restart the
  background search; arrows/Page Up/Page Down choose a result, Enter opens its
  file and selects the match. Searches saved files under `:pwd`, with Unicode
  regex and multiline anchors. Locations use byte columns. Hidden entries,
  `build`, `target`, and `node_modules` are skipped; symlinks are not followed.
  Limits: 1,024 results, 20,000 entries, 16 levels, five seconds, and the editable
  file-size limit. Partial/invalid results are labelled; this is not gitignore-aware.
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
LD_LIBRARY_PATH="$PWD/build/deps/install/lib" SDL_VIDEODRIVER=wayland python3 scripts/smoke.py
```

Tests cover UTF-8 edits, selections, bounded undo/redo, search, capacity rollback,
file conflicts, permission preservation, recovery, symlink/FIFO rejection, layout
validation, multi-buffer undo/view restoration, close/quit cancellation, path
completion, staged explorer edits, preview cancellation, external-source/destination
changes, palette caching, and the native open/edit/save/create/rename/trash workflow. Synthetic
SDL input passes through the actual event loop. Font geometry and ABI checks run
against the installed headers. A native input-burst test verifies that all text
arrives without a frame per key/text event or redundant title updates; its timings
are not measurements of human input latency. Physical keyboard and IME testing
remain separate.

The document owns its text, saved/checkpoint baselines, line index, and bounded undo deltas in an arena.
Unused text and undo capacity is reserved without eagerly initializing its pages.
File/prompt/event bytes are copied before their source expires. Temporary file
reads use a rewindable scratch arena. SDL text objects die before their font,
engine, and renderer. Queued events are processed in bounded batches before drawing, and unchanged
window titles are not resubmitted. Idle waits do not redraw. Trailing spaces
and indentation retain their layout width, including in cursor/selection geometry.
The editing, file, and layout modules do not depend on SDL.

Non-colocated jj, local only. No remote or publication. The project name DNA is
provisional; the extension architecture in DESIGN.md is not implemented yet.

## Rendering and latency checks

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

`just smoke` includes a 50 KB fixture with individual typing and movement events.
The test gates on bounded layout work and reports input-to-SDL-present timings,
not physical keyboard-to-display latency. To measure the native Wayland backend
after building debug and release:

```sh
LD_LIBRARY_PATH="$PWD/build/deps/install/lib" SDL_VIDEODRIVER=wayland python3 scripts/latency.py
```

The search/open/edit regression check (`python3 tests/workflow_performance.py`)
opens twelve files twice and bounds resident-memory growth and text submitted
per frame. Total-memory budgets use the dummy backend; both backends check that
reopening the same files reaches a stable memory footprint. Syntax overlays draw only their spans, with pixel checks against a
full-document reference for Unicode, tabs, and glyph bearings. The default uses
fixture highlight spans so no grammar download is needed. Set
`DNA_PERF_REAL_SYNTAX=1` to use the JSON grammar in `build/test-languages`,
`DNA_PERF_MODE=debug` for the debug build, or `SDL_VIDEODRIVER=wayland` for the
real window backend. This check is included in `just smoke`.

`python3 tests/jump_latency.py` replays `gg`/`ge` on `tests/editor/smoke.dyn` in both
build modes. It checks that jumps reach both file boundaries and bounds shaping
input to linear viewport work, while reporting frame timings. Set
`SDL_VIDEODRIVER=wayland` to measure the real window. This is also in `just smoke`.

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
Terminal/plugin readiness and syntax/search completion wake SDL instead of polling at 60 Hz.
A 500 ms fallback handles maintenance and notification failure; animation frames run only while active.

Terminal normal mode uses a stable, read-only snapshot of retained scrollback and the current screen. `h/j/k/l`, `w/b/e`,
`v`, `x`, line boundaries, and `y` use editor movement/selection rules. PageUp/PageDown
browse scrollback; `gg`/`ge` jump to oldest/latest output; `gh`/`gl`/`gs` move within a line.
`i` resumes the live terminal. The themed cursor uses the editor's smooth movement,
with a bar in input mode and a block in normal mode; reduced-motion settings apply.
Run `DNA_PERF_ROUNDS=10 python3 tests/workflow_performance.py` after building for a
120-search/open/edit/undo replay with a resident-memory growth check.

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

Local headless release measurements (not portable timing guarantees): 12 files
with real Tree-sitter highlighting, 120 search/open/edit cycles, about 77 MiB
final RSS and 1.3 MiB growth after warming; input-to-render mean about 4.3 ms.
With split views and a busy terminal, the shorter replay measured about 83 MiB
RSS and 5.2 ms mean. Run these on your machine:

```sh
DNA_PERF_REAL_SYNTAX=1 DNA_PERF_ROUNDS=10 python3 tests/workflow_performance.py
DNA_PERF_REAL_SYNTAX=1 DNA_PERF_COMBINED=1 python3 tests/workflow_performance.py
just bench-buffer
just package
# Optional clean-container check, using an already-present compatible image:
DNA_PACKAGE_IMAGE=archlinux:base python3 tests/package.py
```

The package check compares two archive hashes, verifies extracted checksums, and
can run the extracted editor in a read-only, network-disabled container with
only a font mounted. It does not validate real GPU/display drivers or every
Linux distribution. `build-info.json` records the minimum required glibc symbol
version; `build/packages/container-check.json` records the tested image digest.


## Explorer columns and icons

The editable explorer uses a mini.files-inspired parent/current/preview layout on
wide windows. Short listings use a compact popup height; narrow windows show the
current directory alone. Folders sort before files, then names sort by UTF-8 byte
order. Enter opens the selected entry; Backspace goes to the parent and reselects
the directory you came from. `h`/`l` retain Helix filename movement.

File and folder icons are drawn natively in a separate gutter, with file-type
colors from the theme. GUI icons work with ordinary fonts; TUI icons use Nerd
Font file/folder glyphs. Ghostty includes these symbols; other terminals may
need a Nerd Font selected in their settings. Icons
never enter selections, clipboard text, undo history, or staged filenames.
`explorer_icons = false` hides them in both frontends. Folder rows retain their `/`
suffix. Parent and preview columns are read-only context; the middle column is
the editable buffer. Navigation still requires applying or discarding staged
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

`:languages` includes separate installed/available lists for grammars and language
servers. `:server-install python` installs pinned Pyright into DNA's language data
directory; `:server-start python` connects it. `:server-update python` activates a
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
their value. Document-sync delays,
cursor/scroll/popup animations, and diagnostic mouse hover default to 50 ms. Language-server computation adds to that delay.
`:lsp-log` shows the active server command, configured delays, and request-to-response
time. Complete candidate lists filter locally, including backspace, without
repeating server analysis. Requests remain usable while only word characters are
appended at their cursor; other edits still reject stale responses.
If an automatic request takes more than 20 ms, DNA can show matching words from a
bounded region of the current file. These entries say “word from file” and insert
plain text; function signatures and snippets arrive with the server response.
No matches hide the list; backspace can restore cached matches immediately.
The completion menu reserves eight rows (clipped to the pane), so filtering and
server updates do not change its height. Unused rows remain empty.
Arrows select, Enter or Tab accepts, Escape dismisses.
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
since the previous frame, last SDL event kind, draw wall time, pane-render/setup time,
SDL present time, document/palette text updates, popup type, and animation state.
Causes include input, window events, animation, diagnostic hover, configuration,
syntax, LSP, plugins, disk updates, formatting, search, macros, and terminals.
Direct draws outside the event loop are marked `explicit`. Multiple causes may
share a frame. Counts of document/palette updates cover those caches, not every
SDL_ttf operation. No file contents, filenames, or typed text are recorded.

Tracing is off by default. Enabled tracing uses a fixed 16 KiB buffer and caps
output at 64 MiB; after that, frame totals continue and the final summary marks
truncation. Buffered records flush while idle and on normal shutdown. A crash or
forced kill can lose the pending buffer and final summary. Write failures print a
warning. The report reads logs with bounded memory and highlights slow frames.
Timing excludes trace serialization/writes, and `present_us` measures the SDL
call—not GPU completion or compositor latency. Compare normal runs separately
because tracing itself adds work.

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
Text layouts report object counts because SDL_ttf/GPU allocation sizes are opaque.
These are requested/reserved sizes, not RSS; native profiling headers, allocator
bookkeeping, other SDL allocations, plugins, and temporary session-reader arenas
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

DNA still draws the entire screen whenever a frame is needed. There is no retained
UI tree diff or partial-pane framebuffer. Cached text layouts avoid shaping the
same text again; events and background work determine when a full draw is needed.

UI label lookup uses collision chains with a shared least-recently-used pool;
colliding labels can use free entries rather than evicting each other from a small
fixed bucket. This caches text shaping, not screen regions.

The cache budgets are explicit: 128 UI layouts, 128 syntax-span layouts per pane,
15 pane records, a target of two inactive syntax parsers, and 16 open documents.
Parser eviction uses one background disposal slot so switching files does not
wait for tree destruction. While that slot is busy, further eviction waits;
parsers remain bounded by the document slots plus one retiring parser. Shutdown
joins disposal before releasing editor state.
Closed panes release their text layouts on the next draw. Evicting an inactive
syntax parser preserves the document and undo history; syntax rebuilds on revisit.
Terminal history retains its existing 2,000-row limit (240 columns), and terminal
review snapshots remain limited by document capacity. Search results remain
limited to 1,024 rows. No automatic eviction discards open text or unsaved edits.
File-picker traversal runs on a cancellable background worker. Directory watches
refresh cached results without losing the selected filename; incomplete watch
coverage uses periodic refresh. Syntax buffers shrink after eight consecutive
small revisions. Undo checkpoints and incremental LSP updates use changed ranges
to avoid repeated full-document scans and copies.
Dirty text equality is cached by document revision and saved-baseline epoch;
explorer row identities are checked independently.

`src/documents.dyn` owns document allocation/release; `src/lifecycle.dyn` coordinates
subsystem cleanup. Session switching is in `src/session.dyn`. Command metadata in
`src/commands.dyn` supplies palette labels, exact aliases and Space-menu bindings;
argument/context handling remains with its owning subsystem.

Full editor smoke tests now live in `tests/editor/`. `just smoke` stages current
production sources with the test startup adapter and builds separate
`build/dna-smoke-debug` and `build/dna-smoke-release` executables under the same
compiler memory limit. `DYN_EDITOR_SMOKE=1` on the normal binary only validates
startup, one full presentation, and shutdown; it does not run the behavioral suite.

Run `mise exec -- just soak` for 20 rounds of editing/search/opening, four rounds
with real syntax and background terminal output, and 300 native resource
lifecycles. It gates memory stabilization, submitted text work, native
allocation balance, descriptor/thread cleanup, and idle redraw/stat behavior.
Manual CI dispatch also runs this extended check. Normal `just smoke` includes
shorter versions, syntax buffer growth and allocation-failure recovery checks,
plus an idle process-CPU budget. Syntax lifecycle checks require the JSON test
grammar and verify completed parsing, stale revisions, and cancellation at teardown.

For desktop measurements, run:

```sh
SDL_VIDEODRIVER=wayland DNA_PERF_REAL_SYNTAX=1 mise exec -- python3 tests/workflow_performance.py
```

This opens a real editor window and replays a temporary project using the installed
JSON grammar under `build/test-languages` (override with `DNA_LANGUAGE_DIR`). Use `x11` instead
when appropriate. Input timings end at SDL present, not the compositor or physical
display. For a retained trace, set `DNA_RENDER_TRACE` to a new absolute filename;
use `scripts/render_report.py` afterward. Profiling itself adds overhead.
