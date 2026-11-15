# Explorer

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

DNA is licensed under the [MIT License](../LICENSE), copyright 2026 Matthew Dray.
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

See [PRERELEASE.md](../PRERELEASE.md) for the prerelease audit, package requirements,
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

`Space s` (`:symbols`) lists the file's symbols from the language server,
nested as the server reports them; typing filters them by name (letters in
order, any case) and Enter goes to one. `Space S` (`:workspace-symbols`) sends
what you type to the server as the query, so it searches the whole project.

Language packages may also contain `textobjects.scm` with predicate-free
Tree-sitter captures named `function.inside`/`function.around`, `class`,
`parameter`, or `comment` with the same suffixes. `mi`/`ma` followed by
`f`, `t`, `a`, or `c` selects those objects (function, type, argument or
parameter, comment). Captures run on the syntax worker. Queries ship for Dyn,
Rust, C, C++, Python, Go, JavaScript, TypeScript, TSX and Bash; reinstall an
existing package with `:language-install NAME`, then `:language-reload`, to get
one. Other languages need their own `textobjects.scm`. Missing or stale results
leave all selections unchanged.

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
