# Architectural Decisions

## 2026-07-09

### SaveCloud owns the canonical save copy

Decision

Games use working copies.

The SaveCloud Library stores the canonical save.

Reason

Allows:

- Version history
- Offline synchronization
- Multiple storage providers
- Conflict detection

Launcher Integration Finding (Acceptance Test)

Manual execution of Eden with the current command line reproduces the same behavior observed through SaveCloud: the emulator launches but does not immediately start the selected game. Since the behavior is identical outside SaveCloud, this is not considered a LaunchService defect. Emulator-specific launch semantics should be encapsulated by the Eden adapter in a future launcher integration milestone.

Status

Accepted

Decision

Adapters are responsible only for save discovery
and save validation.

They never launch games.

Decision

Launch methods are encapsulated by launchers.

Launchers are independent of emulators.

---

## 2026-07-27

### Storage configuration belongs to the installation

Decision

Storage backend and storage root move from `GameManifest` into
`InstallationConfig`, stored in `config.json`.

Reason

Every registered game held an identical `storage_backend` value.
Changing provider meant editing every manifest, and nothing prevented
them drifting apart into a state with no meaningful interpretation.

Manifests carrying the old field still load; the value is ignored, and
`init` adopts it as the installation default when every manifest
agrees. When they disagree, nothing is adopted - picking one
arbitrarily could silently redirect a game's saves.

Status

Accepted

---

### Save identity is content, not modification time

Decision

Saves are identified by a SHA-256 checksum over the directory tree,
covering each file's relative path and contents.

Reason

Timestamps are unreliable across devices, filesystems, and copy
operations; a plain copy can produce a "newer" file with identical
contents. Including relative paths means a rename is detected as a
change, which content-only hashing would miss.

Status

Accepted

---

### Conflicts are detected against a recorded ancestor

Decision

`GameRuntime` records `last_sync_checksum` at every successful
synchronization. Synchronization compares three values: this device's
save, the backend's save, and that ancestor.

Reason

Comparing only two sides cannot distinguish "the remote advanced" from
"this device advanced" - both look like a difference. The ancestor is
what makes a one-sided change safe to apply automatically and a
two-sided change identifiable as a conflict.

Where no ancestor exists, the difference is treated as a conflict
rather than resolved by guessing.

Status

Accepted

---

### A conflict aborts rather than choosing

Decision

Synchronization refuses to resolve a conflict on its own. `--keep-local`
and `--keep-remote` make the choice explicit, and the losing save is
written to version history before being replaced.

Reason

Both sides represent real play time. Only the person who played knows
which matters. Last-write-wins would silently discard a session.

`play` extends this: an unresolved conflict prevents launching, because
playing would build new progress on top of a contested save.

Status

Accepted

---

### Capturing a save is independent of any storage backend

Decision

`SyncService.capture()` imports the working save into the library and
versions it without involving a backend. `upload()` calls it, and
`AutoSyncService` calls it directly before attempting to push.

Reason

An earlier implementation resolved the backend first, so a session
played while storage was unreachable was never captured at all - the
save existed only in the game's working directory, where the next
session would overwrite it. The library is the source of truth whether
or not a backend can be reached.

Status

Accepted

---

### The Syncthing backend refuses folders Syncthing does not manage

Decision

The Syncthing backend reports itself unavailable unless the storage
root contains Syncthing's `.stfolder` marker, and never creates the
root itself.

Reason

Creating a missing directory would produce somewhere that looks correct
and silently never replicates. Failing loudly is better than a backup
that does not exist.

Status

Accepted

---

### Single-action commands are commands, not sub-applications

Decision

`cli.py` registers plain functions with `app.command()`. Only `config`,
which has genuine subcommands, is mounted with `add_typer()`.

Reason

Mounting a single-action command as a sub-Typer makes it a Click group,
so anything following its positional argument is parsed as a
subcommand. `savecloud sync <game> --check` failed with "No such
command". The same ambiguity ruled out giving `pair` both a default
action and a `list` subcommand; it takes a `--list` flag instead.

Status

Accepted

---

### Tests run against a temporary installation

Decision

Filesystem paths are resolved at call time from `SAVECLOUD_HOME` rather
than fixed at import. An autouse fixture points every test at a
temporary directory.

Reason

The previous test scripts wrote to the developer's real installation
and to `~/SaveCloudRemote`, so running them mutated live data and left
tests depending on each other's leftovers. Runtime resolution also
gives the installation-wide storage root somewhere to take effect.

Status

Accepted
