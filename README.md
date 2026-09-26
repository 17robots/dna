# DNA

A native modal editor prototype written in Dyn. The window shows your document;
commands, search, files, and layout controls appear as keyboard-invoked popups.
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

Start in normal mode. Press `i` to type, Escape to return to normal mode,
`Ctrl S` to save, and Space or `Ctrl P` for searchable commands. An unnamed
buffer prompts for a new destination when saved. File paths in Open/Save As
are relative to the directory where DNA was launched; directory-buffer create
and rename operations use the directory being displayed. Paths are literal:
no shell expansion of `~`, environment variables, or globs.

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
| Command palette | Space or F1 in normal mode; `Ctrl P` |
| Open / save | `Ctrl O` / `Ctrl S` |
| Directory buffer | `Ctrl E` |
| Font larger/smaller/reset | `Ctrl +` / `Ctrl -` / `Ctrl 0` |
| Quit | `Ctrl Q` or close window |

In prompts, type and press Enter; Backspace edits the query. The palette filters
case-insensitively; arrows select a command. Document search is literal,
case-sensitive, and wraps. Insert-mode Tab inserts four spaces.

In the directory buffer, `j/k` or arrows select, Enter opens, Backspace goes to
the parent, `c` creates, `r` renames, and `d` requests a move to `.dna-trash`.
Rename and trash show a confirmation before applying. Existing destinations are
never replaced. These operations affect one file at a time; directories cannot
be renamed or trashed yet. Filesystem operations are separate from text undo.
Restore trashed files manually from `.dna-trash`; collisions there are refused.

## Layout files

Use **Load layout file** in the palette, or the built-in compact/wide commands.
Examples are in `layouts/`. The current layout implementation controls popup
size and font size; document splits and arbitrary buffer placement are future work.

```ini
popup_width = 0.64
popup_height = 0.56
font_size = 20
```

Popup dimensions are fractions of the window, between 0.25 and 1.0. Font size
is 12–36. Blank lines and whole-line `#` comments are accepted. Duplicate/unknown
keys and invalid values are rejected before anything changes. Popups expand when
needed for readable content, capped by the window. Switching layouts preserves
text, selections, and undo history. It does not persist changes to a layout file.

## Saving and recovery

Saving writes a sibling temporary file, flushes it, then renames it over the
original. Existing file permission bits are preserved. A content check refuses
to overwrite a file changed externally; Save As only creates new destinations.
Opening another file or creating a new buffer refuses to discard unsaved edits.
Quit offers save/discard/cancel. The palette also provides an explicit discard
confirmation. Symlink files are refused; open their targets explicitly.

For a **named, modified** document, a 500 ms idle period writes a separate
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

- One open document, up to **65,535 UTF-8 bytes**; NUL/binary files are refused.
- Up to 64 undo states, with insert runs grouped until movement/mode changes.
- UTF-8 codepoint movement/deletion; grapheme-aware editing, composed-character
  cursor behavior, IME preedit UI, and comprehensive bidirectional text need work.
- Keyboard editing and cursor-following scrolling; no mouse editing/wheel scrolling.
- Directory listings show at most 256 entries; paths/prompts have fixed limits.
- No syntax highlighting, LSP, configurable keymap, full Vim profile, TUI, SSH,
  public plugin API, multi-buffer sessions, or queued filesystem batches yet.
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
validation, and the native open/edit/save/create/rename/trash workflow. Synthetic
SDL input passes through the actual event loop. Font geometry and ABI checks run
against the installed headers. Physical keyboard and IME testing remain separate.

The document owns its text, saved baseline, and bounded undo snapshots in an arena.
File/prompt/event bytes are copied before their source expires. Temporary file
reads use a rewindable scratch arena. SDL text objects die before their font,
engine, and renderer. Rendering happens on relevant events; idle waits do not redraw.
The editing, file, and layout modules do not depend on SDL.

Non-colocated jj, local only. No remote or publication. The project name DNA is
provisional; the extension architecture in DESIGN.md is not implemented yet.
