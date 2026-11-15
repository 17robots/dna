# Configuration

## Settings and fonts

Copy [config.example.toml](../config.example.toml) to `~/.config/dna/config.toml`.
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
[profiles/minimal.toml](../profiles/minimal.toml) (Helix keys only). Profiles are
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

`just build-profile terminal` ([profiles/terminal.toml](../profiles/terminal.toml))
builds `build/dna-terminal` with only the terminal frontend. The GUI backend
(`src/platform/gui.dyn`, `src/text/native.dyn`) is replaced by concrete native interface stubs and
the native library is built without GUI or Fontconfig code, so the binary links
no graphics libraries or Fontconfig and runs where there is no display or graphics stack (servers,
containers, SSH). It always starts in the terminal.

### Explorer and picker styles

`explorer = "buffer"` (the default) is the editable explorer described under
[Editable explorer](explorer.md#editable-explorer). `explorer = "tree"` makes Space e
open the project as a collapsible tree, docked on the left (`[place.explorer]`
docks it elsewhere or floats it). Like NERDTree, a docked tree stays beside the
panes after you open a file, with focus on the file. **Space e** toggles the
tree from anywhere: it closes an open tree, focused or not, and otherwise opens
it on the current file. **Space E** (or a click) moves focus back to an open
tree. Set `close_on_open = true` under `[explorer]` to close the tree whenever
you open a file from it.

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
| `q` / Escape | close the tree (Space e opens it again; Space e also closes it from the editor) |

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
job; `fg` brings it back. On Windows it opens a command prompt (`%ComSpec%`) in
the same console instead; `exit` returns to DNA.

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
booleans, quoted strings without escapes, full-line comments, and the tables
described here. Unknown/duplicate settings and invalid values report a line
number and preserve working settings.

### Custom keys

```toml
[keys.normal]            # both keymaps
"f2" = "terminal"
[keys.vim.normal]        # Vim only; wins over [keys.normal]
"Y" = "keys:y$"
"g x" = "keys:dd"
"s" = "none"
[keys.helix.select]      # Helix only
"ctrl-a" = "keys:<Esc>"
[keys.insert]
"j k" = "keys:<Esc>"
[keys.space]
"f f" = "file-picker"
```

Tables are `[keys.MODE]` for both keymaps and `[keys.vim.MODE]` /
`[keys.helix.MODE]` for one; MODE is `normal`, `insert`, `select` (alias
`visual`, Vim's visual modes and Helix select mode) or `space` (after Space).
Up to 128 bindings.

- **Keys** are a character (`$`, `A`, `é`; matched by what you type, so any
  layout works) or a name: `space`, `backslash`, `esc`, `enter`, `tab`,
  `backspace`, `delete`, `insert`, `home`, `end`, `pageup`, `pagedown`, arrows
  (`up` …), `minus`, `lt`, `f1`–`f12`. Prefix `ctrl-`, `alt-`, `shift-` (or
  `C-`, `A-`/`M-`, `S-`).
- **Sequences**: up to four keys separated by spaces. The keys wait up to one
  second; a key that breaks the sequence, or the timeout, lets them act as
  usual (in insert mode they type). A binding that is also the start of a
  longer one runs on timeout.
- **Values**: a palette command (with arguments, as typed after `:`), `none` to
  disable the key, `move-up`/`move-down`/`move-left`/`move-right`/`page-up`/
  `page-down`, or `keys:` followed by keys in Vim notation (`<Esc>`, `<CR>`,
  `<C-w>`, `<lt>` for `<`). `keys:` keys are typed without remapping, use a
  count typed before the binding (`3Y`), and repeat with `.` like the keys
  themselves.
- Normal bindings work in documents and both explorers, but not partway
  through a Vim operator or prefix, while choosing a register, or in terminal
  input. Custom Space bindings show in the Space menu.

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
