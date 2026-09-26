# Plugin protocol v1

Plugins are separate local processes. Dyn, Rust, Go, or any language that can
read/write newline-delimited JSON can implement one. This API is experimental.

## Try the Dyn example

```sh
dyn build examples/plugins/uppercase --release --output examples/plugins/uppercase/uppercase
```

In DNA:

```text
:plugin-install /absolute/path/dna/examples/plugins/uppercase/plugin.json
:plugin-load uppercase
```

Review the permissions and press Enter to start, or Escape to cancel. Search the
palette for `uppercase: Uppercase buffer`. Its replacement is previewed before
Enter applies it; Escape keeps the original. `u` undoes the accepted edit.

`:plugin-load /path/plugin.json` runs directly from a development directory.
`:plugin-install /path/plugin.json` copies the manifest and executable to the
config directory's `plugins/<name>/`. Running it again installs an update using
an atomic directory swap and retains the previous version in a hidden directory.
`:plugin-update <name>` recopies the original source manifest and executable,
then offers a fresh permission review. Keep that source available; an unavailable
source leaves the installed version intact. Installation never executes code. Additional resources/shared libraries
are not copied; package these into the executable or use development loading.

`:plugins` separates running, installed, and available catalog entries.
`:plugin-disable <name>` stops one; `:plugins-disable` stops all.
`:plugin-remove <name>` stops it and moves its managed installation into a hidden
`.removed-<name>-*` directory beside the other installations, preserving its files.
`:plugin-log` shows the latest notice/failure and the final 4 KiB of stderr. Plugins do not auto-start on opening projects.

## Local discovery

Copy [plugin-catalog.example.json](plugin-catalog.example.json) beside config.toml
as `plugin-catalog.json`. Map names to absolute manifest paths. Then use
`:plugins` to discover entries and `:plugin-install uppercase` to install one.
Installation copies files without executing them; `:plugin-load uppercase` opens
permission review. This is a user-owned local catalog, not a public marketplace
or automatic network updater. Permission grants are reviewed again on each load.

## Manifest

```json
{"name":"uppercase","executable":"uppercase","permissions":["document.read","document.write"]}
```

The executable is a regular executable file beside the manifest. Supported API
permissions are `document.read`, `document.write`, and `buffer.create`. Unknown
permissions are rejected. Permissions govern the **editor API**; processes run
with your OS account's filesystem/network permissions. Only load trusted code.
Process separation protects the editor from plugin crashes; it is not an OS sandbox.

## Messages

UTF-8 JSON objects, one per line on stdin/stdout, at most 524,287 bytes per line.
Stdout is reserved for protocol messages. Stderr is drained separately and is
retained in a bounded crash log. Initialization and commands have a five-second response
deadline. Invalid messages, denied permissions, oversized queues, and process
exit disable that instance without closing the editor.

The host sends `{"type":"initialize","version":1}`. Register commands, then reply:

```json
{"type":"command","name":"Uppercase buffer"}
{"type":"ready"}
```

The command appears in the palette prefixed with the plugin name. Configuration
can bind that same palette command:

```toml
[keys.space]
"u" = "uppercase: Uppercase buffer"
```

Invocation includes the current buffer and revision. `text` is present only with
`document.read`. Document requests in v1 are limited to 65,535 bytes.

```json
{"type":"command","name":"Uppercase buffer","buffer":0,"revision":12,"text":"hello"}
```

Supported responses:

```json
{"type":"notice","text":"Shown by :plugin-log"}
{"type":"buffer","text":"A new scratch buffer, requires buffer.create"}
{"type":"replace","buffer":0,"revision":12,"text":"HELLO"}
{"type":"done"}
```

`replace` requires `document.write` and targets the buffer identity/revision
captured when the command was invoked. The host rejects stale edits and rechecks
on confirmation. Edits are undoable and do not save files. Another active prompt
causes an edit/buffer request to be rejected rather than interrupting it. Large
replacement previews display their beginning; v1 has no structured range edits.

Readers also receive `event` messages named `buffer-opened` and `buffer-saved`,
with `buffer` and `revision`. Ignore events that are not relevant. Up to eight
processes and 32 registered commands are supported. Commands use the existing
palette, keybindings, and popup system; custom rendering and a public registry
are outside v1.

## Versions and rollback

New manifests can include `"version": "0.1.0"` and `"api_version": 1`.
Unsupported API versions are rejected before execution. Older manifests without
these fields remain compatible with API 1. The version is displayed during
permission review. `:plugin-rollback NAME` atomically swaps the active managed
installation with its newest retained version, then opens permission review.
The replaced version is retained, so another rollback can restore it. Rollback
never starts code automatically. Both the Dyn uppercase example and the protocol
remain language-independent; any executable that speaks the documented messages
can be used.
