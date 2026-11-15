# Languages and language servers

## Language installation and highlighting

Typing keeps the last parsed colors on text that the revision journal proves
unchanged, including suffixes shifted by insertions/deletions. Edited bytes stay
plain until fresh highlighting arrives. If history is unavailable, rendering
falls back to plain text rather than using unrelated offsets. Structural syntax
operations still require the parser's current revision; provisional display
colors never authorize syntax selections or text objects.

Parser completion wakes schedule a full service pass before idle, so finished
colors appear without another keypress. GUI highlighting colors the existing
shaped glyphs once, preserving contextual shaping and avoiding normal-text
overdraw. Highlight queries complete on the worker thread with cooperative
yielding and cancellation; capture counts and elapsed time do not silently
publish a partially colored document as finished.


Nothing downloads on startup. `:languages` opens the language manager in both
the GUI and TUI: one row per language, grouped into **Installed** (highlighting
or a DNA-managed server is installed) and **Available**. Each row shows whether
highlighting works (`syntax ✓`) and the state of the language's server:
**running**, **found** (on PATH; starts when you open a file), **installed** (by
DNA), **configured** (in your config), **can install** (DNA can install it),
**not found** (install it yourself) or **failed**. The pane beside the list
describes the selected language: its file types, where its grammar is installed
and which repository and version it comes from, the server command and where it
was found, why it failed, and what `i` would fetch (for managed servers, the
pinned npm packages, which may be shared with other languages). `/` filters by
name or file extension (`/rs` finds Rust).

`i` installs whatever the language is missing (its grammar and, when DNA
manages one, its server); `x` removes what DNA installed; `u` updates them (with
no marks, every installed language). `R` starts or restarts the language's
server, `l` shows the server log, and `r` re-reads installation state and PATH.
Enter installs, like `i`. A marker before the name shows queued work: `+`
install, `-` remove, `↑` update, `*` marked.
**gg / Home** jumps to the first visible language; **G / End** to the last.
These jumps also extend an active visual range; **Shift+Home/End** starts and
extends a range. **v** starts visual selection; arrows or `j`/`k` extend or
shrink it, as do **Shift+Up/Down**. **v** or **Escape** finishes the range and
keeps its marks, and `i`/`x`/`u` act on it directly. **Space** marks or unmarks
one language; **q** (or **c**) clears all marks without closing the menu. With
marks, `i`, `x` and `u` act only on marked languages, including ones hidden by
the filter. Marks survive filtering, refreshing and reopening the menu;
successful operations clear them and failed ones keep them for retry. Updates
use this DNA build's pinned catalogue versions, not unverified upstream releases.
Press `/` to filter; Enter or Escape finishes filtering. Escape again closes the
manager. The editor stays usable while work runs; reopening `:languages` shows
progress. Failures stay in the menu with an option to view details; other
languages in a bulk operation still run.

When a language server stops, DNA shows one line naming the program and the
reason (the last error line it printed) instead of its whole output; `:lsp-log`
has the full output and `:languages` keeps the reason beside the language.
Incomplete packages remain available to install. The bundled
catalogue contains 55 languages: **Dyn, C, C++, C#, Python, JavaScript/JSX,
TypeScript, TSX, Rust, Go, Zig, Odin, Java, Kotlin, Scala, Dart,
Ruby, PHP, Lua, Haskell, OCaml, Elixir, Erlang, Gleam, Elm, Clojure,
Julia, R, GDScript, GLSL, Bash, Fish, Nushell, CSS, SCSS, HTML, XML, Svelte, Vue,
Markdown, Typst, JSON, TOML, YAML, INI, KDL, HCL/Terraform, Nix, Dockerfile, Make,
CMake, just, Protocol Buffers, GraphQL, and diff**. Package names use lowercase
identifiers (`cpp` for C++, `c_sharp` for C#, `javascript` for JavaScript/JSX,
`nu` for Nushell, `hcl` for HCL and Terraform). Swift, SQL, Perl and LaTeX are
missing because their grammar repositories do not commit a generated parser. These are syntax-highlighting
packages; language servers are listed under Language servers. `:language-install NAME` explicitly
downloads and builds a pinned grammar (for example, `:language-install json`).
Listings and installation progress/errors remain visible after the command finishes,
in navigation mode: Esc or `q` hides the popup; `:bd` closes its buffer. Then use
`:language-reload` to attach installed grammars to open files. The manager reloads
grammars automatically after successful changes.

Grammars live under `$XDG_CONFIG_HOME/dna/languages` (default
`~/.config/dna/languages`), overridable with `DNA_LANGUAGE_DIR`. Managed servers
live under its `.servers` directory. These paths follow DNA's config-directory
convention on the currently supported Linux build and survive mise upgrades.
Existing packages in the previous `~/.local/share/dna/languages` location are
left untouched: reinstall them through the menu to use the new location, or set
`DNA_LANGUAGE_DIR` to the old directory to keep using them. Uninstall removes the
active managed package; older versions retained by updates remain on disk.
The installer
checks the pinned archive SHA-256, compiles locally, validates the grammar ABI and
highlight query, and activates a complete version atomically. Installation uses the compiled Dyn helper plus `curl`, GNU `tar`,
`sha256sum`, `timeout`, and a C compiler; it runs outside the UI loop. No admin access or runtime Python is needed. Python scripts remain development
build/test tooling. The installer is built from [installer/main.dyn](../installer/main.dyn).

Tree-sitter parsing and queries run on workers, using document snapshots and
revision checks; stale results are never painted onto newer text. Uninstalled
languages stay plain text. Parsing has a work deadline and updates the retained
syntax tree incrementally; hidden buffers defer parsing until displayed.
Language packages associate extensions, or exact file names such as
`Dockerfile`, `Makefile`, `CMakeLists.txt` and `justfile`, with a grammar, highlight
query, and default indent width. Set a buffer's language with `:filetype python` (aliases `:ft` and
`:set-language`). This works for unnamed buffers, updates highlighting and language
indent width, and survives saving under another extension. It applies to all views
of that buffer; other buffers keep their own settings. `:filetype text` disables
highlighting, `:filetype auto` restores extension detection, and `:filetype` shows
the current selection. An unavailable grammar is reported with its install command;
the choice is retained for `:language-reload`. Overrides last for the current session.
The status line displays the filetype.

The checked-in catalogue is [languages/registry.toml](../languages/registry.toml).

Custom entries in `~/.config/dna/languages.toml` use the same fields as
[languages/registry.toml](../languages/registry.toml): language name, HTTPS archive
URL, SHA-256, source subdirectory, query path, extensions, optional `filenames`,
and indent width. `highlights` selects a query from the grammar's subdirectory,
`highlights_root` one from the archive root (for repositories that keep queries
above the grammar), and `bundled_highlights` one of DNA's maintained files in
[languages/queries](../languages/queries). Use exactly one. Queries may use the
standard predicates `#eq?`, `#match?`, `#any-of?`, `#contains?` (with `not-` and
`any-` forms) and Neovim's `#lua-match?`; directives such as `#set!` are ignored,
and a pattern with any other predicate is disabled on its own. Semantic tokens and
injected languages (code inside Markdown, scripts inside Svelte/Vue) are not
implemented.
Custom archives must have one top-level source directory; symlinks, hardlinks,
and special archive entries are rejected before extraction. Only install native
grammars you trust. The loader supports C scanners; C++ scanners fail
validation. Language servers are configured separately
from grammars (see below). Injected languages remain follow-up work.

## Language servers

Opening a saved `.dyn` file automatically starts `dyn lsp` from PATH. The compiler
includes this server; no separate package or syntax grammar is required. Set
`auto_start = false` in `[languages.dyn]` to disable this. `:server-start dyn`
starts it manually; `:lsp-log` shows startup failures. An explicit `server`
override retains the normal opt-in `auto_start` setting.

Other languages start a default server when its program is on PATH and you have
not configured one: rust-analyzer, gopls, zls, ols, clangd (C/C++), pyright,
typescript-language-server (JavaScript, TypeScript, TSX), lua-language-server,
jdtls, kotlin-language-server, csharp-ls, haskell-language-server, ocamllsp,
elixir-ls, erlang_ls, `gleam lsp`, elm-language-server, clojure-lsp, ruby-lsp,
intelephense, metals, `dart language-server`, nil, bash-language-server,
fish-lsp, `nu --lsp`, yaml/json/html/css language servers, marksman, taplo,
docker-langserver, cmake-language-server, tinymist, terraform-ls, svelteserver,
vue-language-server, glsl_analyzer and lemminx. Nothing installs on its own.
A configured `server`, or `auto_start = false`, in `[languages.NAME]` takes
precedence; `[lsp] default_servers = false` turns all defaults off.

To start a server explicitly instead:

```text
:filetype dyn
:lsp-start dyn dyn lsp
```

The filetype override is useful when no grammar is installed. Syntax packages and
language servers are independent. Copy [lsp.example.json](../lsp.example.json) beside
config.toml as `lsp.json`, remove servers you do not use, and run `:lsp-config` to
start configured servers. Values are shell commands you trust; the project
folder is their working directory. Other servers do not start merely by opening a project unless you configure `auto_start = true`.

| Feature | Shortcut / command |
| --- | --- |
| Completion | Ctrl-Space / `:complete` |
| Hover | Space-k / `:hover` |
| Definition / references | `gd` / `gr`, or `:definition` / `:references` |
| Rename | `:rename-symbol new_name` |
| Code actions | `:code-actions` |
| Diagnostics | Underlined ranges; mouse hover or `Space-k` shows the error; `:diagnostics` lists all |
| Server lifecycle | `:lsp-restart`, `:lsp-stop`, `:lsp-log` |

Errors are underlined in red and warnings in amber. Hover the marked text for 350 ms to read its message without opening a popup buffer; `Space-k`/`:hover` shows the diagnostic at the cursor and otherwise requests symbol information. The current line's message also appears in the status line. Decorations disappear immediately when their document revision becomes stale. Themes can override `diagnostic_error` and `diagnostic_warning`.

Results use arrows and Enter; Escape cancels. LSP snippets support numbered placeholders, nested defaults, linked fields, and a final cursor position. Tab moves forward, Shift-Tab moves backward, and Escape leaves snippet mode. Variables, choices, transforms, and unsupported or oversized syntax are rejected without changing the buffer. Rename, additional completion edits,
and code-action edits show a preview. Enter changes buffers without saving them;
`u` undoes each buffer's edit. Applying edits preserves selections and split-view
positions by line and column, clamped to grapheme boundaries; it does not track
semantic token identity when a formatter rearranges text. Stale versions,
overlapping edits, invalid UTF-16
positions, and changed files are rejected before text mutation. Code-action
resolution and explicit server commands are supported; command-requested edits
still require preview approval. Ordinary server commands may have their own
side effects outside the editor.

The client uses bounded asynchronous stdio JSON-RPC, UTF-16 positions, full or
full-range incremental synchronization, negotiated save notifications, and
request deadlines. Limits: 8 servers, 128 results/diagnostics, 16 edited files,
8 MiB transport messages. Snippets, semantic tokens, dynamic registration,
resource create/rename/delete edits, and remote document URIs are not supported.
The protocol reference is the [LSP 3.17 specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/).
