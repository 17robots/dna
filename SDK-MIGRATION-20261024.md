# Development SDK migration, 2026-10-24

The working DNA source now uses the published Dyn preview.27 SDK pinned in
`mise.toml`. Global and project mise settings select the same verified package;
the preview helper uses its compiler and language server. Preview.25 remains
installed for rollback. This migration is included in the published Linux
[DNA preview.7](https://github.com/17robots/dna/releases/tag/v0.1.0-preview.7).

The development-SDK migration evidence below is historical. Fresh installed-SDK
qualification is recorded under `build/preview27-installed`; it clears
`DYN_SDK` and rebuilds native adapters against the package runtime.

## Preview.27 installed-SDK qualification, 2026-10-26

One uninterrupted `just smoke` run passed with the published, mise-installed
`dyn 0.1.0-preview.27` and `DYN_SDK` unset. Native adapters, the installer, and
editor binaries were rebuilt against the packaged runtime. This supersedes the
historical development-SDK qualification below for the current working source.

Coverage includes core debug/release suites, host/filesystem adapters, native
ABI and thread ownership, GUI and TUI workflows, language-server interactions,
saving/recovery failures, syntax lifetimes, memory/performance gates, standalone
packaging, and minimal/terminal profiles. The preview example also runs with the
installed SDK. These are Linux host and emulated-display checks; they do not
establish native Windows/macOS DNA behavior or physical keyboard-to-display
latency.

Evidence: `build/preview27-installed/environment.json`, `status.json`,
`full-smoke.log`, and `report.json` with compiler/output hashes. Previous SDKs
remain installed for rollback. At the time of this qualification, working changes were preserved and no
DNA source commit or application release had been created. The tested state was
subsequently reviewed, qualified by CI, merged, and published as preview.7.

## Try it

```sh
python3 scripts/preview_sdk.py
python3 scripts/preview_sdk.py path/to/file.dyn
```

The helper builds dependencies and a release editor with the same compiler and
runtime, then opens a real GUI window. It uses isolated configuration/state under
`build/sdk-preview`, disables recovery for the preview, and selects the matching
Dyn language server. It does not change your normal configuration. The example
prints `length=5, unit=(0.6, 0.8)` in debug and release.

A captured frame from the actual renderer is at `build/sdk-preview/editor.png`.
The capture uses a test interposer; the interactive preview runs without it.

## Changes

- Migrated 1,754 casts automatically across 147 files, plus individually reviewed
  ambiguous expressions and generated test snippets. The converter preserves
  unary/postfix boundaries and refuses uncertain operands. Golden, refusal, CLI
  safety, and legacy/current compiler execution tests cover it.
- Updated native callback types from legacy pointer syntax to function values.
- Migrated SDK file/read/path/argument results and arena-backed producers.
  DNA-owned fields such as `AtomicFile.file` and `FileText.data` retain their names.
- Preserved bounded C strings, path joins, symlink reads, and environment copies.
  JSON encoding counts output before allocation, so bounded editor scratch still
  returns an empty result on capacity failure instead of panicking.
- Replaced JSON lookup presence checks with `json.is_missing`, preserving the
  distinction between an absent property and explicit JSON null.
- Rebuilt native GUI/TUI adapters and the language installer with the development
  runtime. Updated production tests to the same APIs without removing behavioral
  assertions.
- Prevalidated Windows environment names before calling the allocating SDK
  wrapper, avoiding unbounded retries on invalid UTF-8 or oversized UTF-16 names.

The document/session/configuration formats, native thread implementation, sparse
uninitialized allocations, and UI design are unchanged.

## Verification

Logs are retained under `build/sdk-migration-20261024`.

- Development compiler checks and fresh debug/release editor builds pass.
- Native header/layout and SDL event-layout ABI checks pass. Native thread joins
  and process transport pass in debug/release.
- Host and filesystem adapters pass debug/release: Unicode paths/arguments,
  environment capacity, enumeration, permissions, and atomic commit/abort.
- All ten core suites pass debug/release: objects, buffer, files, layout, motion,
  pattern, settings, workspace, LSP, and servers.
- Full scripted editor smoke passes debug/release, including file saving and
  fake language-server workflows. Launch, typing/save/quit, render tracing,
  animations, selection geometry, and the TUI workflow pass.
- Cached syntax rendering matches full-document rendering byte-for-byte for
  Unicode, tabs, glyph bearings, and font resizing.
- Document memory checks pass for first edit, save, history, dirty edits, reload,
  and reclamation. Private dirty usage is identical in all fifteen recorded
  baseline/candidate phases; candidate RSS has a 64 KiB offset in those probes.
- Windows environment executable mocks cover invalid UTF-8, UTF-16 boundaries,
  diagnostic preservation, ownership, and short destinations. Windows target
  checks pass. These are not native Windows execution.

The entire `just smoke` matrix was not run. Native Windows/macOS execution and
physical desktop latency measurements remain outside this qualification.

## Measurements

Three alternating baseline/candidate samples use the same two-round workflow.
Median mean input-update latency is **1.794 ms baseline / 1.820 ms candidate**.
Median final RSS is **50,832 KiB / 52,436 KiB**. These are developer-host samples,
not a statistically established speed difference. Other tests ran during part of
sampling; the benchmark also loads the newly rebuilt native adapter for both
editor binaries. It compares editor executables, not isolated complete SDKs.
No speedup or overall memory reduction is claimed.

The separate latency gate reports release typing mean **0.90 ms** and movement
mean **0.88 ms** on its dummy-display fixture, with layout bounded to two rows.
Those timings are input-update work, not keyboard-to-display latency.

See `comparison/results.json`, `latency.log`, the two `document-memory-*.json`
files, and `focused-results.json` for precise scopes and raw observations.

## Preservation and rollback

DNA already had substantial uncommitted work. The pre-migration working files,
JJ status/diff, hashes, old executable, and native libraries are saved under
`build/sdk-migration-20261024`. `migration-only.patch` compares against that saved
working state, rather than the repository parent. No commit was made.

To undo this migration, reverse only the migration changes against those saved
files, remove its newly added tooling/example, and rebuild with preview.25 and
its matching runtime. Do not restore the entire repository parent: that would
remove the preexisting editor work. The baseline snapshot is local build evidence,
not a substitute for keeping your normal backups.

## Follow-up controlled comparison

A subsequent five-pair serial run uses each editor's matching old/new native
libraries and runtime, with affinity to CPUs 2–5. Median input-update time is
**1.832 ms old / 1.827 ms new**, and final RSS is **50,668 / 50,692 KiB**.
All ten workflow and rendering checks pass. The earlier 1.6 MiB RSS difference
above did not reproduce. These remain dummy-display update timings, not physical
keyboard-to-display measurements. Raw results are under
`build/sdk-migration-20261024/controlled-comparison`.

Separate compiled-program kernels do show regressions. See the detailed local
compiler report at `../dyn/compiler/build/runtime-comparison-20261024/REPORT.md`;
its disposable inlining/alignment experiments do not modify the working SDK.
