# Projects, terminals, tasks and sessions

## Project directory, terminals, and tasks

- `:pwd` shows the project directory.
- `:cd path` changes it, with `~`, relative paths, and Tab completion of directory
  prefixes. `:cd` goes home; `:cd -` returns to the previous directory. Open file
  buffers keep their absolute paths. Pending explorer edits block the change.
- `Space t` (Space, then lowercase t) or `:terminal` opens a shell in a bottom split using one quarter of the active view,
  or focuses its existing pane. `:terminal-new` creates another shell below the active view.
  `:terminal-split` places a hidden terminal in a vertical split; an already visible terminal is focused.
  Terminals also appear in the buffer picker.
- Shell input goes directly to a real PTY. `pwd`, `cd`, Git, and interactive
  programs use the configured shell (`SHELL`, falling back to `/bin/sh`). A shell's
  `cd` affects only that terminal. New terminals start in the editor project root.
- Escape twice within 500 ms enters terminal normal mode; Ctrl+backslash also works.
  The first Escape reaches the terminal program immediately; the second is consumed by DNA.
  Intervening keys/text or changing focus resets the sequence. `i` returns to shell input;
  Escape or `q` hides a command-output popup. `:` opens editor commands, Space opens
  its menu, and Ctrl+W opens the window menu in terminal normal mode.
  Dismissing a popup or closing a split preserves the shell.
- Shift+PageUp/PageDown scroll; normal-mode PageUp/PageDown browse scrollback. Drag to
  select output; Ctrl+Shift+C copies the selection (or screen), Ctrl+Shift+V pastes
  with bracketed-paste support. Navigation-mode `y` copies too.
- Interactive shell buffers close automatically when the shell exits (including `exit` or Ctrl+D).
  Its terminal panes are removed too. Hidden shells close without changing focus.
- Terminal input mode sends every key to the program (Ctrl+X to nano, Ctrl+W to the
  shell, q to htop); only Escape twice or Ctrl+backslash leaves it.
- In terminal normal mode, Ctrl+X or `:bd` closes a terminal buffer. Running processes require confirmation before
  termination; quitting the editor also checks running terminals.
- `:run <shell command>` runs an explicit command in a new terminal buffer. Optional
  `build_command`, `test_command`, and `run_command` settings back `:build`, `:test`,
  and `:run`. `:error-next` opens the next `path:line:` diagnostic from the latest
  terminal's captured output, resolving paths against its initial working directory.

The first terminal backend is Linux/POSIX. It uses libvterm for ANSI colours,
alternate-screen programs, Unicode cells, and resize handling. Scrollback is bounded
at 2,000 lines, screen size at 240×100 cells, and diagnostic capture at 64 KiB.
Mouse input currently selects output rather than being forwarded to applications.
Terminal defaults, selection, cursor, and ANSI colours follow the selected theme.
Applications emitting explicit truecolour RGB retain those colours.

## Project tools, sessions, and extensions

- **Global search:** `Space /` or `:search-global <regex>`. Type to restart the
  background search; arrows/Page Up/Page Down choose a result, Enter opens its
  file and selects the match. Searches saved files under `:pwd`, with Unicode
  regex and multiline anchors. Locations use byte columns. Hidden entries,
  `build`, `target`, and `node_modules` are skipped; symlinks are not followed.
  Limits: 1,024 results, 20,000 entries, 16 levels, five seconds, and the editable
  file-size limit. Partial/invalid results are labelled; this is not gitignore-aware.
  Plain printable ASCII patterns without regex syntax use a cancellable byte-search
  path after the first checked match validates UTF-8. Other patterns use PCRE2.
  File reads and binary scans check cancellation at bounded intervals.
- **Project replacement:** finish a search, Escape, then
  `:replace-preview literal replacement`. The preview lists affected files/counts.
  Enter applies to undoable buffers; Escape cancels. Save each with `:write`.
  Dirty buffers, changed files, partial searches, zero-width matches, and more
  than 16 affected files are rejected. Replacement text is literal, not `$1` expansion.
- **Build/test results:** `:errors` opens a filtered diagnostics picker from the
  latest task terminal. `:error-next` and `:error-prev` navigate `path:line:column`
  output relative to that task's starting directory.
- **Discovery:** `:themes`, `:layouts`, and `:settings` are searchable pickers.
  Custom theme/layout files live beside config.toml in `themes/` and `layouts/`.
  Settings opens the selected key in an existing config; reload with `:config-reload`.
- **Relative layouts:** `tree = "v70(f,h50(f,f))"` means a 70/30 vertical split,
  with the right side split horizontally 50/50. `f` is a view, `v` is vertical,
  `h` is horizontal; ratios are 10–90%. Loading reuses current views in order;
  extra leaves show the active buffer. `tree = "f"` returns to one view.
  Use `:layout path.toml` or `:layouts`, and `:layout-save path.toml`.
- **Sessions:** `:session-save [path]` / `:session-load [path]`; default is
  `config.toml.session` beside your config (its parent must exist). Snapshots
  include text, saved baselines, unnamed buffers, filetypes, project directory,
  split ratios, and primary cursors. Restore refuses dirty buffers and running
  terminals. Terminal panes restore as empty buffers, not running processes.
  Named text comes from the snapshot; save-conflict checks still protect external
  disk changes. Undo history, secondary cursors, explorer staging, and plugins
  are not restored.
- **Crash recovery:** every 500 ms, changed workspace state is queued to
  a background writer under the config directory's `recovery/`. `:recoveries`
  lists snapshots left after a crash; Enter restores one. Each editor instance
  owns a private snapshot and deletes it on clean exit. `DNA_RECOVERY=0` disables
  this facility; `:plugin-log` also reports background recovery failures.
  Up to five seconds of recent work can be absent after a crash.
- **Plugins:** see [PLUGINS.md](../PLUGINS.md) for the separate-process protocol,
  local install/update commands, permission review, and the working Dyn example.

Terminal normal mode supports single-line j/k, Page Up/Down or Ctrl-B/F,
Ctrl-U/D half pages, gg/Home for oldest output, G/End for newest, and i to resume
input. Mouse-reporting terminal apps receive clicks/drags in input mode; hold
Shift for local text selection. Clicking another pane changes focus.
