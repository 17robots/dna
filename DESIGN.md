# DNA — native modal editor design

Status: agreed direction; working project name: DNA. This document describes a new
editor, separate from the Dyn compiler and dyn-editors integrations. The browser
layout sketch in build/editor-layout-prototype is disposable and does not specify
the production UI or implementation technology.

## Experience

The default screen contains only the current file buffer. No persistent toolbar,
sidebar, layout selector, tabs, or required status line. Supporting views appear
as popup buffers when invoked by a keybinding or command. Optional arrangements
can keep views visible without assigning any view a permanent sidebar role.

The editor is modal. Start with Helix-style selection-first behavior; design the
mode interface to support a later Vim-style profile. Profiles govern editing
semantics, including directory buffers, not just keybindings. Compatibility with
existing Vim/Helix plugins or configuration is not a first-version goal.

Every operation is keyboard-accessible through commands. Frequent operations get
shortcuts; every command is discoverable through the palette and can be bound.
Final default bindings remain to be selected. The palette offers descriptions,
current bindings, argument entry, contextual availability, and explanations when
a command cannot run. Layout switching is visible as a palette command, not as
persistent screen chrome.

## State and placement

- Buffer: document contents or another model, such as directory entries or search
  results. Document edit transactions and undo history belong to the document.
- View: a cursor, selections, scroll position, and interaction state for a buffer.
- Placement: a view's location and relative size—popup, split, or full area.

Dismissing a popup closes its presentation, not its underlying document or pending
operations. Focus returns to the invoking view with its selection intact. Nested
popups unwind one level at a time. Closing an unsaved document is a separate action
that requires a save/discard decision.

## Layouts and configuration

Use a simple declarative settings file and separate named layout files. The final
syntax is undecided; JSON in the prototype is only an interchange experiment.
Users can load/switch layouts through the palette or bind a named layout directly.
Interactive placement changes can be saved to a layout file.

Layout files describe roles (current document, directory, search, diagnostics),
relative sizes, and arrangements, rather than hard-coded file paths. Session state
records open files, navigation positions, and other automatically maintained data
separately from user-authored preferences.

Switching layouts preserves buffers, selections, undo history, and unsaved edits.
Validate a layout before applying it; an invalid file leaves the active layout
intact and produces an actionable error. Missing optional view providers must not
prevent access to documents. When minimum sizes cannot fit, use a simpler
arrangement while preserving the requested layout for a larger screen.

## Core keyboard workflows

The following are command sequences, not final shortcut assignments:

1. Open project → invoke Directory → navigate/select using the active editing
   profile → open file → directory popup dismisses → file receives focus.
2. Invoke Directory → queue create/rename/move/delete operations → invoke Apply
   → inspect operation preview → validate collisions/external changes → apply.
   Closing the popup preserves pending operations. Explicit discard clears them.
3. Invoke Command Palette → filter commands → choose command → supply arguments
   where needed → execute → focus returns to the appropriate view.
4. Invoke Command Palette → Switch Layout → choose a named file → validate and
   apply placement without modifying document state.
5. Invoke a supporting buffer → invoke Change Placement → choose popup, split,
   or full area → retain the same buffer and view state.
6. Edit → undo/redo transactions → explicit Save. Crash-recovery snapshots are
   separate from saves to the original file.

Filesystem actions are not automatically ordinary text undo. Decide deletion
recovery before enabling delete. Before applying a batch, check destinations,
unsaved affected documents, and external changes; report partial failures honestly
rather than assuming multiple filesystem operations are atomic. Successful renames
update affected open-document paths.

## Implementation

Native Dyn application, with graphics/input library bindings and an immediate-mode
GUI. No browser runtime, Electron, HTML, or CSS in the production application.
SDL3 and SDL_ttf are candidates, not a committed dependency choice; prototype Dyn
bindings before selecting them. Use a small C bridge only where the ABI requires it.

The GUI derives its presentation from durable editor/view state when a redraw is
needed. Immediate mode does not require continuous idle rendering. A TUI frontend
shares documents, transactions, commands, modes, and layout intent with the GUI.
Build the first native vertical slice on Linux, then bring the same workflow to
the TUI. Keep platform interfaces suitable for Windows and macOS.

The small core owns document integrity, transactions/undo, command dispatch, input
routing, scheduling, plugin lifecycle, and rendering/view primitives. User-facing
features—including the palette, directory buffers, editing profiles, language
support, and language tools manager—are bundled modules behind explicit interfaces.
Bundled features should exercise the public extension interfaces. Compile them
into the application initially; modularity does not require dynamic loading.

The language tools installation mechanism is built in, but tool installation is
user-selected. Custom language definitions must work locally without publishing
or writing a plugin: file patterns, grammar, server/formatter commands, indentation,
and root detection. Keep generated package records out of user settings.

## Responsiveness and memory

Measure startup, input-to-display latency, idle CPU, large-file behavior, and total
session memory (including external tools). Set numerical budgets after measuring
the first vertical slice; no performance claims are established yet.

- Activate language support and external tools only when needed.
- Batch rendering and highlighting work; avoid plugin calls per displayed glyph.
- Keep searches, tooling, and remote I/O off the input/rendering path.
- Give document data explicit lifetimes; frame scratch storage must not escape
  into documents, undo history, or asynchronous jobs.
- Avoid full document copies for every plugin; define bounded read access and
  versioned edits through the core.
- Recover from tool failures without losing documents. Native in-process plugins
  are not crash-isolated merely because they use a plugin interface.

## Remote sessions

Support a local GUI connected to an editor service through an existing SSH tunnel.
File operations, searches, and language tools run beside the remote project.
The local GUI retains sufficient document/view state for responsive interaction.
The tunnel is transport, not synchronization: document versions, edit ordering,
reconnection, conflicts, and recovery still require a protocol.

A TUI can also run directly on the remote machine through an ordinary SSH session.
Both paths must preserve unsaved work across recoverable disconnects. Implement
remote sessions after reliable local editing; do not let the initial interfaces
assume all services share the GUI process.

## First-version boundary and deferred choices

First native vertical slice: window, file buffer, one modal profile, popup directory
buffer, command palette, relative layout switching, undo/redo, explicit save, and
crash recovery. Follow with the equivalent TUI workflow before building a broad
plugin ecosystem. Handle UTF-8 safely from the beginning and exercise cursor and
selection boundaries, composition input, and font fallback early.

Deferred: project name; final shortcuts/config syntax; document storage structure;
font/text-layout backend; deletion recovery mechanism; third-party plugin language,
packaging, permissions and isolation; remote synchronization protocol; full Vim
compatibility scope; complete accessibility and platform integration design.

Next implementation step: choose a separate project home and build a minimal Dyn
window/input/text-binding experiment. Use its results to select the platform layer,
then implement the first keyboard workflow above. Do not expand the compiler repo
with editor application code.
