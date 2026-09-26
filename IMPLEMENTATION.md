# Dyn implementation and Helix compatibility

Requested scope: move DNA-owned native logic to Dyn, improve the supporting SDK
and compiler contracts, and complete the missing Helix editing behavior.
External libraries (SDL, Tree-sitter, PCRE2, libvterm, Fontconfig) remain dependencies.
Do not replace the user's explicit DNA shortcuts to imitate Helix defaults.

## Acceptance rules

- Every port retains the old adapter's error, cancellation, cleanup and bounded-memory behavior.
- Builds use scripts/compile.py; never run concurrent unbounded compiler/linker jobs.
- Edits validate the whole transaction before mutation; one undo restores all selections.
- Test UTF-8, reversed/overlapping selections, multiple cursors, counts, capacity and failure paths.
- Preserve existing working-copy changes. Use jj, no Git colocation.

## Work queue

- [x] Multi-selection ASCII case conversion, indentation, joining and open-line commands.
- [x] Primary selection rotation and content rotation.
- [x] Named registers and bounded macro recording/playback.
- [x] Syntax-node selections and query-backed language text objects (Dyn starter queries; other languages need queries).
- [ ] Binding-by-binding compatibility inventory and input-level behavior tests.
- [ ] Process/PTY API: working directory, environment, nonblocking transport, cancellation and child cleanup.
- [ ] Worker API: synchronization, bounded queues, wakeups, explicit ownership.
- [ ] Filesystem: directories, metadata, watching and atomic replacement contracts.
- [ ] Complete bindings used by terminal, syntax, font and event adapters.
- [x] Port theme/font and recovery adapters to Dyn.
- [ ] Port jobs/RPC/plugins, disk/search, syntax workers and terminal to Dyn.
- [ ] Compiler regression coverage for callbacks, C layouts, threading, cleanup and editor-sized builds.
- [ ] Ownership tests and documentation: borrowed views, transfer, double-close, lifetime violations.

## Compatibility source and intentional differences

Baseline: https://docs.helix-editor.com/keymap.html (checked 2026-09-27).
DNA retains Ctrl-X buffer-close, Ctrl-S save, Ctrl-O open, Space-T/t terminal,
its editable explorer, palette and popup layout decisions. These are intentional
product choices, not claims of identical default keymaps. Full compatibility is
not yet implemented. Selection capacity is currently 32; case conversion is ASCII.

## Validation record

Update this file as tasks land; a checked item requires tests and clear limits.

### Completed batch (2026-09-27)

- Batch edits merge overlaps, preflight capacity, preserve primary identity/direction,
  and undo as one operation. Open-line counts and primary/content rotation added.
  ASCII case conversion edits in place and retains split marks through undo.
- Fontconfig lookup/listing and palette state moved from C to
  `src/native/dyn/`. Dyn exports retain the C ABI; object files link into the
  existing native library. No new runtime library dependency is required.
- C-ABI tests cover palette bounds, reset/generation, font discovery, tiny buffers,
  null pointers and ownership cleanup. Build and packaging retain bounded jobs.
- Dyn shared-library tracing, Windows DLL startup and mutable-global initialization:
  PR27, based on panic cleanup PR26.
- Dyn process child working directory, `process.take`, Windows empty-environment
  fix and runtime-check diagnostics: PR28, based on PR27. Linux regression suite
  and Windows/macOS host tests pass.
- DNA module suites pass debug/release. Full smoke passed before final direction/
  count refinements; module and native input/workflow suites passed after them.
- Package archive determinism, extracted checksums and relocated headless startup
  on the current host pass. Container execution
  was not requested for that check; it does not prove another OS is supported.

Remaining items above are still open. Core synchronization and Linux filesystem
APIs already exist in Dyn: audit and extend their contracts rather than creating
parallel APIs. PTY support, process groups/cancellation and an event loop remain
required before porting jobs, LSP transport and terminals.

### Preview 8 batch (2026-09-27)

- Published preview.8 after Linux/Windows/macOS compiler, native and package
  validation. DNA pins platform checksums in mise.toml; local mise uses preview.8.
- Named a-z text registers retain multi-selection fragments with lazy allocation.
- Named/default macros record UTF-8 input, reject overflow and recursive playback,
  cap replay work, and use the normal edit/undo path. Input tests cover recording,
  replay, named slots, undo and recording overflow. REC appears in the status line.
- Fixed R leaving the character-input prefix pending after replacing a selection.
- Added gy/gi and command equivalents for LSP type-definition/implementation.
- Added nonblocking revision-checked syntax parent/child/sibling selections.
  Added bounded worker-side text-object queries, atomic multi-selection application,
  and bundled Dyn queries. Full Helix parity and more language queries remain open.
- Ported recovery worker to Dyn with SDL synchronization/threads and libc filesystem
  bindings. Preserved coalescing, private permissions, fsync/rename ordering,
  worker-owned snapshots, cancellation/join and cleanup. Fault/crash tests pass.
- Recovery port remains Linux-specific, matching DNA's current platform support.

- Selection normalization: Alt-minus merges all, Alt-underscore merges touching/
  overlapping ranges, Alt-colon makes all ranges forward; underscore trims every
  selection. Input tests include reversed primary selections, overlap and gaps.
- Full preview.8 smoke passed before the last query/macro scheduling refinements;
  final debug/release workflow, syntax queries, lifecycle/performance and extracted
  package checks cover the refinements. All builds retain the 2 GiB guard.

### Compatibility inventory: remaining families

Baseline remains the official Helix keymap linked above. Implemented behavior is
not a claim of complete parity. Remaining families to audit/implement:

| Family | Remaining gaps |
| --- | --- |
| Registers/macros | Special/search registers, append registers, text/macro interchange, last-insert repeat |
| Selection | Alignment &, Alt-J selected join spaces, Alt-x shrink-to-lines |
| Syntax | All-siblings/all-children, parent boundary motions, more language text-object queries |
| View/jumps | z/Z view commands, jump-list traversal, screen-relative goto commands |
| Changes | Numeric increment/decrement, comment toggling, per-selection shell filtering |
| Search | Search-selection * and Alt-*, register-aware search |
| Navigation | Bracket-prefixed navigation, repeat-last-motion, alternate/last-modified locations |
| Modes | Complete Vim profile and per-binding cross-profile tests |

DNA intentionally retains Ctrl-X buffer close, Ctrl-S save, Ctrl-O open,
Space-t terminal and its own explorer/picker decisions. K/Alt-K now filter
selections; hover moved to Space-k and remains available through :hover.

- Added K/Alt-K regex selection filters with preview, cancellation and reverse-range
  preservation. Space-k opens hover/diagnostics. Added corresponding menu hints.
- Delete/change now refuse to erase when the preceding yank fails. Regression
  uses overlapping selections whose combined clipboard text exceeds capacity.
- Startup measurement (dummy display, guarded dyn run src/ --timings): 0.40–0.42 s
  to first frame. Final pre-filter performance run: 4.62 ms input mean, 6.20 ms max;
  60 lifecycle cycles retained descriptor/thread counts with 8192 bytes RSS growth.

Final validation for this batch: `mise exec -- just smoke` and
`mise exec -- python3 tests/package.py` both passed on preview.8, including all
module tests in debug/release, actual input handlers, real/fake LSP, syntax and
text-object queries, recovery fault injection, lifecycle/latency and extracted
package startup. Logs: /tmp/dna-preview8-final-smoke.log and
/tmp/dna-preview8-final-package.log. No container run was requested.

## Operation overhead pass

- UI text layouts use a bounded cache; unchanged status/gutter/picker labels avoid
  repeated text resets. Font changes invalidate cached handles.
- Hidden terminals keep draining; redraw only visible output. Duplicate/hidden
  diagnostics and log-only LSP messages do not request frames.
- Worker invalidations combine with already queued input. Geometry-sensitive
  config/macro changes and pointer events retain paint barriers.
- LSP receive and recovery encode arenas reuse up to 2 MiB; larger requests drop
  storage afterward. Retained LSP results take ownership before reuse. Recovery
  workers reuse completed small snapshot buffers without sharing mutable bytes.
- UI waits follow deadlines and readiness notifications instead of fixed 500 ms
  polling. Native filesystem polling was addressed in the follow-up pass below.
- Render traces include operation wall/main-thread/process CPU, wakeups, selected
  arena lifetimes/capacity, recovery copies, and UI text-cache activity. They are
  not a complete heap profiler or per-worker CPU attribution system.


Implemented the follow-up maintenance pass while preserving full-screen immediate
mode rendering:
- Parent-directory inotify with control-pipe wakeups, bounded fallback/reconciliation.
- Document/native allocation accounting, Tree-sitter allocation hooks, opaque text-object counts.
- Revision-aware dirty comparisons; independent explorer identity validation.
- Two inactive syntax parsers; closed-pane text-cache release.
- Document ownership module and subsystem-specific shutdown helpers.
- Shared palette/alias/leader command metadata.
- Test-only editor smoke harness; production startup probe kept small.
- Real Wayland profiling and extended resource/editing soak targets.

Whole-document work still required by current storage/protocol contracts includes
undo checkpoints, full LSP synchronization, worker syntax snapshot ownership, and
session serialization. This pass removes repeated unchanged dirty comparisons;
it does not claim those copies vanished or that driver/GPU memory is fully tracked.


Local validation for this pass:
- Full debug/release `just smoke`, relocated deterministic package, and `just soak` passed.
- 20 workflow rounds (240 file/search/edit cycles): 92 KiB post-warmup growth in the first extended run.
- 300 native lifecycles: 12 KiB RSS growth; descriptors/threads stable; all tracked native allocations freed.
- Idle file-stat regression: old worker 4 calls / 1.1 seconds, new worker 0; fallback and parent replacement tested.
- 1 MB clean document, 2,000 dirty checks: release 26.2 ms uncached versus 0.14 ms cached.
- Real Wayland + installed JSON parser replay: 0.29 ms mean input-to-SDL-present, 1.41 ms maximum in one local run.
- Complete desktop trace: build/profiles/cleanup-real-desktop-1790602099849933327.jsonl and matching .txt report.
- Production binary: 840,736 to 666,592 bytes; main reduced to 193 lines. Measurements are machine/workload-specific.

The workflow replay now quits through the normal editor path, allowing trace
summaries and resource teardown to run. Pixel-capture subprocesses also shut down
normally and do not reuse the main replay's trace filename.

Configuration reload now uses directory notifications too, retaining a one-second
fallback and 30-second reconciliation. Debug/release tests verify that a real
config write wakes a 30-second wait and redraws, and parent replacement is covered.


Further profiling found UI text-cache collision churn. A stationary file picker
performed 660 text updates over 30 frames even though its labels fit the 128-entry
budget. Replacing four-entry buckets with collision chains and global LRU reduced
that workload to zero text updates without increasing text storage or layout count.
The regression exercises a real picker populated from an 80-file temporary project.

Paired local Wayland/real-JSON-parser workflow: UI updates 30,408 -> 2,981; mean
full-frame draw/present wall time 0.595 -> 0.541 ms. Asynchronous frame counts differ;
these are local observations, not fixed timing guarantees. Reports:
`build/profiles/cache-before-1790602922764670412.txt` and matching `cache-after` file.

Combined split/search/terminal profiling exposed a benchmark ownership bug: the
harness freed an editor-owned terminal before asking the editor to quit. This
segfaulted the unchanged binary too. Normal UI shutdown now owns terminal cleanup,
and the combined workload is included in `just smoke`. Complete combined trace:
`build/profiles/cache-combined-fixed-1790603190679451323.txt`; all tracked native
objects and arena reservations returned to zero. Terminal main-thread polling
used about 1 ms CPU across that replay; syntax initialization/updates remained a
larger service cost. GPU allocation sizes remain opaque.

Syntax follow-up isolated disposal as the dominant service cost during buffer
switching: a native-call probe measured 12.8 ms closing parsers, 3.6 ms opening
them, and 0.7 ms submitting updates. Cache eviction now transfers ownership to a
single background disposer. A full slot rejects further retirement without
transferring ownership; later completion wakes the editor to retry. Explicit
buffer close remains synchronous, and shutdown joins all outstanding disposal.

Paired local Wayland/real-JSON-parser replay: main-thread syntax wall time
28.228 -> 6.209 ms, worst call 2.045 -> 0.412 ms. Tracked syntax-adapter peak
15,766,368 -> 17,876,064 bytes, reflecting the one extra retiring parser. All
tracked native allocations and document arenas returned to zero. Whole-process
CPU time was 976 -> 1,031 ms in those runs: this moves cleanup off the UI thread,
not eliminates cleanup work. Frame counts and worker scheduling differ. Reports:
`build/profiles/syntax-retire-before.txt` and `build/profiles/syntax-retire-after.txt`.

The retirement regression deliberately blocks real disposal, verifies that
collection and a second retirement return without blocking, checks ownership on
rejection, then drains and checks allocation balance. Resource cycling exercises
both synchronous and asynchronous teardown. A 20-round real desktop replay
opened 240 files; RSS grew 4,400 KiB after the first round.

Language UI now anchors hover, cursor diagnostics, signature help, and completion
to the active pane's cursor. Popups flip above the cursor and clamp to pane bounds;
long hover text scrolls with arrows. Completion defaults to enabled, keeps insert
input active, and accepts with Enter or Tab. Cursor-mismatched hover/signature
responses are discarded. The real Dyn LSP UI regression waits for automatic
completion without setting the completion option, accepts a function call with
Tab, and verifies symbol-hover rendering near the cursor.

`:x`/`:wq` saves and closes the active buffer; `:wa` saves modified file buffers;
`:xa` saves before normal editor exit. Save-all advances one buffer at a time,
including asynchronous format-on-save and Save As prompts. Cancellation, failed
destinations, and formatter failures stop the sequence without closing unsaved
buffers. Explorer operations retain their separate preview/apply requirement.
Debug/release workflow tests cover these cases and verify saved bytes on disk.
Full smoke, the real LSP popup test, interrupted-save tests, and relocated package
validation passed. Local screenshots are in `build/language-hover.png`.

Completion follow-up: the original UI probe entered insert mode over a preloaded
prefix and capped waits at 50 ms. It now sends actual key/text events and honors
the editor's deadlines. Variants cover typing after LSP startup, platform.dyn,
the example config, animation reaching its visible state, and guarded `dyn run
src`. The example config incorrectly retained `automatic_completion = false`;
that reproduced missing automatic completion and is corrected. This does not
explain the user's remaining report with the live setting enabled. Fresh local
headless and Wayland tests pass, including the actual platform source path.

The LSP log no longer retains a generic pending message after completion returns:
it identifies automatic requests, result counts, and popup activation. Debug and
release smoke coverage asserts the response status. Awaiting the affected
session's new status to distinguish a pending request from an invisible popup;
the reported live-session failure is not yet confirmed fixed.


Stale-completion follow-up: the affected session reported "Discarded stale
language response; request again." A deterministic native workflow regression
reproduced a lost retry when a temporary panel interrupted a completion request:
`mise exec -- python3 scripts/smoke.py` failed with "completion must resume after
interrupted response" before the fix. Non-completion panels now rearm the timer,
and discarded automatic responses invalidate their consumed scheduling identity.
The background loop consumes replies before scheduling the next completion.
While a request is pending, its expired debounce deadline no longer forces a
zero-wait CPU loop. Stale document/cursor/mode/buffer checks remain enforced;
logs now identify the specific failed check.

Debug/release workflows pass with regressions for panel interruption, editing
while a response is pending, rejecting the old document, retrying the current
revision, and avoiding the pending-request busy loop. Real Dyn completion/Tab/
hover and `dyn run src` platform.dyn typing tests pass. Idle CPU measured 0.29%
of one core, with no unnecessary redraws. These fixes cover reproduced scheduler
faults; the screenshot alone cannot identify which stale check fired in the
user's session, including whether leaving insert mode to inspect the log caused
that final rejection. Live-session resolution still needs confirmation.

Completion latency and snippets: lowered the default typing debounce from 200 ms
to 80 ms. The same SDL replay in platform.dyn measured 349/353/358 ms before and
223/228/231 ms after (final keystroke to first popup text draw, not compositor
presentation). The UI probe now records that latency. Results are prefix-filtered
before the 128-item cap, so later matching snippets are not hidden by unrelated
symbols. Ordinary completion acceptance uses a single validated buffer edit and
releases the response arena, avoiding the former 24 MiB workspace-edit staging
arena and whole-document transformation. Additional edits retain preview/apply.

DNA now advertises LSP snippet support and owns a bounded snippet session: numeric
tabstops, nested defaults, linked leaf placeholders, Unicode replacement/deletion,
Tab/Shift-Tab navigation, and final $0. Escape cancels the session; revision and
buffer-identity checks invalidate stale sessions. Explicit stops are limited to
31, nesting to 16. Variables, choices, transforms, repeated defaults, and mirrors
of nested placeholders are rejected before editing; custom snippet files are not
implemented. Previewed additional edits remap the snippet's insertion position.
No server-owned pointers or per-keystroke snippet heap allocations are retained.

Debug/release unit and native workflows cover snippet parsing, mirrors, adjacent
empty stops, nested replacement, undo invalidation, additional-edit previews,
Unicode, and a matching snippet after 140 irrelevant results. The real installed
Dyn server passes the GUI replay for function-argument snippets, ordinary
completion and hover, and guarded dyn run src. Idle CPU remains 0.28% of one core,
with no unnecessary redraws or retained tracked allocations in the idle probe.

Full-project follow-up found that the isolated fixture hid Dyn server work: the
real src/platform/platform.dyn initially took 1244–1315 ms, including after a
three-second startup wait. Compiler changes in the sibling dyn/compiler checkout
now refresh syntax and serve one queued completion before semantic diagnostics
(without starving diagnostics), and skip synthetic local-scope semantic rebuilds
outside functions. Both faults have failing-before/passing-after regressions;
all 54 compiler LSP contracts pass, including updated syntax context after edits.
Full-project popup latency is now 230–250 ms, including guarded dyn run src with
the actual source path. The local, gitignored .mise.local.toml sets DNA_DYN_LSP to
the rebuilt sibling compiler's dyn-release lsp command. The installed preview is
unchanged; the compiler fixes must be published for other users to get them.
The override only affects the built-in Dyn server; explicit language configuration
wins. Final native debug/release workflows and real Dyn argument-snippet replay
pass. Dyn's built-in function template also returns real newline/tab characters,
which the snippet parser accepts, rather than literal escaped control text.

## Native implementation in Dyn

All ten remaining DNA-owned native C modules have Dyn implementations in
`src/native/dyn/`. Shared, static GUI and static terminal libraries now contain
Dyn objects. The 25 behavioral C test programs/interposers are Dyn modules under
`tests/native/`; the two header assertion programs are consolidated into
`tests/native_abi.py`. That script generates a temporary external-header probe
and compares its results with the actual Dyn layouts. No maintained `.c` or `.h`
files remain under `src/` or `tests/`.

The migration preserves the public `dna_*` ABI, result generations, allocation
categories, worker ownership, filesystem transactions and frontend handoff.
Pthread-backed Dyn wrappers intentionally retain libc TLS setup; the current
raw-clone `std/thread` API does not provide that setup. External SDL, Tree-sitter,
libvterm, PCRE2 and other dependencies retain their original languages.

The SDK is pinned to the tested Dyn 0.1.0-preview.14 release. Native builds check
Linux x86-64 structure layouts, callback records, constants and libvterm bitfields
before linking. Shared native libraries reject unresolved symbols. Runtime
`memcpy`, `memmove` and `memset` stay hidden in both the production library and
native test probes, preserving the host libraries' optimized implementations.

Migration-specific corrections include explicit modulo-2^64 disk hashing,
zero-predicate query handling, synchronized monotonic-clock initialization,
full-screen terminal clipboard capacity including row separators, and avoiding
a one-past array reference when the terminal output queue becomes empty. Native
first-use initialization also establishes descriptor sentinels and libvterm
callbacks for static archives, because the pinned SDK does not run executable
`.init_array` constructors. Shared and static callers use the same public ABI.


Validation after migration: `just smoke` passes all module suites in debug and
release, native ABI and allocation checks, GUI/TUI behavior, filesystem and
process faults, rendering, relocation, and minimal/terminal profiles. A matched
release input probe on the same 50 KB fixture measured C baseline typing/movement
means of 0.93/0.92 ms and Dyn means of 0.92/0.90 ms using SDL's dummy driver.
These are input-to-present CPU measurements, not display latency.

Final `just soak` passes the 20-round workflow, 300 native lifecycle cycles,
redraw-idle and disk-idle checks. Lifecycle descriptor/thread counts remain
unchanged, with 8,192 bytes RSS growth. GUI input fuzz passes three seeds of 500
events each in both debug and release; terminal fuzz passes two seeds of 200
chunks each. Logs are saved as `build/migration-final-*.log`. The standalone
`./dna` executable was rebuilt with `--no-cache` and checked for GUI startup and
PTY input.

The combined-terminal plus real-syntax stress variant originally exceeded its
RSS gate with both the saved C library and the Dyn library. Follow-up profiling
isolated five fixed 16 MiB syntax buffers per worker. All allocations were
released, but allocator retention kept RSS high. Syntax buffers now grow
geometrically with the document, retain capacity while their worker is alive,
and release storage at teardown. The existing file limit and RSS gates remain
unchanged. The same two-round workflow's final RSS fell from 232,856 KiB to
57,516 KiB. A 42 KB JSON fixture's tracked syntax peak fell from 83,898,600 bytes
to 340,264 bytes. The real-syntax workflow now runs in `just smoke` and `just soak`.

Regression checks cover completed growth across capacity boundaries, shrinking
to empty/UTF-8 text, comparison against fresh parser results, all five buffer
allocation failures with same-revision retries, stale result rejection, and
close/retire with queued parsing. Lifecycle tests require a real JSON grammar;
they no longer silently skip syntax when the fixture is unavailable.
The bounded-retirement probe exports its blocking callback from a shared
library, since the current SDK hides executable functions from interposition.
It checks that callback visibility before waiting, so SDK changes fail clearly.

Wayland measurements on this machine found release input-to-present typing
mean/max of 0.26/0.97 ms on 50 KB and 0.30/0.90 ms on 5.28 MB (110,000 lines).
Input frames disable vsync, so these measurements end at `SDL_RenderPresent`
return and do not include physical keyboard, compositor or display scanout.
Actual Dyn completion took 152–212 ms in the exercised cases. A timestamped
212 ms sample comprised the configured 50 ms debounce, 158 ms in the external
Dyn language server, and about 4 ms remaining editor/transport/render time.
These results identify the language server as the next completion bottleneck;
they do not establish a physical key-to-visible-frame latency guarantee.

Final follow-up validation passes the full `just smoke`, four rounds of the
combined real-syntax/terminal workflow (48 file cycles), 300 native lifecycles,
three release completion-fuzz seeds of 700 events, and two TUI fuzz seeds of
300 chunks. The longer workflow ended at 57,548 KiB RSS, with 2,304 KiB growth
after the first pass and input-to-present mean/max of 4.213/6.590 ms. Lifecycle
thread/descriptor counts stayed unchanged; tracked allocations balanced in all
five native categories. Logs are `build/performance-final-*.log`.

### Local editor comparison (2026-10-04)

The comparison used an AMD Ryzen 9 9950X, Neovim 0.12.5, Helix 25.07.1,
Neovide 0.16.2, and the pinned Dyn SDK. Results describe these workloads on this
machine, not a universal editor ranking.

`scripts/benchmark_editors.py` creates isolated configurations and twelve identical
plain-text fixtures per editor. Recovery/swap and language servers are disabled.
All three terminal editors use a 120×32 PTY and the same libvterm screen decoder.
Every measured edit, deletion, jump, or switch waits for the expected changed
screen content. The endpoint includes PTY transport and terminal decoding, but
excludes a desktop terminal renderer and physical display. Filesystem caches are
warm. Editor order rotates over three repeats. Each editor contributes 15 startup,
180 insertion, 180 backspace, 120 jump, and 105 file-switch samples per fixture size.
Memory includes descendants and uses proportional set size (PSS) to apportion
shared pages. It is measured after three passes over twelve open files.

For the 49,941-byte fixture, times below are median / p95 / maximum in milliseconds:

| Operation | DNA | Neovim | Helix |
| --- | --- | --- | --- |
| Startup to file content | 2.932 / 3.414 / 3.414 | 8.766 / 10.270 / 10.270 | 10.897 / 12.038 / 12.038 |
| Insert one character | 0.125 / 0.192 / 0.295 | 0.305 / 0.453 / 0.621 | 0.454 / 0.539 / 0.667 |
| Backspace | 0.145 / 0.212 / 0.293 | 0.312 / 0.466 / 0.621 | 0.465 / 0.561 / 0.641 |
| Jump to file boundary | 0.139 / 0.232 / 0.261 | 0.294 / 0.534 / 0.626 | 0.848 / 1.234 / 1.440 |
| Switch file | 0.206 / 0.449 / 0.576 | 0.612 / 1.835 / 1.987 | 1.386 / 7.924 / 9.419 |
| Retained PSS, MiB | 15.12 | 14.82 | 17.81 |

For the 5,279,949-byte fixture:

| Operation | DNA | Neovim | Helix |
| --- | --- | --- | --- |
| Startup to file content | 5.269 / 6.649 / 6.649 | 12.228 / 13.688 / 13.688 | 13.343 / 17.735 / 17.735 |
| Insert one character | 0.327 / 0.416 / 2.450 | 0.259 / 0.436 / 0.494 | 0.320 / 0.514 / 0.682 |
| Backspace | 0.461 / 0.609 / 0.678 | 0.276 / 0.454 / 0.518 | 0.335 / 0.531 / 0.597 |
| Jump to file boundary | 0.161 / 0.253 / 0.340 | 0.297 / 0.514 / 0.583 | 0.804 / 1.222 / 1.241 |
| Switch file | 0.197 / 3.048 / 3.343 | 0.636 / 5.323 / 5.616 | 2.086 / 9.594 / 12.129 |
| Retained PSS, MiB | 99.18 | 84.95 | 86.93 |

The comparison exposed eager saved/checkpoint copies in untouched DNA documents.
Lazy materialization reduced the large-workload PSS from 210.05 to 99.18 MiB
(53% reduction). Median startup fell from 8.097 to 5.269 ms in the repeated local
runs. The tradeoff is a first-edit copy: maximum insertion increased from 0.672
to 2.450 ms, while median/p95 insertion remained about 0.33/0.42 ms. Large-file
backspace still costs more than Neovim/Helix in this test. The contiguous buffer
continues to move the suffix; these results do not justify replacing the entire
storage architecture. A DNA-only 128 MiB PSS gate for this twelve-file workload
now runs in `just smoke`.

`scripts/compare_completion.py` uses the same saved Dyn fixture, typed `h`, server
binary, and actual `helper_unique` popup acknowledgement. It records protocol
request/response timestamps through a transparent proxy. Each editor runs three
fresh editor/server sessions, with one first completion and ten warm completions
per session. Filesystem/compiler caches are not cleared: “first” is not a
cold-disk compiler benchmark. Neovim uses built-in LSP autotrigger without a
completion plugin. Scheduling policies remain native; Helix trigger characters
can bypass its ordinary completion timeout.

| Warm popup latency, ms | Median | p95 | Maximum |
| --- | --- | --- | --- |
| DNA, new default | 26.711 | 27.767 | 27.950 |
| Neovim | 26.693 | 27.760 | 27.948 |
| Helix | 7.787 | 8.002 | 8.897 |

DNA's earlier 50 ms default measured 52.072 ms median in the baseline run.
The default is now 25 ms, with a configurable 10–2000 ms range. Explicit values,
including 50 ms, remain unchanged. In this warm workload server time is roughly
0.5–0.6 ms, so scheduling dominates; the earlier 158 ms server sample is not
representative of every completion. The change preserves pending-request,
cancellation, and document-sync behavior.

`scripts/benchmark_gui.py` launches DNA and Neovide sequentially under an isolated
headless Gamescope compositor, using the same GPU, 1100×760 windows and a
52,800-byte plain-text file. Five measured runs alternate order after excluded
warmups. Median launch to the observer seeing the first non-null toplevel buffer
commit was 153.30 ms for DNA and 186.84 ms for Neovide (maxima 156.55/193.60 ms).
Median idle process-tree PSS after two seconds was 100.37/118.21 MiB. Neovide's
Neovim child is included. Driver allocations and the compositor process are not.
This endpoint may precede actual file content; it includes Wayland logging and
observer overhead and is neither GUI typing latency nor physical presentation.
It must not be compared directly with the terminal startup figures above.

Reproduce after building the standalone `./dna` and installing the comparison
editors (Gamescope is required only for the GUI comparison):

```sh
mise exec -- python3 scripts/benchmark_editors.py --output build/comparison-small.json
mise exec -- python3 scripts/benchmark_editors.py --bytes 5280000 --output build/comparison-large.json
mise exec -- python3 scripts/compare_completion.py --output build/comparison-completion
mise exec -- python3 scripts/benchmark_gui.py --output build/comparison-gui/results.json
```

Raw retained evidence is in `build/comparison-small-final.json`,
`build/comparison-large-final.json`, `build/comparison-large-before.json`,
`build/comparison-completion-after/`, and `build/comparison-gui-final/`.

Validation also exposed a terminal-exit race: PTY hangup could arrive before
`waitpid` could reap the child, leaving the editor asleep without another event.
Terminals now watch a child pidfd independently, release it on reap/close, and
fall back to 16 ms polling after hangup if pidfd creation is unavailable.
The notification regression closes all child terminal descriptors before a
delayed exit and requires an event-driven wake, with no timer polling to hide
the race. Private boundary coverage checks the unavailable-pidfd fallback.
