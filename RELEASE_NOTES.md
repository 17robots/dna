# DNA 0.1.0-preview.21

Experimental Linux x86-64 preview built with the published Dyn
**0.1.0-preview.41** compiler, SDK and runtime. It migrates DNA to Dyn's
next-design language and standard library (`<T>` generics, `T!E` return-value
errors, `.len`, alias-first `use`), updates the bundled Dyn Tree-sitter grammar
and highlight queries, and ships smaller, faster release binaries (~11% smaller
executable, 6–17% faster release buffer editing benchmarks). The package still
needs only **glibc 2.38**.

## Changes

- Built on published **Dyn 0.1.0-preview.41** with verified SDK checksums in
  `mise.toml`.
- The Dyn grammar is pinned to `tree-sitter-dyn` `367c3c46` (pure `grammar.js`,
  no `scanner.c`), matching `dyn-editors` `v0.1.11`, and DNA's bundled
  `languages/queries/dyn.scm` highlights `<T>` generics, `T!E` / `A | B` error
  unions, `try` / `catch` / `fail` / `errdefer`, `nocopy`, `#take`, `.Variant`
  shorthand, raw backtick strings, and labeled loops.
- Release binary `.text` shrinks ~13% (overall release binary ~11% smaller) and
  release buffer edits, equal-length replacements, and bulk indentation run
  ~6–17% faster.

## Compatibility

Configuration, document and session formats are unchanged from preview 20.
An installed Dyn grammar is not replaced automatically: update it once with
`u` on Dyn in `:languages` (or `:language-install dyn`) to pick up the
preview 41 grammar and highlights.

## Qualification

Formatting, the complete Linux smoke suite, deterministic archive verification,
clean Ubuntu 24.04, Debian 13 and Fedora 40 package container runs, and native
host-adapter checks across Linux, macOS (Cocoa), Windows x64 and Windows ARM64.

See `PRERELEASE.md` for the remaining limitations.
