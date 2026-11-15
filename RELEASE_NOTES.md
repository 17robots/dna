# DNA 0.1.0-preview.20

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.39 compiler, SDK and runtime. It fixes Dyn highlighting of
strings that contain comment markers after an escape, and takes the Dyn
grammar and highlights from dyn-editors. The package still needs only
**glibc 2.38**.

## Changes

- The Dyn grammar is pinned to tree-sitter-dyn `b0a012f`, the revision
  dyn-editors 0.1.9 ships for Dyn preview 39 (previously `6fca64d`), and DNA's
  Dyn highlights are dyn-editors' Helix highlights. `#instance`, `#max`,
  `#min`, `#offset` and `#slice` are highlighted as builtins, and generic
  struct type parameters as types. `#wrap` and `is`, which Dyn no longer has,
  are gone.

## Fixes

- A `//` or `/*` inside a Dyn string after an escape was highlighted as a
  comment: `"q \" /* r"` greyed the rest of the line and every line up to the
  next `*/`, and `"q \n // r"` greyed the rest of the line. Strings now stay
  string text.

## Compatibility

Configuration, document and session formats are unchanged from preview 19.
An installed Dyn grammar is not replaced automatically: update it once with
`u` on Dyn in `:languages` (or `:language-install dyn`) to get the fix.

## Qualification

Formatting, the complete Linux smoke suite (including a new check that
comment markers after each escape stay string text), deterministic archive
verification, and the package in clean Ubuntu 24.04, Debian 13 and Fedora 40
containers. Highlighting was checked in the installed package on Arch.

See `PRERELEASE.md` for the remaining limitations.
