# DNA

A native modal editor prototype written in Dyn. The window shows your document;
line numbers and a slim status line provide orientation. Commands, search, files,
and buffer switching appear as keyboard-invoked popups.
No web runtime. [DESIGN.md](DESIGN.md) records the broader product direction.

## Run

Requirements: Linux x86-64, a working Dyn SDK, SDL3 development/runtime libraries,
FreeType and HarfBuzz development libraries, CMake, Python 3.12+, a C compiler,
and `just`. Tested with Dyn 0.1.0-preview.5, SDL 3.4.16 and SDL_ttf 3.2.2.
`just build` downloads and builds pinned SDL_ttf into ignored `build/deps`;
it does not install system packages.

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

Start in normal mode. Press `i` to type, Escape to return to normal mode,
`:write` then Enter to save, and `:` for searchable commands. Space opens a shortcut guide;
Ctrl shortcuts remain alternatives. An unnamed
buffer prompts for a new destination when saved. File paths in Open/Save As
are relative to the directory where DNA was launched; directory-buffer create
and rename operations use the directory being displayed. Open expands `~`/`~/` and suggests matching files/directories as you type.
Tab completes, arrows choose, and Enter opens a file or enters a directory.
Completion uses filename prefixes, showing at most 128 matches. No shell expansion
of environment variables or globs is performed.

Text uses antialiased fonts, 1.5× line spacing, and display-aware scaling. Zed Mono
is preferred, with Noto Sans Mono as fallback. Choose a font with
`DNA_FONT=/absolute/path/font.ttf just run`. No fonts are bundled.

## Keys

These are provisional, Helix-inspired controls, not full Helix or Vim compatibility.
Selections span the bytes between anchor and cursor; `v` extends the selection
with movement, and typing in insert mode replaces a selection.

| Action | Keys |
| --- | --- |
| Insert / append after cursor / new line below | `i` / `a` / `o` |
| Leave insert/select mode; dismiss popup | Escape |
| Move | Arrows; normal-mode `h j k l` |
| Extend selection | Shift + arrows; normal-mode `v`, then movement |
| Select line / select all | `x` / `Ctrl A` |
| Line start/end; document start/end | Home/End; normal-mode `g`/`Shift G` |
| Move 20 lines up/down | Page Up/Page Down |
| Delete / change selection (or next character) | `d` / `c` |
| Undo / redo | `u` / `Shift U`; `Ctrl Z` / `Ctrl Shift Z` or `Ctrl Y` |
| Copy / paste | `y` / `p`; `Ctrl C` / `Ctrl V` |
| Search; next/previous match | `/` or `Ctrl F`; `n` / `Shift N` |
| Command palette | `:` or F1 in normal mode; `Ctrl P` |
| Shortcut guide | Space |
| Buffer picker / next / previous | `Space b` / `Space n` / `Space p` |
| Close current buffer | `Space c` or `:bd` |
| New empty buffer | `:enew` |
| Open / save | `Space f` / `:write` then Enter; `Ctrl O` / `Ctrl S` |
| Directory buffer | `Space e`; `Ctrl E` |
| Font larger/smaller/reset | `Ctrl +` / `Ctrl -` / `Ctrl 0` |
| Quit | `:q`, `Ctrl Q`, or close window |

The command palette supports descriptive names and short commands: `open`/`e`,
`write`/`w`, `quit`/`q`, `buffers`/`b`, `bn`, `bp`, `bd`, and `enew`. `:open path`
and `:write path` accept a literal path (including spaces) and expand `~/`.

Each document retains its text, undo history, cursor, selection, editing mode,
and scroll position when switched away. Opening another file preserves the
current buffer, including unsaved edits; reopening the same resolved path switches
to its existing buffer. Buffer search filters by filename and marks modified files.
Closing a modified buffer prompts for save/discard/cancel. Quit visits every dirty
buffer, including hidden ones; Escape cancels further closing. Confirmed discards
before cancellation remain discarded. Buffer/session state is not persisted across
launches.

Line numbers are relative except for the current line, which shows its absolute
number. The status line shows mode, filename, modified state, buffer count,
line/column, and selected codepoints. Palette commands independently toggle line
numbers, relative numbering, the status line, and current-line highlighting.

In prompts, type and press Enter; Backspace edits the query. The command palette
is a compact panel near the bottom with up to four visible results. It filters
case-insensitively, prioritizes prefixes, and caches unchanged queries/text layouts;
arrows select a command. Document search is literal,
case-sensitive, and wraps. Insert-mode Tab inserts four spaces.

## Editable explorer

`Space e` opens an editable directory popup. It shares the document editing keys:
`h/j/k/l`, `i`, `a`, `o`, `v`, `x`, `d`, `c`, `u`/`Shift U`, and clipboard commands.
Enter in normal mode opens the current row; Backspace goes to its parent.
Apply or discard pending edits before navigating to another directory.

Existing rows look like `[1] filename.txt`. Keep the `[id]` and its following space
unchanged; edit the filename to stage a rename. The id identifies the original file
even if rows move. Add a plain filename on a new line to stage an empty file.
Delete an entire existing row (`x`, then `d`) to stage a move to `.dna-trash`.
Directory rows end in `/` and must remain unchanged; folder creation, renaming,
and removal are not supported yet. Names beginning with `[` cannot be created
through a new row, and control characters in names are unsupported.

For example, changing:

```text
[1] notes.txt
[2] old.txt
```

to:

```text
[1] journal.txt
new.txt
```

stages a rename, a new file, and a move of `old.txt` to trash. **Nothing on disk
changes while you type.** Escape leaves insert/select mode; another Escape hides
the explorer while keeping its draft and undo history.

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
size, font size, and document chrome; document splits and arbitrary buffer placement are future work.
The command palette uses content-sized height, and the editable explorer uses a
larger scrolling view; neither reserves the generic popup height.

```ini
popup_width = 0.64
popup_height = 0.56
font_size = 20
line_numbers = 1
relative_numbers = 1
status_line = 1
highlight_line = 1
```

Popup dimensions are fractions of the window, between 0.25 and 1.0. Font size
is 12–36. Chrome switches use 0/1 and default to enabled.
`layouts/minimal.dna-layout` hides the gutter, status line, and line highlight. Blank lines and whole-line `#` comments are accepted. Duplicate/unknown
keys and invalid values are rejected before anything changes. Popups expand when
needed for readable content, capped by the window. Switching layouts preserves
text, selections, and undo history. It does not persist changes to a layout file.

## Saving and recovery

Saving writes a sibling temporary file, flushes it, then renames it over the
original. Existing file permission bits are preserved. A content check refuses
to overwrite a file changed externally; Save As only creates new destinations.
Opening another file or creating a new buffer retains unsaved edits in its original
buffer. Close and quit offer save/discard/cancel. The palette also provides an explicit discard
confirmation. Symlink files are refused; open their targets explicitly.

For each **named, modified** document, including inactive buffers, a 500 ms idle period writes a separate
`<filename>.dna-recovery` snapshot with private permissions. It never autosaves
the original. After a crash, reopen the original and choose **Restore recovery
snapshot**, then save normally. An existing unclaimed snapshot is preserved until
you explicitly restore it. Snapshots owned by this session are removed on save
or explicit discard. Untitled buffers do not yet have crash recovery. A write
error is shown in a popup; the in-memory document remains available.

This is still a prototype: content checking is not a filesystem lock, and saving
replaces the inode (hard links, ownership, ACLs, and extended attributes are not
preserved). Rename durability across power loss is not guaranteed. Recovery is
not a replacement for backups or version control.

## Current limits

- Up to **16 open documents**, each up to **65,535 UTF-8 bytes**; NUL/binary files
  are refused. Storage allocates lazily, roughly 4.3 MiB per open document.
- Up to 64 undo states, with insert runs grouped until movement/mode changes.
- UTF-8 codepoint movement/deletion; grapheme-aware editing, composed-character
  cursor behavior, IME preedit UI, and comprehensive bidirectional text need work.
- Keyboard editing and cursor-following scrolling; no mouse editing/wheel scrolling.
- Directory listings and staged batches support at most 256 entries/operations.
  Explorer text has the same 65,535-byte limit and allocates its own undo arena.
- No syntax highlighting, LSP, configurable keymap, full Vim profile, TUI, SSH,
  public plugin API, split views, or persistent sessions yet.
- File operations currently target Linux x86-64. Windows/macOS are not supported
  by this prototype yet, despite the portable SDL rendering layer.

## Checks and ownership

```sh
just smoke  # core/file/layout tests + native UI workflow, debug and release
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

The document owns its text, saved baseline, and bounded undo snapshots in an arena.
File/prompt/event bytes are copied before their source expires. Temporary file
reads use a rewindable scratch arena. SDL text objects die before their font,
engine, and renderer. Queued events are processed in bounded batches before drawing, and unchanged
window titles are not resubmitted. Idle waits do not redraw. Trailing spaces
and indentation retain their layout width, including in cursor/selection geometry.
The editing, file, and layout modules do not depend on SDL.

Non-colocated jj, local only. No remote or publication. The project name DNA is
provisional; the extension architecture in DESIGN.md is not implemented yet.
