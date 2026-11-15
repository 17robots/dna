# Installing DNA

## Install the prerelease with mise

The Linux x86-64 preview requires **glibc 2.38 or newer** (Ubuntu 24.04, Debian
13, Fedora 39 and later), a system monospace font, and desktop display
libraries for GUI mode. See [PRERELEASE.md](../PRERELEASE.md) before
installing. Preview.19 changes are recorded in
[RELEASE_NOTES.md](../RELEASE_NOTES.md).

```sh
mise use -g 'github:17robots/dna[prerelease=true,strip_components=1,bin_path=.]@0.1.0-preview.19'
dna path/to/file.dyn
dna path/to/project
```

Use `mise exec github:17robots/dna@0.1.0-preview.19 -- dna path/to/project`
if mise is not activated in your shell. The explicit `bin_path=.` selects the
archive's launcher, which loads its bundled libraries and the host's Wayland,
X11 and GL libraries (so they match the graphics driver). The Dyn SDK is needed to
build DNA, but is not required to run this package. Language servers are
installed separately.

This uses [mise's GitHub backend](https://mise.jdx.dev/dev-tools/backends/github.html);
no separate mise plugin or registry entry is required.

### Desktop launchers

Packages from preview.9 on include `dna-install-desktop` and standard entries
under `share/applications`. Run the helper after extracting the package:

```sh
./dna-install-desktop
```

It registers **DNA** (`--gui`) and **DNA (Terminal)** (`--tui`, `Terminal=true`)
in `$XDG_DATA_HOME/applications`, defaulting to `~/.local/share/applications`.
The entries use the package launcher's absolute path; fuzzel and other desktop
menus need no mise environment or PATH changes. The terminal entry uses the
terminal configured by your desktop launcher. Run the helper again after moving
or upgrading the extracted package. Setup needs a POSIX shell and `awk`.

For mise releases that include the helper, add this to the existing DNA tool
section of your global mise config to refresh the entries after each install:

```toml
[tools."github:17robots/dna"]
# Keep your existing version, asset and checksum settings.
postinstall = '"$MISE_TOOL_INSTALL_PATH/dna-install-desktop"'
```

To register an older installation, such as preview.8, from this checkout:

```sh
./packaging/linux/dna-install-desktop --launcher "$(mise which dna)"
```

To remove the menu entries, delete `dna.desktop` and `dna-tui.desktop` from that
applications directory. Setup registers launchers; choose default file
associations separately in your desktop settings.

## Local Linux preview package

```sh
just smoke
just package
# Extract build/packages/dna-preview-linux-x86_64.tar.gz anywhere, then:
./dna-preview-linux-x86_64/dna [file]
```

The archive includes the editor, native adapter, language installer, linked
non-glibc libraries, theme/layout examples, dependency metadata, licenses, and
checksums. No Dyn SDK or Python is needed to run it. Add the extracted directory
to PATH for the `dna` launcher; keep its bin/lib/share directories together.
The launcher supplies its own library search path. A system monospace font,
compatible glibc, display backend, and graphics drivers are still required.
`build-info.json` records the build inputs; the archive envelope is deterministic
for identical input binaries. Fully reproducible compiler/system builds and
cross-distribution compatibility are not claimed. Packaging does not upload,
tag, or publish anything. Platform ports remain separate work.
