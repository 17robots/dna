# DNA

A native modal editor written in [Dyn](https://github.com/17robots/dyn). The
window shows your document, with line numbers and a slim status line.
Commands, search, files and buffer switching open as keyboard popups. It runs
as a native window (Wayland or X11, OpenGL) or in a terminal (`--tui`), with no
web runtime. Helix-style and Vim keymaps are built in.

DNA is an **experimental preview**. Read [PRERELEASE.md](PRERELEASE.md) for
the known limitations before relying on it.

## Install

The preview package is for Linux x86-64 and needs **glibc 2.38 or newer**
(Ubuntu 24.04, Debian 13, Fedora 39 and later), a monospace font, and desktop
graphics libraries for the window frontend.

```sh
mise use -g 'github:17robots/dna[prerelease=true,strip_components=1,bin_path=.]@0.1.0-preview.19'
dna path/to/file.dyn
dna path/to/project
```

Language servers are installed separately. Desktop menu entries, older
releases and the extracted package are covered in
[docs/install.md](docs/install.md).

## First five minutes

| To | Do |
| --- | --- |
| See command-line options | `dna --help` |
| Open the help buffer in the editor | `:help` (key reference only: `:keys`) |
| Open a file | `Space f`, or `:e path` |
| Insert text, then go back to normal mode | `i`, then Escape |
| Save / save and close | `:w` / `:x` |
| Close the buffer / discard and close | `:q` / `:q!` |
| Quit / discard everything and quit | `:qa` / `:qa!` |
| Run any command | `:` then type; arrows pick a row, Enter runs it |
| See the leader menu | Space |
| Switch keymap | `:keymap vim` or `:keymap helix` |
| Re-read recent status-line messages | `:messages` |

An unknown command reports `Not an editor command` instead of running the
closest match. Settings live in `~/.config/dna/config.toml`; start from
[config.example.toml](config.example.toml).

## Documentation

- [Keys](docs/keys.md): the Helix-style and Vim keymaps, menus, text objects
- [Helix compatibility](docs/helix-compatibility.md): every Helix default binding, measured
- [Configuration](docs/configuration.md): settings, fonts and layout files
- [Themes](docs/themes.md): built-in themes and writing your own
- [Languages](docs/languages.md): grammars, highlighting and language servers
- [Explorer](docs/explorer.md): the editable directory buffer and file tree
- [Projects](docs/projects.md): project directory, terminals, tasks, sessions, plugins
- [Saving and recovery](docs/saving.md): saving, recovery and external changes
- [Current limits](docs/limits.md)
- [Plugins](PLUGINS.md) and the [release notes](RELEASE_NOTES.md)

For contributors:

- [Building from source](docs/building.md): the pinned Dyn SDK, native macOS
  and Windows builds, renderers
- [Dyn version policy](docs/dyn-versions.md): when DNA ports to a new Dyn preview
- [Validation](docs/internals/validation.md): checks, ownership and latency tests
- [Design](docs/design.md) and [implementation notes](docs/implementation.md)
- [History](docs/history/): past migration notes and reviews

## Build from source

The pinned Dyn SDK and its checksums are in [mise.toml](mise.toml).

```sh
mise install
mise exec -- just run            # debug build of the window frontend
mise exec -- just run-release    # optimized build
mise exec -- just smoke          # full Linux check suite
```

Run `just deps` once after cloning. See [docs/building.md](docs/building.md)
for compiler development, other platforms and renderer options.

## License

[MIT](LICENSE).
