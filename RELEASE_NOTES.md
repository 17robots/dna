# DNA 0.1.0-preview.19

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.39 compiler, SDK and runtime. It fixes the window frontend on
hosts whose graphics driver needs a newer Wayland client library than the one
preview 18 bundled. The package still needs only **glibc 2.38**.

## Changes

- Updated the compiler, SDK and runtime to Dyn 0.1.0-preview.39, which removes
  union types. DNA declared none, so its sources are unchanged. Verified SDK
  pins for Linux, macOS and Windows and the Linux CI compiler download are
  updated.

## Fixes

- Preview 18 bundled Ubuntu 24.04's libwayland-client 1.22 and loaded it ahead
  of the system copy. NVIDIA's EGL driver (620 series, with egl-wayland2)
  loads the same library, failed with the older one, and DNA exited with
  `window creation failed (no usable display or GPU driver; try dna --tui)`.
- The Wayland, X11/xcb and GL dispatch libraries (`libwayland-*`, `libX11`,
  `libxcb`, `libEGL`, `libGL`, `libGLX`, `libGLdispatch` and what only they
  need) now come from the host, so they match its graphics driver. The package
  keeps copies under `lib/host/<soname>/`; the launcher adds one to the search
  path only when the host's `ldconfig` cache lacks that library, for example
  for `dna --tui` on a machine without a desktop.

## Compatibility

Configuration, document and session formats are unchanged from preview 18.
Plugins written in Dyn must build with Dyn preview 39; replace any `union`
with `#bitcast` or a payload enum as described in Dyn's
`docs/migrations/0.1.0-preview.39.md`.
The archive layout gains `lib/host/`. Start DNA through the `dna` launcher;
running `bin/dna-wayland` or `bin/dna-x11` directly uses only the host's
display libraries.

## Qualification

Formatting, the complete Linux smoke suite, deterministic archive
verification, the package in clean Ubuntu 24.04, Debian 13 and Fedora 40
containers, extracted GUI startup, and launcher library selection with and
without host display libraries. The Wayland frontend was checked on Arch with
NVIDIA 620.70 and egl-wayland2 1.0.2.

See `PRERELEASE.md` for the remaining limitations.
