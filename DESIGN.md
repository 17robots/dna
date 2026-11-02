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

Documents have no fixed size. Text lives in a persistent piece tree
(`src/buffer/rope.dyn`): immutable blocks of up to 16 KiB per leaf, AVL-balanced
internal nodes caching byte and newline counts, and a per-leaf table of newline
offsets. Edits build new nodes along one path and share everything else, so the
saved baseline and each of up to 64 undo entries are retained roots, not copies.
Undo retains at most 64 states and budgets 1 GiB of private changed text;
removed or inserted ranges still backed by a file mapping do not consume that
byte budget. Small edits preserve mapped neighbors instead of copying them into
private blocks. Tree metadata and retained baselines remain separate costs.
`buffer.Capacity` (256 MiB) bounds individual contiguous insertion and clipboard
operations, not document size. Formatter input uses retained storage chunks;
output can grow to 4 GiB minus one byte and is adopted directly as text storage.

Language-server shadows retain immutable roots. Opening and full-change messages
escape document chunks directly into the native outgoing queue, with no separate
flattened or escaped editor copy. Outgoing encoded messages are bounded at 1 GiB;
incoming responses retain their independent 8 MiB bound. Ranges of 16 MiB and
more are escaped from a snapshot by one thread per CPU (a measuring pass, then
a writing pass) that skip plain runs a word at a time; the UI thread waits for
them, about 140 ms for 1 GiB. Queued JSON still occupies memory until sent. Incremental
changes send only the changed range.

Large-file recovery records a stamped replacement patch against the saved file.
Restore checks the stamp before applying the patch and transfers that stamp to
the restored file state. A mismatch aborts restore without replacing the current
workspace. The native recovery record remains bounded at 1 GiB total and
256 MiB of new bytes;
if edits cannot fit, capture fails and retains the previous record instead of
silently replacing unsaved edits with a path-only entry.

Syntax highlighting on large documents parses a shared snapshot, with colors
queried around the last drawn view (`syntax_window_tick` in `src/syntax.dyn`).
Tree queries for objects and syntax selections remain disabled for these
documents. Cursor, selection and explorer identities remain per-state metadata.

Single-line drawing is bounded at 64 KiB of text per displayed row. On a longer
line, a window follows the primary cursor in half-window steps. Drawing, caret
geometry, selections, syntax ink and mouse hit tests share its origin. Text
outside the current window becomes visible when the cursor moves there.
`tests/large_file.py --mib 1024 --binary build/dna-release` checks a real terminal
open, end motion, visible insertion and byte-exact save on a 1 GiB single line.
Native framebuffer tests cover windowed GUI drawing and selection consistency.

Files of 256 MiB and more open lazily (`src/buffer/lazy.dyn`): the document
appears after its first 4 MiB of whole lines are checked, while workers
validate and index the rest; the scheduler polls `load_tick`, which appends the
tail to the current text, the saved baseline and every undo root. Edits made
meanwhile touch only the prefix, so all of them stay consistent. Saving, disk
comparison and recovery patches wait for completion; a tail that is not UTF-8
leaves the start open with saving disabled. A 1 GiB file shows its first frame
in about 10 ms.

Large-document syntax parses immutable piece-tree snapshots from the beginning
of the document (`syntax_stream.dyn`). The worker reads chunks directly without
flattening the document. Queries and color output stay confined to an 8 MiB
view window, so comment and string openers retain their context regardless of
their distance from the view. Scrolling at the same document revision reuses the
complete tree. Edits cancel stale parsing; a new revision reparses in the worker.
The UI releases snapshot references only after a completion acknowledgement,
including cancellation and shutdown. Predicate captures spanning chunks are
copied into worker scratch buffers and evaluated normally. Tests cover 12 MB
comments and strings, range changes, predicates and source lifetime.

Parse-tree memory and parse time now follow the full document's grammar
structure; color storage remains bounded and the document text is shared. The
Tree-sitter byte API is 32-bit: documents beyond 4 GiB minus 2 bytes remain
uncolored, rather than parsing a window without its preceding grammar state.

Recovery for large files records edits as pieces of the saved file plus only
the new bytes (`buffer.saved_pieces`), found by matching leaf storage
addresses, so edits far apart cost only what was typed; records stay bounded by
256 MiB of new bytes per record (1 GiB total record size). Edited spans over
1 MiB use pieces even when a contiguous patch would fit. Restore checks the
file's stamp, then rebuilds the text from the pieces as one undoable edit.

The disk watcher needs a hash of the saved text as its baseline. Files with a
stamp from when they held that text (every opened or saved file) pass the
stamp instead (`dna_disk_watch_stamped`): the watcher thread hashes the file
itself while the stamp still matches and reports it changed otherwise, so the
UI thread never hashes a large file. Reloads from disk refresh or drop the
stamp.

macOS and Windows report real file stamps (fstat, GetFileInformationByHandle)
so unchanged-file checks skip rereads. The filesystem boundary now supplies
read-only mappings on both platforms: Darwin uses MAP_RESILIENT_MEDIA so
inaccessible backing pages become zeroes; Windows views prevent truncation
until unmapped. Mapping failures retain the ordinary read fallback. The mapper
callback carries an isize descriptor so Windows HANDLE values are not narrowed.
Linux's editor still installs its native SIGBUS guard.

Windows range copies try ReFS block cloning for 64 KiB-aligned interiors and
copy partial edge blocks through a separately reopened source handle. Unsupported
filesystems or incompatible source/destination alignment fall back to writing
immutable document bytes. Failures after copying an edge abort the transaction.
APFS saves can seed the exclusive temporary file from a whole-file clone
(`fclonefileat`). The source stamp must match before and after cloning. The
writer seeks past unchanged runs still at their original offsets, writes edited
or shifted runs, resizes the clone to the snapshot length, then uses the existing
sync/conflict-check/atomic-rename sequence. Read-only origins, unsupported volumes
and failed clone setup retain the normal exclusive-create/full-write fallback.
Existing temporary paths are never replaced. Save As keeps its original path and
permission behavior. Mapped origin stamps are checked again after writing and
before publication so an externally changed mapping cannot validate itself as
its saved baseline. `tests/clone_save.py` runs the production Darwin setup and
writer against a Linux clone emulator, checking exact bytes, write avoidance,
shifted edits, truncation, repeated saves, mapped-source changes, failures,
permissions and descriptor cleanup in debug and release.

Platform seams have deterministic mocks and x86-64/arm64 target checks. Native
filesystem CI exercises mapping, truncation, range-copy fallback and exclusive
clones. macOS arm64 CI is configured to run a real mapped-buffer/APFS save test and
the isolated window/presenter qualification. These native runs remain unverified locally on
Linux. The desktop probe now locates installed SDKs as well as source checkouts;
four target object checks run in smoke and do not imply runtime qualification.
Window selection now keeps Wayland on Linux and selects the SDK Cocoa/Win32
backend on macOS/Windows. The same selection applies to the event adapter and
presenter. Renderer environment lookup uses the existing bounded host adapter;
search polling uses the SDK sleep API. Full editor objects compile for both
architectures on macOS and Windows in debug/release. The Windows SDK duplicate
`dyn_win_last_error` declaration is repaired in a content-addressed build-local
SDK copy. The same overlay unifies Darwin `__error` declarations without loader
calls after failed IO. Installed SDK files are never changed. The Windows ARM64
unwind limit exposed a large scratch-array initializer; static zero initialization
now avoids that generated stack frame. Bulk memory transfers keep the Linux
checked libc entry points, use libSystem's checked copies on macOS, and resolve
CRT functions once on Windows so LLVM cannot fold them into byte-loop helpers.
All object checks remain distinct from native linking and runtime qualification.

The Darwin service bridge has native adapters for spawn/process groups,
nonblocking transport, unreaped exit inspection, per-pipe SIGPIPE suppression,
kqueue one-shot readiness, vnode change delivery, PTYs, terminal layouts/raw mode,
suspend and frontend handoff. Disk watches register both parent directories and
actual document/config vnodes; replacement retires the old file vnode, and an
epoch sweep removes registrations for closed documents. A nonblocking event pipe
coalesces rescan requests while preserving the existing worker ownership/status
protocol. Registration failure retains explicit periodic fallback. Installation
policy consumes normalized stat/dirent values, uses descriptor-relative nofollow
checks and Darwin atomic exclusive/swap rename, and preserves version retention.
Intel bindings select Apple's `$INODE64` stat/directory entry points. Mappings use
Darwin resilient backing rather than a Linux signal-handler layout.

`scripts/native_macos.py` supplies the Cocoa support-library/editor build path,
including native SDK linking, explicit DNA exports and all text provider rpaths.
The language installer has Darwin cwd, symlink/readlink and descriptor-relative
nofollow tree removal adapters; its archive/timeout/hash commands use Homebrew
GNU tools. Native prerequisites are pkgconf, libvterm, Tree-sitter >=0.25, PCRE2,
utf8proc, HarfBuzz, FriBidi, FreeType, coreutils and gnu-tar, plus a supported
TrueType monospace font. `tests/native_macos.py` checks native header layouts,
full debug/release Cocoa startup/presentation/cleanup, process jobs, file changes,
notification rearm and PTY lifecycle. CI executes these checks on macOS, including native debug/release Cocoa builds.
Deterministic Darwin process/vnode mocks and both architecture object checks
also execute locally on Linux.

Windows adapters implement Job-owned processes, nonblocking pipe transport,
one-shot readiness, ConPTY, console input/handoff, directory notifications,
retained-directory filesystem access and recovery persistence. Managed plugins
publish immutable versions through an atomic current/previous record; language
packages use signed regular-file pointers to immutable directories. Nofollow
checks and private DACLs protect staging and cleanup. Directory fsync and terminal
suspend remain explicitly unsupported; recovery does not claim directory
power-loss durability.

`scripts/native_windows.py` builds the native DLL, Win32 editor and language
helper using MSYS2 UCRT64 providers. Runtime bundles capture the PE dependency
closure, language data and pinned Microsoft ConPTY DLL/host with licenses.
Language builds require the MSYS2 build tools. CI exercises native x64 services,
editor startup/relocation and installer workflows; Windows qualification remains
in progress while those gates expose failures. Both Windows architectures compile
in debug/release, but ARM64 currently has object proof only. Passing objects does
not imply a working native build.

Native thread lifecycle keeps pthreads on Linux and uses SDK desktop threads on
macOS/Windows, including OS TLS, self-join detection, callback results and arena
ownership through successful join. Failed joins retain ownership for retry.
`test_host.py threads` exercises condition handoff and repeated create/join in
debug/release; CI runs this on each native host. Four desktop object targets run
in smoke. Linux join-fault tests still cover transient recovery, persistent
retention, eventual reclamation and self-join rejection.

Large-file worker counts use per-platform APIs: Linux sched_getaffinity, Darwin
hw.activecpu via sysctlbyname, and Windows GetActiveProcessorCount across groups.
The Linux-only hard-coded syscall number is gone from portable buffer code.
The pinned SDK rejects duplicate foreign declarations of __error across its
thread module and the filesystem adapter. The adapter resolves that accessor
once through the process's libSystem, before any fallible libc call; a concurrent
mock test checks that initialization never clobbers an I/O error. The installed SDK itself
is unchanged; the build-local compatibility overlay is described above.

Files of 16 MiB and more are mapped read-only instead of read
(`files.read_mapped`), so unchanged text costs page cache, not private memory.
The block keeps the file descriptor and its platform stamp; saving copies
unchanged ranges through the filesystem adapter while the stamp holds, and
refuses to write mapped text once the file changed. Linux uses a native SIGBUS
guard (`src/native/dyn/mapping.dyn`) to replace truncated pages with zeroes until
the disk watcher reports the change. Saves never truncate the mapped file:
they write a temporary file and rename it.
After a successful replacement, origin metadata is refreshed for the inode
unlinked by that rename, only if its size and modification time still match.
This preserves repeated saves from the retained mapping without accepting an
external content change as a valid origin.

Loading validates UTF-8 and builds per-leaf newline tables on all CPUs
(`src/buffer/parallel.dyn`). Those workers are raw threads without libc thread
state, so they never allocate: one pass validates and counts, the main thread
allocates the tables, a second pass fills them.

Search prompts on documents of 16 MiB and more run on a worker
(`src/pattern/background.dyn`) over a `TextSnapshot`, a retained root that the
document may move past meanwhile; a stale result reruns. Repeats (n/N) use the
same windowed search and wait for it. Backward search walks windows back from
the cursor instead of rescanning from the top. PCRE2 gets bump-allocating memory
functions from the task's arena, so the worker never calls malloc.

Code outside `src/buffer` reads text only through `src/buffer/text.dyn`:
`byte_at`, `range`, `all`, `pointer` and `chunk_at`. A range inside one leaf is a
direct view; a range crossing leaves is copied once into a document-owned view.
Views stay valid until the next edit or `release_views`.
Large replacements can exhaust the byte budget sooner than small edits.
Saved and checkpoint views share the current text while unchanged. The first
mutation preserves one copy shared by both baselines. Saving inside an edit group
can make them diverge; only then does the editor preserve separate copies.
Checkpoints retain a synchronized mirror and update only the bounded changed span
plus a shifted suffix. A 128-revision change journal also bounds incremental LSP
diffs; missing revisions safely fall back to a full comparison. Subsequent edits
reuse that storage. Once saved and checkpointed, both views can
share current text again and unused snapshot pages are returned to the OS with
`MADV_DONTNEED`. Only full pages inside the written array bounds are discarded;
adjacent state and retained undo deltas remain intact. Hot storage stays resident
while editing. Baseline views are borrowed until mutation, save, or checkpoint.
Text, line-index, and undo storage also record their largest written prefixes.
Reloading a document already resets its undo history; after consuming the input
and rebuilding the new index, reload now returns unused full pages from those
old prefixes to the OS. Inputs may alias document storage because reclamation
happens after copying. Ordinary edits keep active storage and retained undo
deltas resident. Equal-length replacements with unchanged newline counts skip
rewriting the unaffected suffix of the line index; changed internal newline
positions are still rebuilt.
Dirty-state checks track prefix and suffix runs known to match the saved text.
Replacement, case changes, and undo/redo shrink these bounds before mutation;
saving or proving text equality resets them. Equal-length documents compare only
the potentially changed span, so typing and erasing a character does not scan an
entire large file just to update the modified indicator. Row identity checks
remain independent.

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

The file picker scans on one cancellable worker. Generations reject stale roots;
filesystem watches trigger debounced rescans, with a two-second fallback when
watch coverage is incomplete. Filtering cached rows stays on the UI thread.
Refresh preserves the selected filename. Scans retain the existing 2,048-file,
8,192-entry and 12-level bounds. Closing the picker cancels work; editor shutdown
joins the worker before releasing its storage.

Syntax worker buffers shrink after eight consecutive small completed revisions.
Alternating large/small updates retain warm capacity; failed shrink allocations
preserve the original owner and retry after another eight small revisions.

## Storage decision and performance checks

Contiguous storage up to 256 MiB was replaced by the piece tree. Edits no longer
move the text after the cursor, and saving streams leaf chunks. Measured with
`scripts/benchmark_workloads.py` (release, TUI), before and after:

| 100 MiB file | contiguous | piece tree |
|---|---|---|
| open | 71 ms | 74 ms |
| resident after open | 213 MiB | 115 MiB |
| insert, key to screen | 4.8 ms | 0.09 ms |

A 600 MiB file (previously refused) opens in 0.4 s at 635 MiB resident, inserts
in 0.09 ms and saves in 0.26 s.

With mapping and parallel loading, a 1 GiB file (17.9 million lines, btrfs, warm
page cache) shows its first frame in 0.08 s (0.26 s single-threaded) with 49 MiB
of private memory; the text itself is page cache. Each keystroke in its search
prompt answers in about 1 ms instead of 0.5 s, and a backward repeat over
millions of matches takes 0.01 s instead of more than a minute. Save cleanup
(trailing whitespace, final newline) edits the tree in place instead of copying
the text, so it no longer refuses files over 256 MiB.

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
