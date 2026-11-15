# Current limits

## Current limits

- Open-document storage grows with available memory; there is no fixed buffer-count limit.
  Files open, edit and save at any size (tested to 4 GiB); large files are
  mapped, not copied. Operations that build text in one piece (clipboard text,
  `:s` results, formatter output and language-server edits) are limited to
  **268,435,455 UTF-8 bytes**. NUL/binary files are refused. Unused text,
  line-index, and undo pages are not eagerly touched.
- Up to 64 undo states within a 4 MiB changed-byte budget per document; large replacements retain
  fewer states. Insert runs group until movement/mode changes.
- Movement/deletion follows Unicode grapheme clusters, including combining marks,
  emoji ZWJ sequences, and flags. IME preedit UI and comprehensive bidirectional
  text still need work. Tabs and wide glyphs render correctly; vertical movement
  currently follows grapheme columns rather than visual tab stops. Vertical
  movement remembers the desired column across shorter lines, including in
  selection mode. Horizontal movement and text edits reset that preference.
- Keyboard and mouse selection with cursor-following and mouse-wheel scrolling.
- Word classes distinguish whitespace, identifier text, and punctuation. Non-ASCII
  categories distinguish letters/marks/numbers from separators and punctuation;
  full linguistic Unicode word segmentation is not implemented.
- Directory listings and staged batches support at most 256 entries/operations.
  Explorer listings remain limited to 65,535 bytes and allocates its own undo arena.
- Tree-sitter highlighting, LSP, command-key overrides and a Vim keymap profile
  are available (see Vim keys for its gaps). Native GUI and TUI frontends, an
  experimental process-based plugin API, and persistent sessions are available.
  Remote filesystem access over SSH is not implemented.
- Linux remains the primary platform. Native macOS and Windows x64 builds run in
  CI, including file operations and GUI startup. On Windows ARM64, CI runs the
  native qualification tests as ARM64 programs; the full editor build there
  still needs an ARM64 MSYS2 toolchain.
