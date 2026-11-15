# DNA 0.1.0-preview.18

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.38 compiler, SDK and runtime. The package now needs only
**glibc 2.38**: it runs on Ubuntu 24.04, Debian 13 and Fedora 40, which
preview 17 (glibc 2.43) did not.

## Changes

Commands and messages:

- A mistyped `:` command reports `Not an editor command: …` instead of running
  the closest fuzzy match. Enter runs a palette row when you picked it with
  the arrows or Ctrl-N/P, or when the typed words start its title's words.
- New `:q!`, `:qa!`, `:e!`, `:w!`, `:ls`, `:sav path`, `:!cmd`, `:noh`,
  `:messages`, `:marks` and `:[range]sort[!] [i] [n] [u]`.
- Short results appear in the status line until the next key instead of in a
  dialog: searches that find nothing, writes, unknown commands, Vim errors,
  language servers that fail to start. `:messages` lists the last 20.
- `:help` opens a reference generated from the key menus, your `[keys]`
  bindings and the command table; `:keys` shows the key part.
- `dna --help` prints usage; an unknown option exits with status 2; startup
  problems you can fix print a message instead of panicking.

Keymaps:

- Helix: insert-mode Ctrl-W / Alt-Backspace, Alt-D, Ctrl-U, Ctrl-K, Ctrl-D;
  `.` repeats the last insert; `]g` `[g` `]G` `[G` move between git changes;
  `]f` `]t` `]a` `]c` (and `[`) between functions, types, parameters and
  comments; `y` reports what it yanked. 216 of Helix's 230 default bindings
  now respond (see docs/helix-compatibility.md).
- Vim: Replace mode (`R`), `gq` rewrapping that keeps comment leaders, file
  marks `m{A-Z}`, and `E20` for an unset mark.

Terminal and window:

- Dialogs keep text off their border and fit their buttons; the scrollbar no
  longer draws over text; Vim mode shows `~` after the last line.
- Input methods receive the text around the caret and can replace it
  (corrections, reconversion).
- The Dyn language server comes from the project's pinned dyn when mise pins
  one, so a different dyn on PATH no longer reports false errors.

## Compatibility

Configuration, document and session formats are unchanged. Behavior changes:
an unknown command no longer runs another command, and short messages no
longer open dialogs. In the Helix keymap, Ctrl-W in insert mode deletes the
previous word instead of opening the window menu (Space w still does).

## Qualification

Formatting, the complete Linux smoke suite, deterministic archive
verification, the package in clean Ubuntu 24.04, Debian 13 and Fedora 40
containers, and extracted GUI startup.

See `PRERELEASE.md` for the remaining limitations.
