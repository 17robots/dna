# DNA 0.1.0-preview.22

Experimental Linux x86-64 preview built with the published Dyn
**0.1.0-preview.41** compiler, SDK and runtime. It modernizes DNA to Dyn
preview.41 idioms across the codebase and delivers major startup, search,
typing-burst, and memory optimizations (**−46% RSS**, **−78% private dirty
memory**, **4.6× faster 50 MB literal search**, **3–6× faster typing bursts**,
and **1.80 ms** terminal cold startup). The package still needs only
**glibc 2.38**.

## Performance & Memory

- **Typing bursts & input stack frames:** Moved `ExplorerVimBorrow` off the
  stack into `Explorer.saved_vim`, collapsing five hot input stack frames from
  282.5 KiB to 16–208 B and cutting 61-character typing burst input latency from
  774 µs to 55 µs (~0.29–0.37 ms end-to-end).
- **Startup & resident memory:** Switched fresh-arena large struct allocations
  (`App`, `UiTextCache`, `Document`, `Slot`, `PaneText`) to lazy zero pages,
  compacted `UiTextCache` (2.01 MiB → 128 KiB), deduplicated Vim file marks into
  `VimSession`, lazy-allocated `TuiText` and `Terminal` cell buffers (cutting
  `.bss` from 2.15 MiB to 421 KiB in `dna-release` and 105 KiB in
  `dna-terminal`), and eliminated per-lookup Linux `host.environment` arenas.
  Terminal cold startup drops to ~1.80 ms at ~5.75 MiB RSS (1.43 MiB private
  dirty).
- **Search:** Added a zero-copy rope-chunk literal fast path (`memchr`) and
  PCRE2 JIT compilation for both foreground and background (>16 MiB) searches,
  shrunk literal worker arenas from 17 MiB to ~140 KiB, coalesced incremental
  search previews per event batch, and replaced 1 ms polling loops with direct
  thread joins (`task_wait` / `save_wait`). 1 MB literal search drops to
  ~0.32 ms and 50 MB literal search drops from 6.4 ms to ~1.40 ms.
- **Rendering & buffer hot paths:** Added an O(1) 4096-entry GPU glyph atlas
  hash table (5.4× faster lookups), reusable `NativeFont.selection_scratch`,
  3-tier `rope_leaf` newline scanning, O(1) `line_slot_claim`, cursor-based TUI
  input parsing, and whole-row TUI diff skipping.
- **Save memory reclamation:** `set_saved()` now releases stale flattened text
  views, preventing up to ~94 MiB of retained snapshot memory in repeated
  save-in-group workloads.

## Cleanup & Modernization

- Modernized across 200+ files to Dyn preview.41 idioms (`str`, typed enums
  including `Command`, `.Variant` shorthand, exhaustive `case`, `nocopy` +
  `#take`, `T!` errors, range loops, `mem.copy`) with zero `dyn vet` warnings
  across Linux, Windows, and macOS targets.
- Removed obsolete one-off migration scripts and scratch helpers (−583 net lines
  overall).

## Compatibility

Configuration, document and session formats are unchanged from preview 21.

## Qualification

Formatting, cross-target `dyn vet` (Linux, Windows, macOS), the complete Linux
smoke suite, deterministic archive verification, clean Ubuntu 24.04, Debian 13
and Fedora 40 package container runs, and native host-adapter checks across
Linux, macOS (Cocoa), Windows x64 and Windows ARM64.

See `PRERELEASE.md` for the remaining limitations.
