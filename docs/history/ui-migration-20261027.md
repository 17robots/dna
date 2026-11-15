# Shared UI migration and friction log, 2026-10-27

## Delivered boundary

DNA's keyed UI now uses persistent `std/ui/box` builders for identity lookup,
duplicate-key derivation, recycled storage, owned frame text, clipped hit-testing
and geometry. The private key hash/linear lookup and fixed 32 KiB label buffer
are removed. Panel layout operates directly on the cached shared boxes rather
than allocating a temporary array of geometry nodes for every panel.

DNA retains bounded integer handles for application colors, values and its
configurable selection/scroll tweens, plus its existing SDL custom drawing.
Those records refer to shared boxes; they no longer implement another keyed UI
cache. The SDL text-object cache remains renderer-specific until text rendering
moves to the native backend. Shared owners and frame text are released with
editor state; release followed by rebuilding creates fresh widget identities.

The font bridge replaces direct Fontconfig use with `std/font/system`, retaining
the existing native C ABI and SDL/TTF. Collections and CFF faces remain
unsupported; exact family misses stay explicit.

## Friction resolved

1. The standard box API only exposed an end call that also rendered. The compiler
   now provides separate layout and render operations, allowing DNA's custom SDL
   renderer and document/terminal drawing to remain.
2. DNA panels use physical container padding, screen-absolute floating boxes and
   a filler-first shrink rule to keep footers visible. Standard boxes now support
   padding, per-axis absolute positioning and opt-in greedy shrinking. Cross-axis
   fill policy stays in DNA's adapter.
3. The preview.28 candidate retains preview.27's pointer-handle, chained-arena
   API. DNA explicitly creates arenas and clears released handles. Its bounded
   owner adapter accounts for the SDK header while preserving requested payload
   capacity; the previous value-owner compatibility mapping is removed.
4. Removed public C-string helpers are replaced by a small DNA bounded conversion
   module. Invalid input and insufficient capacity preserve destination bytes.
   Standalone examples and the installer use the SDK pointer-handle API directly.
5. Review found that copying every box touched in a frame erased previous panels
   when only the current root was solved. Both bridge loops now restrict work to
   descendants of the current root. A two-panel same-frame regression proves
   geometry and hit regions survive.

6. The remaining private keyed pool and hover lookup duplicated standard UI
   state. Shared boxes now carry an application handle in `user_data`, with
   `find`, explicit byte identities and portable numeric identities supplied by
   std. Only the application's metadata handle slots remain bounded at 511.
   Current-frame lookup hides omitted keys; recycled identities clear old state.
7. Independent roots share one cached tree. Subtree layout temporarily isolates
   the current panel's sibling link and restores it afterward, so relaying out
   an earlier panel preserves later geometry and input. Frame text is owned by
   a resettable arena and stays valid across every panel layout in that frame.

## Evidence

All commands below used `DYN=../dyn/compiler/build/dyn-release`, the existing
shared native dependencies under `build/deps/install/lib`, and isolated test
configuration. No SDK or application release was published.

- Production `src` check and debug/release executable builds passed.
- The cache oracle covers identity/tween retention, stable duplicate keys,
  expired state clearing, clipped input, multiple panels, earlier-panel relayout,
  40,000-byte owned labels, 96 frames of key churn with bounded persistent storage,
  release/rebuild and repeated release. Full production workflows pass in both
  debug and release after the migration.
- `scripts/build_smoke.py` and `scripts/smoke.py` passed in debug and release.
  The native workflow covers dialogs, popups, explorer, pickers, editing and
  saving through the SDL dummy display. The added production geometry oracle
  checks panel position, padded text, flexible lists retaining footers, scroll
  rows, repeated names, clipping and multiple independent panels.
- `scripts/test.py` passed all ten core suites in debug and release.
- `scripts/test_host.py` and `scripts/test_host.py filesystem` passed both modes.
  `tests/host_environment.py` passes its Windows wrapper oracle and checks the
  actual host module for both macOS and Windows architectures. This caught and
  corrected shared helper imports that initially existed only in Linux source.
- `tests/owned_arena.py` passed debug/release and six desktop target builds.
  Available ARM64/RISC-V64 emulators and Wine executed the checks, including
  a 2.5 MB payload that exercises Windows commitment beyond the initial region.
- `tests/save_failures.py`, `tests/document_memory.py` and
  `tests/json_scratch.py` passed. Existing document memory/reclamation budgets
  remain satisfied; measurements are in `build/document-snapshot-memory.json`.
- `tests/redraw_idle.py` reported zero unnecessary pointer redraws.
  `tests/render_trace.py` matched twelve SDL presents in debug and release.
- The language installer builds with value arenas and bounded command strings.
  The adjacent native font test and full dependency build passed separately.

Build artifacts include `build/dna-{debug,release}`,
`build/dna-smoke-{debug,release}`, `build/editor-smoke` and the individual
`build/test-*` stages. This is focused qualification, not a fresh uninterrupted
`just smoke` run or native macOS/Windows application qualification. Full Windows
DNA checking still encounters existing target-specific syscalls in the buffer
module; the compatibility owner itself cross-builds and runs under Wine.

## Remaining order

Shared widget parity, font discovery and persistent keyed-state migration are
implemented. Replace native window and text backends one platform at a time.
The shared window layer now supplies opt-in ordered key/text events, repeat and
modifier information, explicit overflow and worker wake-ups. The shared layer now also provides basic preedit/candidate placement and owned
ordered clipboard replies. DNA still needs those APIs integrated with its
renderer, surrounding-text corrections and real IME qualification before its
SDL event loop can switch. The window README
records source commit bounds and platform qualification; Cocoa native runtime
behavior remains unqualified locally. Keep document, terminal and preview
drawing specialized.

## IME and clipboard follow-up

The shared window layer retains exact composition snapshots and clipboard
chunks in its ordered queue. Text fields keep preedit separate from document
storage, preview selected replacement, and suppress IME-consumed editing and
submission keys, including the final cancellation poll. Candidate placement is
computed after layout. Production XIM callbacks and C ABI checks, Wayland
protocol mocks, Wine IMM probes, native window/rendering regressions and the
22-fixture native-host runner pass. DNA's existing production workflow smoke
still passes debug/release against this SDK (`build/ui-ime-smoke.log`).

These are protocol/callback checks, not real ibus/fcitx or native Windows/macOS
IME sessions. Later surrounding-text and native-profile work is recorded below.
The default DNA build continues to use SDL/SDL_ttf.

## Optional native Linux profile

`scripts/build_native.py` stages the production editor with replacements from
`modules/native`, leaving the SDL build and all editor data intact. It builds
an isolated native library, window/event adapter, software drawing backend and
OpenGL framebuffer presenter. Text uses HarfBuzz/FriBidi through `vendor/text/layout`, with owned UTF-8
text, cached glyph bitmaps, source byte ranges, point lookup, wrapping and
grapheme-level fallback faces. TrueType rasterization uses `std/font`; FreeType
handles scalable CFF and collection faces that the core parser rejects. Terminal drawing calls the same backend through a validated
callback table; native text memory accounting remains balanced. Worker wake
callbacks are installed and removed under the notification mutex before window
closure. The builder audits transitive dependencies and rejects SDL linkage.

Build with `DYN=../dyn/compiler/build/dyn-release python3 scripts/build_native.py`
(add `--release` for optimized builds). Run `build/dna-native-debug` or
`build/dna-native-release`. Native builds use the existing native development
packages and language installer under `build/deps/install`; they do not rebuild
or replace that installation. Delete `build/native-gui` and native binaries to
remove this development profile. Continue using the existing SDL binary for
rollback.

For the production workflow oracle, add `--smoke` when building, then run
`DNA_SMOKE_BACKEND=native scripts/smoke.py` with matching `DNA_SMOKE_MODES`.
Actual window resizes require a display whose window manager permits them;
the local smoke runs use an isolated rootful Xwayland display rather than the
user's tiling window manager. `tests/native_text.py` covers owned text, metrics,
Unicode source ranges, wrapping, fallback invalidation and callback accounting.
`tests/native_platform.py` covers rendering pixels, clipping, alpha composition,
text-mask scaling, events, keymap translation and renderer recreation.

This profile currently targets Linux X11. It is not the default migration for
macOS, Windows or Wayland. HarfBuzz shaping and paragraph bidi are integrated, including contextual
joining across fallback fonts. CFF/TTC rasterization is available through
FreeType. Color bitmap/vector glyph formats remain unsupported. AltGr/keymap
group state is not yet represented in portable ordered key events. Surrounding
corrections stay unavailable on X11 because of the verified XIM transport
limitations; Windows now supports IMM document feed and selected-range
reconversion in the shared SDK. Real engine sessions and native macOS/Windows
application qualification remain pending. These limitations prevent removing
SDL as the default backend.

Native migration exposed the old 64 KiB shared X11 clipboard bound. The SDK now
uses checked owned snapshots up to 16 MiB with ICCCM INCR transport. The adapter
requests complete snapshots without filling the bounded Clipboard event queue,
keeps unrelated input ordered, returns independently owned C-string results and
frees each result explicitly. Oversized/malformed offers fail before ownership
changes; failed receives retain the previous completed snapshot and report an
error. Production smoke includes a 1.2 MB multi-selection yank/delete.

Final local qualification passed native debug/release production workflows,
native pixel/input/clipboard ownership oracles, text fixtures and seven desktop
text object targets. Production native debug/release binaries pass the transitive
SDL dependency audit. The original SDL debug/release workflow smoke also passes.
Logs are retained under `build/native-editor-qualification/`. The SDK changes are
committed locally as `f17d528a`; this DNA working copy remains uncommitted to
preserve the existing migration and documentation work.

## Shaping and presentation follow-up

The optional profile now loads HarfBuzz, FriBidi and FreeType runtime libraries
explicitly. The builder checks availability before replacing build outputs.
Paragraph direction and wrapped-line ordering use FriBidi; script/font runs use
HarfBuzz with the complete accepted line as context. Source bytes remain
unnormalized. Ligature byte offsets share a cluster rectangle, matching SDL_ttf's
query contract; RTL midpoint clicks now follow logical source direction.
CFF and first-face TTC open/render/resize/lifetime tests use the FreeType fallback.

The shared itemizer inherits Common/Inherited scripts from neighboring strong
scripts, rather than implementing the complete Unicode ScriptExtensions and
paired-punctuation policy. It exposes one caret affinity at bidi transitions.
Those limits, color glyph formats, other native platform profiles and real IME
session qualification still prevent changing the default backend.

Profiling the full production workflow attributed its timeout to opaque fills
and presentation, rather than shaping. Fully opaque pixels now replace the
destination directly; transparent native pixels skip clip work. The profile
requests GLX interval zero at creation and forwards later vsync changes, using
the shared checked extension API. Qualification keeps the original 20-second
workflow timeout. Diagnostic counters were confined to disposable build stages.

Native font files remain bounded to 64 MiB, point sizes to 1..256 and fallback
faces to 16. Fractional point sizes round to a pixel EM for shaping/rasterization,
as in the initial native adapter. CFF/TTC support currently applies to explicit
font-file loading; the shared discovery scan still filters to core TrueType
faces. Additional caret affinities remain application-level follow-up work; visual
selection support is recorded below.

Final shaping qualification passed native and SDL production workflows in both
debug and release under the unchanged smoke timeout. Native pixel/input and
clipboard oracles pass; independent C shaping/bidi/raster metrics oracles and
desktop object builds pass. Native production binaries retain an SDL-free
dependency audit. Logs are under `build/shaped-text-qualification/`. Shared SDK
changes are committed locally as `834fb9a7`; DNA changes remain in the existing
uncommitted working copy.

## Visual selection follow-up

`vendor/text/layout.selection` maps a logical UTF-8 range to selected visual
rectangles, preserving bidi gaps and expanding touched ligatures/graphemes.
The text wrapper exposes read-only region callbacks for native, SDL and TUI
backends. Application drawing coalesces touching regions, retains visual y
offsets, and uses virtual space after the visual line end for selected LF
characters. It does not union a logical row into one rectangle across gaps.

Bundled SDL_ttf's range API unions every selected cluster on a logical row,
which can cover unselected bidi cells. The SDL adapter instead visits individual
clusters and groups consecutive selected visual cells, retaining unselected
clusters as barriers. This preserves ordinary contiguous LTR bands despite
glyph side bearings. Geometry callbacks describe painting regions; source
offset/length fields of a merged region are a hull, not a caret/navigation run.

The SDK regression includes adjacent LTR source ranges at different embedding
levels, separated visually by unselected Hebrew. Production tests cover that
gap, visual Unicode line offsets, coalesced LTR/blank rows and single-cell LF
selection. LF remains the document row model; broader visual-row accounting
for Unicode paragraph separators is unchanged.

Terminal qualification also found that the native overflow event reused the
terminal paste event ID. Overflow now uses a distinct ID with a compile-time
assertion. The full terminal frontend test, including bracketed paste into
a shell pane, passes again.

Final visual-selection qualification passed native and SDL production workflow
smoke in debug/release, all six legacy selection/cursor cases in both SDL modes,
backend selection oracles and the full terminal frontend regression suite
(including shell-pane bracketed paste). The terminal release-only profile also
builds. SDK C-derived selection unions pass debug/O2/O3 and six desktop object
targets, including the equal-parity bidi counterexample. Logs are retained under
`build/selection-qualification/`. SDK changes are committed locally as
`583b7f5f`; DNA remains in its existing uncommitted working copy.


## Optional Wayland frontend

`scripts/build_native.py --backend wayland` stages an independent native profile
under `build/native-wayland` and produces `dna-native-wayland-debug` (or
`-release`). Add `--smoke` for the workflow fixture. The existing X11 output
paths and default selection remain unchanged. Run the selected binary directly
inside a Wayland session; `DNA_SMOKE_BACKEND=native-wayland` selects its smoke
fixture. The Wayland binaries link neither
SDL nor X11/GLX; the framebuffer presenter and shaped text backend are shared.

Backend-specific character translation now lives behind a small platform module.
X11 retains its XKB lookup. Wayland uses the Unicode snapshot carried by each
ordered key event, preserving Shift, keyboard group and AltGr even if subsequent
queued events change modifiers. Production rendering/input oracles pass in both
modes, including GPU pixel readback, renderer recreation, event ownership,
multiclick/drag state and queued translated characters. The independent shaping
oracle and existing X11 platform/workflow checks also pass.

The native SDK now exposes checked title, size, swap interval and clipboard
operations through its Wayland/Windows/macOS facades. Wayland clipboard snapshots
support 16 MiB, immutable outgoing transfers and atomic nonblocking receives with
a five-second idle timeout. Failure preserves the previous completed snapshot.
Windows and Cocoa explicitly retain their 64 KiB capacity. Windows strict x64
and ARM64 builds and a Wine clipboard API oracle pass; Cocoa still requires a
macOS SDK and runtime.

Wayland publication needs a genuine seat input serial. Automated editor startup
has no such input; the unassisted startup workflow therefore fails at its first
clipboard-dependent Vim edit. The test-only `DNA_TEST_WAYLAND_INPUT` gate waits
for real input after presenting the window. An isolated nested niri harness
supplies that input without accessing the desktop clipboard. The SDK live
harness passes a genuine 1.2 MB source/offer/pipe round trip and empty publication.
The full DNA workflow also passes in both debug and release inside that isolated
compositor, including clipboard-dependent Vim edits and multi-selection paste.
The harness supplies one Shift press/release per newly focused test window;
continuous injection would correctly exhaust the bounded deferred input queue.
After building both smoke modes, run:

```sh
DNA_SMOKE_BACKEND=native-wayland DNA_SMOKE_MODES="debug release" DNA_DEFAULT_SERVERS=0 \
  python3 ../dyn/compiler/tests/window-clipboard-wayland-live.py --run python3 scripts/smoke.py
```

Standard pipe/production callback tests additionally cover capacity, malformed
UTF-8, busy requests, immutable sends and all-or-overflow event delivery.

These profiles remain optional. Real IME sessions, native Windows/macOS editor
integration, color glyphs, expanded font discovery, ScriptExtensions/caret
affinities and Unicode paragraph-separator row accounting remain follow-up work.


SDK changes are committed locally as `b1cc613f` at `ui-box`. DNA remains in its
existing uncommitted working copy. Workflow evidence is retained in
`build/wayland-workflow-isolated.log`; platform, shaping and X11 regression logs
are alongside it. Temporary nested compositors and the Xwayland regression
server were stopped after qualification.


## Installed SDK compatibility and desktop portability audit

The published preview.27 SDK predates `std/ui/box`. Running current unpublished
DNA source against that package reproduces the missing-import error, even with
the correct preview.27 compiler selected. Supplying the development SDK makes
source checking pass; the supported local workflow uses the matching development
compiler and SDK together. The README now states that requirement. The preview
helper and editor build wrapper reject a missing UI SDK with concrete commands,
and the compiler now distinguishes missing SDK modules from project imports.
Preflight layout tests, real resolver regressions, development source checking
and the release editor build pass. The published preview.7 compatibility evidence
remains historical and does not qualify this later working source.

The Windows/macOS presenter is already a portable OpenGL function table, and the
text loader supports platform library names. The remaining editor services are
not portable yet: notification uses epoll/eventfd; watching uses inotify;
synchronization embeds glibc pthread storage; installation assumes Linux file
layouts and renameat2; processes use Linux pipe/wait/signal behavior; terminal
transport uses forkpty with Linux termios/ioctl layouts. Windows needs its own
terminal transport. Recovery also calls the glibc errno accessor. The builder
assumes ELF linking and Linux dependency inspection. Windows/Cocoa ordered key
producers still need translated-character snapshots before sharing DNA's new
Wayland character adapter. A frontend switch alone cannot qualify these hosts.

The next bounded desktop step is a native window/presenter/keyboard probe that
excludes the Linux editor service library, followed by explicit platform service
adapters. Native Windows/macOS runtime access remains necessary for qualification.


## Release shortcut and isolated desktop probe

`just run-release [file]` now builds the optimized editor with the selected
compiler/SDK and launches it with the same file quoting and default-server
behavior as `just run`. The development-SDK release build passes; the recipe
also preserves paths containing spaces.

`tests/native_desktop.py` isolates the native window facade and production
framebuffer presenter from `libdna_native` and all editor services. It compiles
Windows and macOS x64/ARM64 objects in debug and release. On Linux it also builds
the Wayland bridge and runs live debug/release checks for title/size/pacing,
ordered wake events, asymmetric pixel upload/readback, swap, invalid/closed
handles and presenter destruction/recreation. Its dependency audit rejects
SDL, X11/GLX and the editor service library. These checks pass. Use
`python3 tests/native_desktop.py --object-only` without a live desktop session.
Native Windows/macOS execution, translated keyboard snapshots and clipboard
behavior are explicitly outside this probe's qualification.


## Native translated keyboard snapshots

Windows and Cocoa now populate the same ordered `KEY.height` scalar snapshot
as Wayland. Logical key identity and text/IME delivery remain separate. Windows
captures keyboard state/layout at message processing time, preserves AltGr,
normalizes plain Ctrl shortcuts and copies the snapshot across coalesced repeats.
Cocoa reads each event's character string with its Shift/Option/Caps modifiers.
Ambiguous multi-scalar output, malformed UTF-16 and dead-key output without a
single committed character report zero. Cocoa also excludes function-key codes.
The shared event ABI remains 312 bytes.

The Win32 production-message oracle passes with controlled keyboard APIs under
Wine, including queued layout/modifier changes, repeats, supplementary Unicode,
Ctrl/AltGr and unchanged WM_CHAR behavior. Strict Windows x64/ARM64 C compilation
passes. Cocoa's production UTF-16 helper passes portable scalar tests. Existing
ordered-event, live Wayland snapshot and IME regression checks pass. Actual
Windows keyboard layouts/dead-key sessions and Cocoa AppKit compilation/runtime
remain unqualified here. This supersedes the earlier missing-snapshot audit item;
Linux-specific editor services still block full Windows/macOS editor builds.

SDK keyboard changes are committed locally as `c0bbe281` at `ui-box`. DNA
remains in its existing uncommitted working copy. Compiler qualification logs
are retained under `build/keyboard-{events,ime,surround,wayland}.log`.


## Portable synchronization ownership

DNA mutexes, conditions and one-time initialization now use `std/sync` records
behind the existing opaque exported handles. Native threads still use pthreads
on Linux so linked C libraries retain valid TLS. The clock and other Linux
services remain platform work; this does not qualify the full editor on other
hosts. Native layout probes no longer compare opaque SDK records to pthread
mutex/condition layouts. The syntax try-lock path uses SDK try-lock as well.

The SDK adds `condition_wait_timeout` with relative monotonic nanoseconds,
explicit Signaled/TimedOut outcomes, a fixed deadline across interruption, and
mutex reacquisition on success, timeout and failure. Disk fallback retains its
250 ms bounded wait when no control pipe can be created. Predicate handoffs,
contention and independent mutexes pass through the exported DNA ABI before and
after migration. A symbol audit rejects leftover pthread mutex/condition/once
calls, preventing incompatible native APIs from receiving SDK records.

Qualification passes allocation accounting, thread TLS/results and join-failure
ownership, syntax updates/memory/fault recovery/retirement, process transport,
and file watching with notification and control-pipe failures. Live native
Wayland and SDL workflows pass in debug/release. One initial combined Wayland
workflow exceeded its existing 20-second release timeout; a fresh release run
and one combined rerun passed. All logs are retained under `build/sync-port-*`.
SDK timeout tests cover genuine waiting, producer signals, interruption without
budget restart, error mapping and reacquisition in debug/release. Windows/macOS
cross-links pass; native timed-wait execution on those hosts remains unqualified.

Qualification also exposed two build-boundary issues. The ELF linker now keeps
hidden runtime unwind references module-local even when a dependency exports
the same names; the independent provider/consumer regression and actual syntax
retirement fixture pass. Optional native profiles now use distinct service
library SONAMEs, preventing the SDL runtime in mise's LD_LIBRARY_PATH from
replacing their isolated runtime. Compatibility symlinks retain existing oracle
paths. Both native builders pass their dependency audits with that environment.


Static native archives now localize compiler-generated SDK definitions while
retaining their unmangled public ABI. This prevents new transitive SDK imports
(such as `std/errors` through timed conditions) from colliding with definitions
in the consuming editor. Both regular and TUI archive export guards and a
consumer that uses the same SDK modules pass. Shared-library input objects stay
unchanged. The terminal profile builds again.

SDK changes are committed locally as `96ee1bb2` (hidden unwind binding) and
`4bf9cf64` (timed conditions), with `ui-box` at the latter. DNA remains in its
existing uncommitted working copy. Remaining desktop services include process,
terminal, notification, file watching, native thread/clock and filesystem ABI
ports; this synchronization slice alone does not make Windows/macOS editor
builds available.

The final full terminal frontend suite passes with the rebuilt terminal profile,
including PTY/shell-pane behavior. Static lifecycle and archive-isolation gates
also pass after a complete dependency rebuild. Qualification logs remain under
`build/sync-port-*`.


## Portable clock adapter

`src/native/dyn/clock.dyn` now owns monotonic elapsed time through `std/time`
and `std/sync`, independently of pthreads and Linux clock IDs. Allocation
lifetimes retain nanosecond precision. Failed, regressing or overflowing samples
retain the last accepted elapsed value. A separate initialization flag accepts
a genuine zero monotonic origin. The public `dna_ticks` millisecond epoch begins
at its first call; earlier allocation tracing and syntax timing do not start it.

Syntax workers use internal elapsed milliseconds. Search retains its five-second
monotonic deadline, including compilation time; unavailable clock/deadline
samples cancel the scan with a partial result. Join-failure retry sleeps now use
SDK sleep rather than a Linux nanosleep syscall. Native pthread threads remain
in place for C-library TLS. The obsolete native timespec layout assertion is
removed; platform time layouts belong to the SDK.

The standalone production clock probe passes controlled failure, zero-origin,
backward time, fractional nanoseconds, overflow/recovery and real elapsed-time
checks in debug/release. It also compiles all six desktop objects. The probe
includes the exact production syntax timer and catches accidental initialization
of the public epoch. These object checks do not qualify Windows/macOS execution.

Release editor builds, allocation/TLS checks, mutex/condition ABI tests,
join-failure ownership, project-search cancellation/read interruption, syntax
updates/memory and static lifecycle checks pass. Rebuilt SDL and native Wayland
workflows pass in debug/release; the Wayland profile also retains isolation with
the default dependency directory on LD_LIBRARY_PATH. Logs are retained under
`build/clock-port-*`. DNA remains in the existing uncommitted working copy.

Final clock qualification also passes the rebuilt full terminal frontend suite,
including shell panes, resize, suspend/handoff and paste behavior. The terminal
log is `build/clock-port-terminal.log`.


## Release performance comparison, 2026-10-27

`scripts/benchmark_versions.py` compares the preserved October 24 release with
current default SDL release using frozen matching libraries, the same explicit
font and text fixture, CPUs 2–5 and five alternating pairs after warmup. It makes
no product changes. The scored CPU-only dummy-display comparison finds typing
medians of 1.198/1.198 ms and paging medians of 0.930/0.927 ms (old/current).
Warm launch-to-first-submit medians are 6.42/6.59 ms. Input batch CPU, including
startup/loading/probe exit, rises about 3%. Idle RSS medians are 31.64/35.99 MiB;
PSS medians are 25.58/30.21 MiB. These measurements support essentially unchanged
typing/paging speed with roughly 4–5 MiB higher footprint in this fixture.

Each input kind contributes 300 timed actions per version. Paging alternates
PageDown/PageUp; it is not mousewheel input. Idle CPU medians are zero observed
scheduler ticks, but one-second windows with 10 ms CPU accounting resolution do
not establish zero CPU work. The optional native Wayland renderer and physical
input-to-display latency are not measured. The legacy multi-file workflow stalls
on baseline readiness during preparation and is excluded, rather than counted
as a performance regression. An earlier unpinned-font pilot is also excluded.

Raw samples, frozen binaries/libraries, hashes, exact dependencies, logs and the
HTML report are under `build/version-benchmark-20261027-scored`. No usability
changes were made; that work remains the next user-directed task.


## Terminal editor comparison, 2026-10-27

The current optimized terminal-only DNA profile was compared with the installed
Neovim 0.12.6 and Helix 25.07.1 using `scripts/benchmark_editors.py`. Three runs
rotate editor order on CPUs 2–5. All editors use the same ~50 KB plain-text
fixtures, 120-by-32 PTY and actual reconstructed screen-content acknowledgments;
personal configuration and third-party plugins/LSP are excluded. Per editor,
the run includes fifteen startups, 180 inserts, 180 backspaces, 120 top/bottom
jumps and three passes over twelve files.

Median startup is 2.474/8.160/10.046 ms for DNA/Neovim/Helix. Insert medians are
0.171/0.314/0.443 ms; backspace 0.191/0.316/0.476 ms; top/bottom jump
0.259/0.436/0.903 ms. Retained proportional memory after repeated file opening
is 23.01/14.89/18.43 MiB. DNA has lower measured latency but higher memory in
this narrow workload. These terminal figures are not comparable to the earlier
SDL CPU-submission timings and do not establish physical display response.
They do not cover large files, LSP workloads or GUI behavior; CPU utilization
was not measured here.

Command-based file switching produces an unexplained Helix outlier near 282 ms,
versus DNA 0.292 ms and Neovim 0.662 ms. That command-path measurement needs
separate investigation and is excluded from the headline interpretation. Raw
results, binary/runner hashes, exact versions, the combined summary and HTML
report are under `build/editor-compare-20261027`. No product/usability changes
were made for this comparison.


## Measured performance improvements, 2026-10-27

The pre-optimization releases and matching libraries/source are frozen under
`build/performance-improvements-20261027/baseline`. Memory attribution found
transparent huge-page amplification in sparse terminal screen arrays, rather
than unreclaimed undo data. The initial residency hint alone did not recover
already resident pages. Screen grids and output now use one lazy owning arena,
receive the Linux small-page hint before first touch, and are released/reset on
TUI shutdown. Capacity and rendering semantics remain unchanged. Linux hints
now accept unaligned valid spans; unsupported hints remain nonessential.

Three fresh phase pairs attribute 5752 KiB (about 5.6 MiB) directly to screen
mapping savings. Larger observed PSS reductions include stack/huge-page placement
variation. A separate three-pair 12-buffer terminal workload measured median
PSS 21.34 to 13.71 MiB; five SDL pairs measured idle PSS 28.27 to 22.24 MiB.
These are local measurements, not portable memory guarantees. Existing document
reload/shrink returns within about 250 KiB of the empty phase; preserving undo,
snapshots and reclamation tests avoided speculative history changes.

SDL selection caches one active layout, bounded to 1 MiB of source bytes,
visually sorted cells, region scratch and metadata. Text/wrap/whitespace/font
changes invalidate it; known fallback fonts are tracked, and registry overflow
falls back safely. SDL properties own cleanup, with pins protecting callback
mutation, reentry and destruction. Ordinary unchanged setter calls and unrelated
chrome updates preserve reuse. Large cases continue through the correct
uncached path. In focused paired tests, warm ASCII/RTL requests fell from about
1023 to 23 microseconds (44x); multiple-range requests from 1014 to 7.9
microseconds (128x), with equal geometry checksums. Tested retained capacity is
about 331 KiB. These are repeated geometry-query gains, not editor-wide gains.

The expanded harness covers 1/10/100 MiB files, a long Unicode line, sixteen
selections with exact save/undo checks, and a logged deterministic LSP peer.
Each edit/paging action has 100 samples with p95/p99, CPU ticks, faults and phase
RSS/PSS. LSP traffic proves initialize/open, 200 changes, 100 completions and
diagnostics. Baseline Unicode end visibility failed: terminal coordinate
conversion collapsed every negative text origin to -1. Correct signed flooring
fixes it, with ASCII/combining/CJK/emoji rendering regressions. Final candidate
passes all six workloads, including 200 Unicode end/start jumps. Raw baseline
failure remains explicit; no baseline jump latency is invented.

Hard-workload latency changes are mixed and single trials do not establish a
general speedup. Immutable binary hashes, exact harness/fixture/config hashes,
paired memory/selection data, before/after percentile summaries and the HTML
report are saved under `build/performance-improvements-20261027`. Full SDL and
isolated native Wayland workflows pass debug/release; the full TUI suite,
legacy selection/cursor rendering, cache lifecycle and document reclamation
checks pass. No Windows/macOS runtime or physical-display latency claim is made.
All DNA changes remain in the existing uncommitted working copy.
