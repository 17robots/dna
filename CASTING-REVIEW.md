# Casting review

Status: proposal for review. Nothing here has been applied.

DNA's `src/` (44k lines) contains 1,433 `#cast(` expressions on 1,152 lines:
about one line in 38. 186 lines contain two or more. Most casts are not
conversions the program needs; they come from a few type choices that force a
conversion at every use. This document lists those choices and what to change.

Counts were taken with `grep` on 2026-10-09 and are approximate.

## Breakdown

| Target | Count | Main cause |
|---|---|---|
| `#cast(usize)` | 379 | lengths and counts stored as `i32`/`u32` |
| `#cast(f32)` | 281 | screen geometry stored as `i32`, drawn as `f32` |
| `#cast(i32)` | 164 | the reverse of both of the above |
| `#cast(u32)` | 156 | C API lengths, bit masks |
| `#cast(*T)` | 142 | untyped arena pushes, pointers back from C |
| `#cast(rawptr)` | 140 | passing typed pointers to C (`sdl.free`, userdata) |
| `#cast(u8)` | 74 | colour channels, ASCII digits |

## 1. Geometry: one type for screen coordinates

**Problem.** Layout rectangles and sizes are integers, but SDL draws with
floats, so drawing and hit-testing code converts every field:

```dyn
// mouse.dyn:22
if pane.used && !pane.branch && x >= #cast(f32) rect.x && y >= #cast(f32) rect.y &&
    x < #cast(f32) (rect.x + rect.width) && y < #cast(f32) (rect.y + rect.height) {
```

`#cast(f32) width` alone appears 46 times and `#cast(f32) height` 36 times.
Heaviest files: `mouse.dyn` (25), `ui.dyn` (21), `picker_view.dyn` (20),
`platform/tui.dyn` (15), `panes.dyn` (14), `diagnostic_view.dyn` (14),
`ime.dyn` (13), `dialog_view.dyn` (13), `placement.dyn` (12).

Integer geometry fields include `view.dyn:25-26`, `mouse.dyn:161-162`,
`typography.dyn:123-124`, `animation.dyn:20-21`, `text/text.dyn:114-120` and
`platform/platform.dyn:73-74`.

**Change.** Keep GUI geometry in `f32` everywhere (rects, sizes, positions,
scroll offsets). Convert to integers only where an integer is the real
meaning:

- the TUI grid (`platform/tui.dyn` rows and columns stay integers);
- `sdl.PixelRect` for clipping, converted once in one helper
  (`pixel_rect(r: Rect) sdl.PixelRect`);
- cell/line indexes derived from a position (`floor` once, at the hit test).

**Expected effect.** Removes most of the 281 `f32` casts and many of the
`i32` casts in the opposite direction.

## 2. Lengths: `usize` inside DNA, C types only at the boundary

**Problem.** Lengths and counts that come from C APIs keep their C type
(`length: i32` in `platform/platform.dyn:126` and `text/text.dyn:114`;
`rows, cols, history_count: i32` in `native/dyn/terminal.dyn`), so every
index and slice needs a cast:

```dyn
// native/dyn/terminal.dyn:78
_ = copy(#cast(*u8) &t.history[..480000][base], #cast(*const u8) cells,
    #cast(usize) count * #sizeof(TermCell))
```

Heaviest files: `native/dyn/terminal.dyn` (62), `native/dyn/predicates.dyn`
(36), `native/dyn/syntax.dyn` (29), `operations.dyn` (17),
`buffer/buffer.dyn` (15).

**Change.** Store lengths, counts and indexes as `usize` in DNA's own structs.
The `extern fn` declarations keep the exact C types; the thin wrapper around
each one converts once, on the way in and on the way out. For libvterm, that
means `Terminal.rows/cols/history_count` become `usize`, and only the
`term_*` call sites convert.

**Expected effect.** Removes most of the 379 `usize` casts and a large part of
the `u32`/`i32` ones. Conversions move to `native/` wrappers, where a reviewer
expects them.

## 3. Changes that depend on the compiler

These need a Dyn release first. They are agreed in principle.

### 3a. Implicit `*T` to `rawptr`

Dyn will convert a typed pointer to `rawptr` implicitly (the reverse stays
explicit). Then these become plain calls:

```dyn
defer sdl.free(#cast(rawptr) incoming)   // before
defer sdl.free(incoming)                 // after
```

There are 58 `free(#cast(rawptr) ...)` calls and about 80 other `rawptr`
casts, mostly userdata arguments in `native/dyn/syntax.dyn` (16),
`sync.dyn` (13), `process.dyn` (13), `notify.dyn` (12), `memory.dyn` (11) and
`terminal.dyn` (10). After the release, delete them mechanically and run the
tests.

### 3b. Literal casts and numeric conversions (no compiler change)

Integer literals already take their type from the expression, and Dyn
already converts implicitly when no value can be lost (wider integer of the
same sign, unsigned into a wider signed type, integers that fit a float's
precision, `f32` to `f64`). Decided 2026-10-09: this stays as it is. Lossy
conversions (`i32` to `f32`, `i32` to `usize`, narrowing, float to integer)
keep requiring `#cast`.

The 48 casts on literals are really sign or narrowing casts on the other
operand, so they disappear with the type changes in sections 1 and 2:

```dyn
offset := #cast(usize) 32 + index * 64 + selected * 2   // before (index: i32)
offset := 32 + index * 64 + selected * 2                // after (index: usize)
```

Casts that only widen without loss (for example `u32` to `usize`) are already
unnecessary and can be deleted now.

### 3c. Typed arena pushes

Today 27 pushes cast the result to a pointer type and 23 slice a `*u8` out of
a push:

```dyn
created_cache := #cast(*UiTextCache) mem.arena_push_uninit_or_panic(
    &typography.ui_owner, #sizeof(UiTextCache), #alignof(UiTextCache))
bytes := (#cast(*u8) mem.arena_push_uninit_or_panic(&work.arena, snapshot_size, 1))[..snapshot_size]
```

Whatever std provides (typed `mem.push(T, &arena)` or a byte-slice helper
`mem.push_bytes(&arena, n)`), these 50 sites should move to it. Until then a
small DNA helper for byte buffers removes the 23 slice forms now:

```dyn
fn push_bytes(arena: *mem.Arena, count: usize) []u8 {
  return (#cast(*u8) mem.arena_push_uninit_or_panic(arena, count, 1))[..count]
}
```

## 4. Small cleanups

- **Zeroing a value** (8 sites): replace
  `mem.zero((#cast(*u8) &slot.diagnostics)[..#sizeof(Diagnostics)])` with
  `slot.diagnostics = {}` or a `zero_value` helper.
- **Pointer arithmetic for a header size** (`ui_cache.dyn:88`):
  `#cast(usize) &created_cache.bytes[0] - #cast(usize) created_cache` should
  be a named constant or a separate header struct.
- **Colour channels** (`animation.dyn:148`, `theme.dyn:59`): store theme
  colours as `f32` channels once, rather than dividing `#cast(f32) c / 255.0`
  at every vertex.
- **ASCII digits** (`settings_view.dyn:11`): use the std integer formatter
  instead of building digits with `#cast(u8) (#cast(usize) 48 + ...)`.

## What stays

After the changes above, roughly 500 casts remain. These are real
conversions: float to integer for pixel snapping, narrowing to C types inside
`native/` wrappers, and pointers coming back from C as `rawptr`. They should
stay explicit.

## Build script: allow parallel builds

Not about casts, but part of the same review list. `scripts/compile.py` adds
`--jobs 1` to every `build`/`run` and caps memory at 2048 MiB
(`DNA_BUILD_MEMORY_MB`). That made sense when every module job re-analyzed
the whole program. From Dyn preview 18 the program is analyzed once and
large modules compile in parallel chunks: a debug build takes 0.57 s on all
cores versus 1.50 s with `--jobs 1`.

**Change.** Stop forcing `--jobs 1`; let the compiler pick the worker count,
or pass a configurable `DNA_BUILD_JOBS`. Measure peak memory of a full build
with the default job count first, and keep or raise the 2048 MiB cap based on
that measurement.

## Suggested order

1. Geometry to `f32` (largest, purely DNA, no compiler dependency).
2. Lengths to `usize`, starting with `native/dyn/terminal.dyn`.
3. `push_bytes` helper and the small cleanups.
4. Now: delete casts that only widen without loss (3b).
5. After the next Dyn release: delete `rawptr` casts (3a).

Check each step with `just test` and `just smoke`. None of it should change
behaviour.
