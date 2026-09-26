# DNA

A native modal editor experiment written in Dyn. Local prototype; not yet an
editor for real files. [DESIGN.md](DESIGN.md) records the intended product.

## Run

Requirements: Linux x86-64, a working Dyn SDK, SDL3 development/runtime libraries,
FreeType and HarfBuzz development libraries, CMake, Python 3.12+, a C compiler,
and `just`. Tested here with Dyn 0.1.0-preview.5, SDL 3.4.16 and SDL_ttf 3.2.2.
`just build` downloads and builds pinned SDL_ttf into ignored `build/deps`; it
does not install system packages. No browser or C
runtime bridge is involved. Other operating systems have not been validated.

```sh
just run
```

The window contains only an in-memory sample document. Controls are provisional:

- `i`: enter insert mode, appending at the end of the buffer.
- Type printable ASCII; Enter inserts a newline, Backspace removes the last byte.
- Escape: leave insert mode or dismiss the popup.
- Space or F1 in normal mode: show commands.
- Ctrl + / Ctrl -: increase/decrease font size (12–36px); Ctrl 0 resets to 20px.
- `1` / `2` in the popup: select compact/wide relative popup geometry.
- Close the window to exit. **All edits are discarded on exit.**

No file loading/saving, undo, selection-first editing, TUI, SSH, plugins, or layout
file parsing exists yet. Capacity is 8191 bytes; additional or non-ASCII input is
ignored. SDL_ttf renders antialiased text with real newlines, 1.5× line spacing,
and display-scale-aware font sizing. Zed Mono is preferred when installed, with
Noto Sans Mono as fallback. Set `DNA_FONT=/absolute/path/font.ttf just run` to
choose another font. No font files are bundled. Unicode editing and input-method
composition remain required; the input buffer still accepts only ASCII.

## Checks

```sh
just smoke
# Also exercise the real desktop driver and exit automatically:
LD_LIBRARY_PATH="$PWD/build/deps/install/lib" DYN_EDITOR_SMOKE=1 ./build/dna-debug
```

The smoke path creates a real SDL window/renderer using its headless driver,
pushes SDL keyboard and text events through the application's actual event loop,
and checks resulting text, mode, popup, and layout state. It also asserts that
the initial document lays out over multiple lines and that enlarging the font
increases its rendered height. Debug and release are
both exercised. This does not replace manual physical keyboard/IME testing.

The document owns fixed backing storage. Text from SDL events is copied before
reading the next event. Window and renderer cleanup is registered immediately;
text objects are destroyed before their text engine/font, and the renderer is
destroyed before the window and SDL shutdown. Drawing is immediate
mode on relevant events; the application waits when idle.

SDL bindings live in `src/platform/`. Their event layouts currently target the
64-bit SDL3 ABI. `tests/abi.c` checks layout assumptions against installed headers;
application smoke checks verify corresponding Dyn sizes and event handling.

## Repository

Non-colocated jj, local only. No GitHub remote or publication has been created.
The project name DNA is provisional. The production plugin/runtime and rendering
architecture remain design work; this small experiment is deliberately disposable.
