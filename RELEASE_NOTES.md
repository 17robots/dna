# DNA 0.1.0-preview.11

Experimental Linux x86-64 preview built with the published Dyn
0.1.0-preview.30 compiler, SDK and runtime.

## Changes

- Fix fuzzy or distorted text in pickers, the command palette, and the explorer
  at larger window sizes. Popup textures sampled at texel boundaries could
  duplicate or skip glyph pixel columns due to GPU interpolation rounding.
  Integer one-to-one texture copies and glyph masks now sample texel centers.
- Add a 2548 × 1407 GPU regression comparing popup glyph pixels with the
  software renderer. Existing scaled, cropped, translucent, and retained-target
  rendering checks remain in place. The test uses an exact-size framebuffer
  so headless compositors cannot constrain its readback dimensions.

## Compatibility

Unchanged from preview.10. The application target remains Linux x86-64 and
needs compatible host glibc, a monospace font, and desktop libraries/graphics
drivers for GUI operation. See the archive's `build-info.json` for its minimum
glibc version. Both GUI and TUI are included; macOS and Windows editor releases
are not available.

## Qualification

Release gates are formatting, the complete Linux smoke suite, deterministic
archive verification, extracted dependency resolution without checkout paths,
and extracted GUI startup. The popup regression is also checked with both
Wayland and X11 in debug and release builds.

Back up important files before trying this experimental preview. Broader desktop,
IME and sustained workload testing remains outstanding. See `PRERELEASE.md`.
