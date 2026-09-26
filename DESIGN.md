# DNA — native modal editor design

Status: agreed direction; working project name: DNA. This document describes a new
editor, separate from the Dyn compiler and dyn-editors integrations. The browser
layout sketch in build/editor-layout-prototype is disposable and does not specify
the production UI or implementation technology.

## Experience

The default screen contains only the current file buffer. No persistent toolbar,
sidebar, layout selector, or tabs. A hideable line-number gutter and slim status
line are enabled by default, with subtle current-line highlighting. Supporting views appear
as popup buffers when invoked by a keybinding or command. Optional arrangements
can keep views visible without assigning any view a permanent sidebar role.

The editor is modal. Start with Helix-style selection-first behavior; design the
mode interface to support a later Vim-style profile. Profiles govern editing
semantics, including directory buffers, not just keybindings. Compatibility with
existing Vim/Helix plugins or configuration is not a first-version goal.

Every operation is keyboard-accessible through commands. Frequent operations get
shortcuts; every command is discoverable through the palette and can be bound.
Final default bindings remain to be selected. The palette offers descriptions,
current bindings, argument entry, contextual availability, and explanations when
a command cannot run. Layout switching is visible as a palette command, not as
persistent screen chrome.

## State and placement

- Buffer: document contents or another model, such as directory entries or search
  results. Document edit transactions and undo history belong to the document.
- View: a cursor, selections, scroll position, and interaction state for a buffer.
- Placement: a view's location and relative size—popup, split, or full area.

Dismissing a popup closes its presentation, not its underlying document or pending
operations. Focus returns to the invoking view with its selection intact. Nested
popups unwind one level at a time. Closing an unsaved document is a separate action
that requires a save/discard decision.

## Layouts and configuration

Use a simple declarative settings file and separate named layout files. The current
implementation uses a restricted TOML settings file with explicit reload and
validated command-key overrides; named layout files remain separate.
Users can load/switch layouts through the palette or bind a named layout directly.
Interactive placement changes can be saved to a layout file.

Layout files describe roles (current document, directory, search, diagnostics),
relative sizes, and arrangements, rather than hard-coded file paths. Session state
records open files, navigation positions, and other automatically maintained data
separately from user-authored preferences.

Switching layouts preserves buffers, selections, undo history, and unsaved edits.
Validate a layout before applying it; an invalid file leaves the active layout
intact and produces an actionable error. Missing optional view providers must not
prevent access to documents. When minimum sizes cannot fit, use a simpler
arrangement while preserving the requested layout for a larger screen.

## Core keyboard workflows

The following are command sequences, not final shortcut assignments:

1. Open project → invoke Directory → navigate/select using the active editing
   profile → open file → directory popup dismisses → file receives focus.
2. Invoke Directory → queue create/rename/move/delete operations → invoke Apply
   → inspect operation preview → validate collisions/external changes → apply.
   Closing the popup preserves pending operations. Explicit discard clears them.
3. Invoke Command Palette → filter commands → choose command → supply arguments
   where needed → execute → focus returns to the appropriate view.
4. Invoke Command Palette → Switch Layout → choose a named file → validate and
   apply placement without modifying document state.
5. Invoke a supporting buffer → invoke Change Placement → choose popup, split,
   or full area → retain the same buffer and view state.
6. Edit → undo/redo transactions → explicit Save. Crash-recovery snapshots are
   separate from saves to the original file.

Filesystem actions are not automatically ordinary text undo. Decide deletion
recovery before enabling delete. Before applying a batch, check destinations,
unsaved affected documents, and external changes; report partial failures honestly
rather than assuming multiple filesystem operations are atomic. Successful renames
update affected open-document paths.

## Implementation

Native Dyn application, with graphics/input library bindings and an immediate-mode
GUI. No browser runtime, Electron, HTML, or CSS in the production application.
The Linux build uses SDL3 and SDL_ttf. Binaries embed a relative library path
(`$ORIGIN/deps/install/lib`, `$ORIGIN/../lib`), so they start without
`LD_LIBRARY_PATH`; the release archive bundles its non-glibc libraries. Use a small C bridge only where the ABI requires it.

The GUI derives its presentation from durable editor/view state when a redraw is
needed. Immediate mode does not require continuous idle rendering. A TUI frontend
shares documents, transactions, commands, modes, and layout intent with the GUI.
Build the first native vertical slice on Linux, then bring the same workflow to
the TUI. Keep platform interfaces suitable for Windows and macOS.

The small core owns document integrity, transactions/undo, command dispatch, input
routing, scheduling, plugin lifecycle, and rendering/view primitives. User-facing
features—including the palette, directory buffers, editing profiles, language
support, and language tools manager—are bundled modules behind explicit interfaces.
Bundled features should exercise the public extension interfaces. Compile them
into the application initially; modularity does not require dynamic loading.

The language tools installation mechanism is built in, but tool installation is
user-selected. Custom language definitions must work locally without publishing
or writing a plugin: file patterns, grammar, server/formatter commands, indentation,
and root detection. Keep generated package records out of user settings.

### Immediate-mode UI core (`src/ui.dyn`)

Popups, pickers, menus, dialogs, the explorer frame, status lines and split
handles are built with a small immediate-mode UI in the style of the RAD
Debugger. `draw()` begins one UI frame; each panel on screen adds a top-level
box tree for that frame and lays out and renders it. Nothing is built on frames
that are not drawn, so idle cost stays zero.

- Boxes are keyed by a hash of their name and parent key. A fixed pool keeps
  per-box state across frames (hover and selection fades, scroll offsets); boxes
  not built in the previous frame are reused. Equal names in one frame get a
  derived key instead of failing.
- Sizes are declared per axis: pixels, text content, percent of parent, or sum of
  children, each with a strictness. Layout runs standalone, parent-dependent and
  child-dependent passes, then resolves overflow: fully flexible boxes (strictness
  0) give up space first, the rest shrink proportionally.
- Input hit-tests the rectangles from the last drawn frame, respecting clipping
  ancestors; the latest-built box wins. Motion requests a redraw only when the
  hovered box changes.
- Animation reuses the editor's interruptible tweens (`popup_animation_ms`,
  `scroll_animation_ms`, reduced motion).
- Fixed-row lists build only the rows near the visible range and stand in
  spacers for the rest, so list length never exhausts the pool.
- Specialised renderers stay custom and draw inside a UI box: document text,
  the explorer's editable listing, picker/explorer previews, hover and dialog
  bodies, and the terminal grid.

## Responsiveness and memory

Measure startup, input-to-display latency, idle CPU, large-file behavior, and total
session memory (including external tools). Set numerical budgets after measuring
the first vertical slice; no performance claims are established yet.

- Activate language support and external tools only when needed.
- Batch rendering and highlighting work; avoid plugin calls per displayed glyph.
- Keep searches, tooling, and remote I/O off the input/rendering path.
- Give document data explicit lifetimes; frame scratch storage must not escape
  into documents, undo history, or asynchronous jobs.
- Avoid full document copies for every plugin; define bounded read access and
  versioned edits through the core.
- Recover from tool failures without losing documents. Native in-process plugins
  are not crash-isolated merely because they use a plugin interface.

## Remote sessions

Support a local GUI connected to an editor service through an existing SSH tunnel.
File operations, searches, and language tools run beside the remote project.
The local GUI retains sufficient document/view state for responsive interaction.
The tunnel is transport, not synchronization: document versions, edit ordering,
reconnection, conflicts, and recovery still require a protocol.

A TUI can also run directly on the remote machine through an ordinary SSH session.
Both paths must preserve unsaved work across recoverable disconnects. Implement
remote sessions after reliable local editing; do not let the initial interfaces
assume all services share the GUI process.

## First-version boundary and deferred choices

First native vertical slice: window, file buffer, one modal profile, popup directory
buffer, command palette, relative layout switching, undo/redo, explicit save, and
crash recovery. Follow with the equivalent TUI workflow before building a broad
plugin ecosystem. Handle UTF-8 safely from the beginning and exercise cursor and
selection boundaries, composition input, and font fallback early.

Deferred: project name; final shortcuts/config syntax; document storage structure;
font/text-layout backend; deletion recovery mechanism; stable third-party extension API and OS sandboxing; remote synchronization protocol; full Vim
compatibility scope; complete accessibility and platform integration design.

Current prototype: the separate `dna` repository implements native SDL3/SDL_ttf
rendering, multiple UTF-8 file buffers, modal selection/editing, undo/redo, search,
command and directory popups, editable directory drafts with previewed create/rename/trash batches,
validated popup/font/chrome layout files, explicit saves, and background session recovery.
README.md describes the tested behavior and limits. This is not yet the complete
architecture above: crash recovery for directory drafts, nested supporting buffers,
editing profiles, richer extension interfaces, and a shared TUI remain
next steps. Keep editor application code out of the compiler repository.

## Current project/process/language boundaries

The project root is independent of explorer navigation and terminal working
folders. `:cd` changes the editor process directory and invalidates its picker;
file buffers retain absolute paths. A terminal is a slot-owned PTY/libvterm model
with popup or split presentation. Hiding views keeps processes alive; closing a
live terminal or exiting requires confirmation. Tasks use this same process model.

Tree-sitter parsers own worker threads and consume copied document snapshots.
Results carry revisions so rendering never applies stale byte ranges. Grammar
installation is explicit, checksum-pinned, validated, and activated atomically.
The Dyn native adapter handles libvterm, POSIX PTYs, Tree-sitter worker lifetime,
and Fontconfig enumeration through external library bindings. Stable exported
`dna_*` interfaces preserve the editor, installer and test ABI. Pthread calls
retain libc TLS initialization; the raw Dyn clone API is unsuitable for these
workers until it provides that contract. Header probes validate Linux x86-64
layouts before building. GUI-only functions have Dyn stubs for the TUI profile.
These are internal modules, not the final public plugin API.

## Local editor services (September 2026)

Project search owns a cancellable worker and versioned result set. Replacement
previews validate every target before applying undoable buffer edits. Disk saves
remain explicit. Search is bounded and currently scans saved files.

Workspace snapshots use a versioned, length-delimited format with validated split
trees. Recovery writes coalesce on a background worker, use private permissions,
and atomically replace each instance's snapshot. A session includes current text
and saved baselines; terminals restore as empty views. Layout files persist only
relative topology/chrome, independently of document paths and session content.

The first extension API uses independent processes and newline-delimited JSON.
Commands feed the existing palette/keybinding dispatch; buffer creation and
revision-checked replacement use core document operations. Permission checks
apply to editor APIs, not OS filesystem/network access. See PLUGINS.md. Built-in
features remain statically linked; converting every feature into an external
process would add overhead without improving these ownership boundaries.

Document capacity is 256 MiB minus one byte. Each document's storage (text,
saved copy, undo checkpoint, line index and a 1 GiB circular undo byte store with
up to 64 metadata entries) is one reserved `MAP_NORESERVE` mapping, so only the
pages a file actually uses occupy memory. Documents of 16 MiB and more are plain
text: no syntax highlighting, no language server, and recovery snapshots record
them by path for reloading instead of rewriting their text. This keeps storage bounded while
storing only removed/inserted bytes for each checkpoint. A retained checkpoint
baseline lets grouped edits form one delta. Cursor/selection/explorer identities
remain per-state metadata; discarded redo storage is reused immediately.
Large replacements can exhaust the byte budget sooner than small edits.
Saved and checkpoint views share the current text while unchanged. Before the
first mutation, the editor materializes each baseline in its reserved backing;
subsequent edits reuse that storage. Saving or checkpointing can share the new
current text again. This avoids two full resident copies for untouched open
files while preserving saved-content comparisons and grouped undo. The first
edit bears the copy cost; returned baseline views are borrowed until mutation.

Syntax workers grow their snapshot and color buffers to match document size,
with geometric capacity growth and a byte of EOF slack. Shared buffers remain
mutex-protected; parsing scratch buffers belong to the worker thread. Teardown
releases every buffer. Failed buffer growth preserves ownership and permits a
retry of the same document revision.

A document-owned line index supports binary-search offset-to-row lookup and
direct row-to-offset lookup; edits adjust the affected entries. Split views own
bounded viewport text layouts. Terminal normal mode freezes a bounded read-only scrollback and screen
snapshot and routes permitted motions through the document editing model.
Native descriptor readiness and syntax/search completion wake SDL; no terminal
or plugin process requires a perpetual 16 ms UI polling loop.


## Ownership and shutdown

`App` groups document ownership in `Documents`, pane state in `Views`, project
paths in `Workspace`, and recovery scheduling in `RecoveryState`. Editing and
prompt dispatch live in separate modules. A `Slot` owns its document arena,
syntax worker and terminal, including terminal input mode, review selection,
cursor animation, and pending key sequences. Switching panes never transfers
ownership of a document or a terminal.

Each pane owns its viewport, caret and 128 syntax-span text objects. Cache keys
include buffer identity and revision; ranges distinguish visible spans. Theme
colors update independently of shaping. Font changes update every retained text
object before releasing the old font. Overflow spans use the shared fallback
text object. SDL_ttf's pinned renderer patch culls glyph submissions to the
explicit clip rectangle; dependency builds verify the patch context.

Native open/create functions transfer one handle to the caller. Submit/update
functions copy input before returning; workers never borrow mutable Dyn document
storage. Close functions stop and join their workers before freeing state. UI
code owns handles and descriptor registration; the notification thread only
posts pointer-free wakeups. Remove a readiness registration before closing its
file descriptor. Worker completion notifications can coalesce: the UI polls
owned handles, not pointers embedded in events.

Background search, plugins, recovery, syntax and terminals shut down before
font/renderer/window destruction. Notification delivery stops before SDL quits.
Document arenas are released after their consumers. Recovery close discards
queued work and removes this instance's recovery file on clean exit; a crash
leaves the last atomically replaced record. The single recovery worker creates
directories and files, flushes replacements, and reports failures for the UI to
consume. Legacy sidecar recovery remains read-compatible only.

## Storage decision and performance checks

Keep contiguous document storage up to 256 MiB. Edits cost one memmove of the
text after the cursor, and checkpoints compare and copy the document, so bulk
operations go through glibc (`__memcpy_chk`/`__memmove_chk`, `memchr`, `memcmp`):
the Dyn runtime's own memcpy/memmove/memset copy a byte at a time and are kept
local to the executable (version script) so other libraries keep glibc's. On a
100 MiB log, typing at the top of the file measured 8.6 ms from key to present,
held j/k under 2 ms, and opening took 85 ms more than a small file. A piece table
would make edit cost independent of size, but every direct `document.bytes`
access would change with it.

The rendering regression checks unchanged split redraws for zero large text
reshaping, exercises a 1 MB line and a large Unicode selection, and bounds
long-line geometry submissions. Lifecycle tests compare file descriptors,
threads and resident memory after warming the allocator. Fault tests interrupt
real writes and inject recovery flush failures; they verify old committed data
and retry behavior. Timing results are local observations, not portable latency
guarantees. The existing workflow replay additionally checks rendered pixels
and repeated search/open/edit/undo behavior.

Syntax-span caches also retain local glyph geometry and bearings. Buffer identity,
revision, span range and viewport range validate that geometry; font replacement,
font sizing and line-spacing changes invalidate it. Scrolling, clipping and theme
colors remain live. The unchanged split redraw test bounds geometry queries, and
pixel comparisons exercise cached layouts after font zoom. Terminal backgrounds
merge adjacent equal-color cells into horizontal runs before glyphs/cursors draw;
a mixed ANSI-color fixture checks the rectangle budget and color boundaries.


Language-server transport lives in the native readiness layer; protocol state,
UTF-16 conversion, result presentation and validated buffer edits live in Dyn.
Workspace edits preflight every target before applying. Results own their parse
arenas and are discarded on identity/revision mismatch. External file watching
owns one worker and posts changes to the UI; only the UI mutates documents.
Both lifecycles shut down before SDL teardown. Unicode editing uses utf8proc's
extended-grapheme boundaries; byte offsets remain the storage/protocol boundary.
Sparse document mappings disable Linux transparent huge pages to avoid touching
megabytes of unused storage for short text prefixes.

## Source organization and cleanup rules

`src/app.dyn` is the root state inventory. Related storage belongs in the named
subsystem records declared beside the code that uses it: macros, registers,
plugins, configuration, completion, pickers, prompts, and project search.
These records remain inline in the existing App arena; grouping them does not
introduce allocation, reference counting, or per-frame copies. Pass App and its
large state records by pointer. Arena allocation is zero initialization; explicit
startup functions still establish nonzero defaults.

`editor.dyn` coordinates popup submission and presentation. File operations live
in `file_actions.dyn`, command names and dispatch in `command_palette.dyn`, font
and text-rendering records in `typography.dyn`, and bounded text helpers in
`text_helpers.dyn`. Buffer contents and editing semantics remain in `buffer/`.

Keep declarations readable with related fields together and multiline records
for large types. Preserve field order in SDL, SDL_ttf, libc, and other foreign
structs: their layout is a protocol, not an internal implementation choice.
`tests/platform_abi.py` compares actual Dyn layouts against SDL headers, while
`tests/input_save.py` exercises typing, Escape, and saving through real SDL events.
Keep Document byte storage after its explicitly initialized metadata as documented
in `buffer/buffer.dyn`; do not reorder that allocation contract either.

The native job and RPC implementations are in `src/native/dyn/`; obsolete C
copies have been removed. Native adapters keep their existing exported names so
callers and process-lifecycle tests exercise the same implementation.
