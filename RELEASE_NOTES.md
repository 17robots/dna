# DNA 0.1.0-preview.13

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.30 compiler, SDK and runtime.

## Changes

- Custom keys per keymap and mode: `[keys.vim.normal]`, `[keys.helix.select]`,
  `[keys.insert]` and the rest. Bindings can be key sequences (`"j k"`,
  `"g x"`), type keys with `keys:` in Vim notation (`"Y" = "keys:y$"`), or
  disable a key with `none`. Up to 128 bindings; custom Space bindings show
  in the Space menu.
- Vim substitute and search reach full parity: `\%V`, `\%23l` and other
  position items anywhere in a pattern, `:set ic`/`scs`/`gd`, case
  conversion for accented, Greek and Cyrillic letters, and `^E`/`^Y` in the
  confirm prompt.
- New ex commands: `:m`, `:t`/`:co`, `:j`, `:reg`. `:g` and ranged `:normal`
  run top-down like Vim, so `:g/^/m0` reverses a file.
- Macros live in registers: `qA` appends, `"ap` pastes, `"ayy` makes one,
  and recursive macros work. A failing command stops a macro, `@:` repeats
  the last ex command, and Escape stops a long-running macro.
- Fix `gJ` adding spaces, and the cursor column after `dd` on the last line.

## Compatibility

Unchanged from preview.12. The application target remains Linux x86-64 and
needs compatible host glibc, a monospace font, and desktop libraries/graphics
drivers for GUI operation. See the archive's `build-info.json` for its minimum
glibc version. Both GUI and TUI are included. macOS and Windows ports now
build and pass CI, but editor releases for them are not available yet.

## Qualification

Release gates are formatting, the complete Linux smoke suite, deterministic
archive verification, extracted dependency resolution without checkout paths,
and extracted GUI startup.

Back up important files before trying this experimental preview. Broader desktop,
IME and sustained workload testing remains outstanding. See `PRERELEASE.md`.
