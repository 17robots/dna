# DNA 0.1.0-preview.7

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.27 compiler, SDK and runtime.

## Changes

- Migrate the editor, native adapters, language installer, examples and tests to
  the current Dyn syntax, arena handles and standard-library result contracts.
- Preserve missing-versus-null JSON semantics for language-server and plugin
  messages, and keep serialization within bounded editor scratch storage.
- Include document-memory improvements: sparse saved/checkpoint baselines,
  compact line indexing, edit/undo position mapping and incremental syntax hints.
- Improve project-search loading and cancellation, syntax lifetime handling,
  and associated memory/resource regression coverage.
- Pin verified Dyn preview.27 assets in project mise configuration and CI.

## Qualification and scope

The working source passed one uninterrupted Linux `just smoke` run with the
installed preview.27 SDK and no development-SDK override before release
preparation. Release qualification additionally requires formatting, the CI
smoke matrix, deterministic archive checks and extracted-package startup.
Scoped static reviews found no concrete issues; they are not an exhaustive
correctness or security audit.

The published application target remains Linux x86-64. The archive includes
native dependencies but still requires a compatible host glibc, a monospace
font, and display/graphics-driver libraries for GUI operation. Check the
archive's `build-info.json` for its exact minimum glibc version. Windows/macOS
host-adapter checks do not qualify a full editor release on those platforms.

Existing document, configuration and session formats remain in place. Back up
important files and configuration before trying this experimental preview.
See `PRERELEASE.md` for current limitations. Headless update-time measurements
are not keyboard-to-display latency measurements, and no universal performance
improvement is claimed.
