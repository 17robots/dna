# Plugin sandbox design

Status: proposal, not implemented. Today a plugin is a separate process that
runs with the user's full filesystem and network access; DNA's permissions
(`document.read`, `document.write`, `buffer.create`) only govern the editor
API. This document describes how to confine the process itself.

## Goals

- A plugin can read its own installation directory and the data DNA sends it
  over stdin, and nothing else, unless its manifest asks for more and the user
  grants it in the existing permission review.
- No network access unless granted.
- A denied operation fails inside the plugin (`EACCES`, `EPERM`); it never
  kills the editor or needs a prompt mid-session.
- The protocol stays newline-delimited JSON over stdin and stdout, so existing
  plugins keep working unchanged when they need no extra access.

## Manifest additions

```json
{"name":"lint","executable":"lint","permissions":["document.read"],
 "sandbox":{"read":["~/.config/lint"],"write":[],"network":false}}
```

- `sandbox.read` and `sandbox.write` list extra paths (absolute or `~/`).
  The project directory is a separate permission, `project.read`, because a
  linter often needs it and a formatter usually does not.
- `sandbox.network` is a boolean; there is no host allow-list in v1.
- A manifest without `sandbox` gets the default: its installation directory
  read-only, a private temporary directory read-write, no network.
- The permission review shows every requested path and network access next to
  the API permissions. Grants are reviewed on each load, as today.

## Linux

Applied in the child between `fork` and `exec` (`src/native/dyn/process.dyn`),
so it covers the plugin and everything it starts:

1. **Landlock** (kernel 5.13+; ABI 4 on 6.7+ adds TCP rules). Create a ruleset
   handling every filesystem access right, add rules for the installation
   directory (read, execute), the private temp directory (read, write) and each
   granted path, then `landlock_restrict_self`. With ABI 4, also handle
   `LANDLOCK_ACCESS_NET_CONNECT_TCP` and `BIND_TCP` when network is denied.
2. **seccomp** as a backstop for older kernels: deny `socket` for `AF_INET`
   and `AF_INET6` when network is denied (`AF_UNIX` stays for stdio-style
   helpers), deny `ptrace`, `process_vm_*`, `mount`, `bpf`, `keyctl`, and
   `perf_event_open`.
3. `PR_SET_NO_NEW_PRIVS` before either, as both require.
4. Resource limits (`RLIMIT_AS`, `RLIMIT_NPROC`, `RLIMIT_CPU`) from the
   existing plugin timeouts.

When Landlock is unavailable (old kernel, disabled LSM), DNA says so in the
permission review ("filesystem confinement unavailable on this system") and
loads the plugin only after an explicit second confirmation. It never claims a
sandbox it did not apply.

## macOS

Run the plugin through `sandbox_init` with a generated SBPL profile (the same
mechanism `sandbox-exec` uses): `(deny default)`, `(allow process-exec)` for
the executable, `(allow file-read*)` for the installation directory and
granted paths, `(allow file-write*)` for the temp directory and granted write
paths, and `(allow network*)` only when granted. The API is deprecated but is
what the system's own tools still use; if it fails, fall back as on Linux.

## Windows

Create the process in an **AppContainer** (`CreateAppContainerProfile`, then
`SECURITY_CAPABILITIES` in `STARTUPINFOEX`). An AppContainer has no file or
network access by default. Grant the installation directory and each granted
path to the container SID with `SetNamedSecurityInfo`, and add the
`internetClient` capability only when network is granted. Put the process in a
job object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and memory limits so it
and its children end with the editor.

## Testing

- A test plugin that tries, in order: read its own directory (must succeed),
  read `~/.ssh` (must fail), write to the project (must fail without a grant),
  open a TCP connection (must fail without a grant), and reports each result.
  Run it with and without grants on each platform in CI.
- Existing plugin tests must pass unchanged with the default sandbox.

## Phases

1. Linux Landlock + seccomp with the default policy and `project.read`.
2. Manifest `sandbox` paths and network, shown in the permission review.
3. macOS and Windows, alongside their editor releases.
