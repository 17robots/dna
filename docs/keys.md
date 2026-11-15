# Keys

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
| Next / previous git change, last / first git change | `]` / `[` then `g`, `G` |
| Next / previous function, type, parameter, comment (needs the language's text objects) | `]` / `[` then `f`, `t`, `a`, `c` |
| Repeat the last insert | `.` |
| Insert mode: delete word before / after, to line start / end, next character | Ctrl-W or Alt-Backspace / Alt-D, Ctrl-U / Ctrl-K, Ctrl-D |
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
| Symbols in this file / workspace (language server) | `Space s` / `Space S`; `:symbols`, `:workspace-symbols [query]`; type to filter, Enter goes |
| Go-to menu | `g` (Escape cancels) |
| Close current buffer | `Space c` or `:bd` |
| New empty buffer | `:enew` |
| Open / save | `Space f` / `:write` then Enter |
| Save and close buffer | `:x` / `:wq` |
| Save all / save all and exit | `:wa` / `:xa` |
| Directory buffer | `Space e`; `Ctrl E` |
| Focus the file tree (`explorer = "tree"`) | `Space E` |
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

Enter runs the highlighted command only when you picked it with the arrows or
Ctrl-N/P, or when each word you typed starts a word of its title (`sw th`
runs **Switch theme**, `sav` runs **Save as**). Anything else, such as a typo
like `:wrtie`, reports `Not an editor command: wrtie` in the status line and
runs nothing; the palette then highlights no row. `!` forms discard instead
of asking: `:q!` closes the buffer, `:qa!` quits, `:e!` reloads from disk.
Vim spellings `:ls`, `:sav path`, `:!cmd` (runs in a terminal) and `:noh`
work too.

Short results appear in the status line until the next key: a search that
finds nothing (`Pattern not found: text`), a write (`"notes.txt" 2L, 24B
written`), an unknown command. `:messages` lists the last 20. With the status
line hidden, errors open a dialog instead.

`:help` opens a generated reference buffer: getting started, every key menu
and your `[keys]` bindings, and every command with its `:` names. `:keys`
shows the key part only. Both are ordinary buffers; search them with `/` and
close them with `:q`.

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
Named registers, macros and syntax-aware selections are covered under Registers,
macros, and syntax navigation below.
The implementation queue and remaining compatibility work are tracked in
[IMPLEMENTATION.md](implementation.md).
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
number. In a git repository the gutter marks lines changed since the file's
committed version: a green bar for added lines, yellow for modified, and a red
line over the line that follows a deletion. Markers follow edits after a short
pause and compare with `HEAD`, fetched again on save; untracked files, files
outside a repository and files over 8 MiB show none. The status line shows mode, filename, modified state, buffer count,
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
| Marks | `m{a-z}`; `` `{a-z} `` and `'{a-z}`, also after operators; `` `` `` and `''`; file marks `m{A-Z}`, `:marks` |
| Replace, format | `R` (Replace mode), `gq{motion}`, `gqq`, `gqap` |
| Search | `/` and `?` (PCRE), `n N`, `* #` |
| View | Ctrl-d Ctrl-u Ctrl-f Ctrl-b, Ctrl-e Ctrl-y, `zz zt zb` |
| Language server | `K` hover, `gd gy gr gi` (definition, type, references, implementation) |
| Buffers, files | `gt gT`, `ZZ` (`:x`), `ZQ` (`:qa`), `:w :q :wq :x :wa :qa`, `:e path` |
| Ex | `:42`, `:[range]s/pattern/replacement/[gi]` with ranges `%`, `N,M`, `.`, `'<,'>`; `&` is the match, `\r` a line break |

Ctrl-o / Ctrl-i walk the jump list (recorded by `gg`, `G`, searches, marks and
LSP goto). `m{a-z}` sets a mark in the current file; `` `{a-z} `` goes to it and
`'{a-z}` to its line, as motions too (`d'a`, `` y`a ``); `` `` `` and `''`
return to the last jump. Marks move with edits and last until the file is
reloaded. `.` after a visual change repeats it on a region of the same size at
the cursor (not after block mode).

`R` enters Replace mode: typed characters overwrite, Backspace puts back what
each one replaced, and typing past the line end appends. `gq{motion}`, `gqq`,
`gqap` and visual `gq` rewrap lines to 79 columns; blank lines separate
paragraphs, and each paragraph keeps its indentation and comment leader, so
code next to a comment is never folded into it. `m{A-Z}` sets a file mark;
`'{A-Z}` and `` `{A-Z} `` open its file and jump there. `:marks` lists the
buffer's marks and the file marks. An unset mark reports `E20: Mark not set`.

Not yet: `=`, sentence and tag objects, `gJ` (joins with spaces like `J`),
`:earlier`/`:later`, and capture groups in `:s` (patterns are PCRE, so write
`a|b`, not `a\|b`). Ctrl-x closes the buffer only in the Helix keymap.

`:[range]sort[!] [i] [n] [u]` sorts whole lines in either keymap; without a
range it sorts the file. `!` reverses, `i` ignores case, `n` compares the first
number in each line, and `u` keeps one of each run of equal lines.

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
