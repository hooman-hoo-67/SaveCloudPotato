# SaveCloud Command Reference

Every command delegates to a service. Nothing below implements a
workflow itself.

---

## Machine-readable output

### `savecloud --json COMMAND ...`

Emit a JSON document instead of prose. The option goes before the
command, since it applies to whichever one follows.

```
savecloud --json list
savecloud --json sync pokemon-scarlet --check
savecloud --json doctor --verbose
```

Supported by `list`, `info`, `history`, `sync`, `config show`,
`doctor`, and `pair --list`.

One document per command, on stdout alone. Progress goes to stderr, so
stdout can be parsed without filtering it.

Every document carries `ok`. A failure keeps the exit code it would
have had and reports the reason in the same shape, so a caller can
check the status without parsing anything:

```json
{
  "ok": false,
  "game_id": "pokemon-scarlet",
  "action": "conflict",
  "error": "Both this device and the remote have changed.",
  "resolutions": ["keep-local", "keep-remote"]
}
```

`--json` changes how a command reports, never what it does. A flag
rather than a separate set of commands, because a GUI and a person ask
the same questions and two code paths answering them would drift.

---

## Installation

### `savecloud init`

Create the SaveCloud filesystem and `config.json`.

Safe to run repeatedly. If an installation predates Milestone 8 and its
manifests all name the same storage backend, that value is adopted as
the installation default.

---

## Configuration

### `savecloud config show`

Display the active configuration and whether its backend is reachable.

### `savecloud config backend [NAME]`

Without an argument, list available backends and mark the active one.
With an argument, switch to it.

```
savecloud config backend syncthing
```

### `savecloud config root [PATH]`

Show or change the directory the storage backend uses.

```
savecloud config root ~/Sync/SaveCloud
```

### `savecloud config retention [N]`

Show or change how many historical versions are kept per game.

```
savecloud config retention 2      # default
savecloud config retention 0      # keep every version
```

Counts history only, so `2` leaves three saves in total: the current
one plus two previous.

Setting the window applies it immediately, in the library and in
storage:

```
✓ Keeping 2 versions per game.
  test_zelda: removed 5 versions locally
  test_zelda: removed 5 versions from storage
```

Versions are otherwise trimmed as they are created, which never reaches
a game whose save has not changed. Without applying it here, lowering
the window would appear to do nothing until the next play session.

Storage is trimmed as well as the library. If only one side pruned, a
device still holding older history would keep re-uploading what the
other had just removed.

Unreachable storage is reported, not fatal. The setting is saved and
the library is trimmed regardless; storage catches up on the next
upload.

### `savecloud config provider [NAME]`

Set up credentials for a storage backend. Defaults to the active one.

```
savecloud config provider dropbox
```

Backends that need no credentials say so and do nothing. Each device
needs its own setup, because credentials are never synchronized.

### `savecloud config validate`

Verify the configured backend is usable. Exits non-zero if not, which
makes it suitable for a startup check.

---

## Game Management

### `savecloud register`

Register a game interactively. Prompts for a display name, game ID,
launch type, platform, adapter, launcher, and launch command, then
locates and validates the save directory through the chosen adapter.

Storage backend is not asked for. It is installation-wide.

### `savecloud unregister GAME_ID`

Remove a game's registry entry, library, and local device profile.

### `savecloud list`

List registered games.

### `savecloud info GAME_ID`

Show a game's configuration, runtime state, and this device's profile.
A game that is registered but not set up here says so and names the
command that adopts it.

### `savecloud autosync GAME_ID [on|off]`

Show or change whether **this device** synchronizes a game
automatically.

```
savecloud autosync pokemon-scarlet          # show
savecloud autosync pokemon-scarlet off      # this device stops
```

Off means `play`, `wrap`, and a bare `savecloud sync` skip the game on
this machine. Naming it explicitly still works, since the switch
governs automatic behaviour rather than permission.

The setting lives in the device profile, so it is never synchronized:
turning it off on a laptop changes nothing for the desktop it shares
saves with. `sync_enabled` on the manifest is the other switch - it
travels with the game and means "managed at all", so a game disabled
there is disabled everywhere.

---

## Save Management

### `savecloud import GAME_ID`

Copy the working save into the library.

### `savecloud export GAME_ID`

Copy the library's current save to the working save directory.

### `savecloud snapshot GAME_ID`

Create a version from the current save.

### `savecloud history GAME_ID`

List available versions.

### `savecloud restore GAME_ID VERSION`

Restore a version. The save being replaced is preserved as a new
version first, so a restore is itself reversible.

---

## Synchronization

### `savecloud sync [GAME_ID]`

Synchronize a game, or every game when the ID is omitted.

| Option | Effect |
|--------|--------|
| `--check` | Report what would happen, change nothing |
| `--keep-local` | Resolve a conflict in favour of this device |
| `--keep-remote` | Resolve a conflict in favour of the remote |

Without a resolution flag a conflict aborts with a non-zero exit code
and nothing is overwritten.

```
savecloud sync                        every game
savecloud sync pokemon-scarlet        one game
savecloud sync pokemon-scarlet --check
savecloud sync pokemon-scarlet --keep-local
```

### `savecloud upload GAME_ID`

Capture the working save and push it, regardless of what the remote
holds.

### `savecloud download GAME_ID`

Pull the remote save and publish it to the working save directory,
regardless of local changes.

`upload` and `download` are deliberate overrides. `sync` is the command
that decides.

### `savecloud pair [GAME_ID]`

Adopt a game that exists in storage onto this device.

| Option | Effect |
|--------|--------|
| `--list` | Show what storage holds and its state here |

Omitting the game ID prompts with the games not yet paired. Pairing
downloads the registry and library, then asks only for what cannot be
synchronized: the local save location, launcher, and launch command.

---

## Diagnostics

### `savecloud doctor`

Check this installation for problems.

| Option | Effect |
|--------|--------|
| `--verbose` / `-v` | Show checks that passed, not only problems |
| `--strict` | Exit non-zero on warnings as well as errors |

Checks the installation, the configured backend, every registered
game's registry, library, adapter, device profile, launcher, and
runtime state, and reports data left behind by games that are no longer
registered.

Also asks the active backend for anything only it can know about. For
Syncthing that means `*.sync-conflict-*` files, which SaveCloud never
reads and would otherwise sit unnoticed.

Every problem is reported with the command that fixes it.

```
✗ Storage backend
    /home/user/Sync/SaveCloud is not a Syncthing folder (no .stfolder
    marker). Share it in Syncthing first, or switch to the local backend.

    → Saves are still captured locally, but nothing will reach your
      other devices until this is fixed.
```

Exits `1` if anything is broken, `0` if only warnings were found. Use
`--strict` in a script that should treat a pending upload as failure.

---

## Gameplay

### `savecloud wrap GAME_ID -- COMMAND...`

Run a command supplied by Steam, with synchronization around it.

This is the inverse of `play`: Steam starts SaveCloud and hands it the
command it would otherwise have run. Put it in the game's **Launch
Options** in Steam:

```
savecloud wrap hollow-knight -- %command%
```

Steam replaces `%command%` with the full invocation, including the
Proton runtime for a Windows game. SaveCloud synchronizes, runs it,
waits for it to exit, and captures the save.

| Option | Effect |
|--------|--------|
| `--keep-local` | Resolve a conflict in favour of this device |
| `--keep-remote` | Resolve a conflict in favour of the remote |

SaveCloud's own options must come **before** the game ID, since
everything after it belongs to the game:

```
savecloud wrap --keep-local hollow-knight -- %command%
```

The game's exit code is passed through, so Steam reports what actually
happened.

### `savecloud play GAME_ID`

Synchronize, launch, wait for exit, capture the session, and upload.

| Option | Effect |
|--------|--------|
| `--keep-local` | Resolve a pre-launch conflict in favour of this device |
| `--keep-remote` | Resolve a pre-launch conflict in favour of the remote |

An unresolved conflict prevents launching: playing would build new
progress on top of a save that is already contested.

`play` refuses launchers that cannot report when the game exits - the
Steam launcher among them, since `steam -applaunch` returns as soon as
Steam has been told to start the game. Capturing then would record the
save from *before* the session. Use `wrap` for those.

Unreachable storage does not prevent playing. The session is captured
into the library and marked pending, and the next successful sync
uploads it.

Every session is captured whatever the exit code. A game closed by
Steam's Stop button or Gaming Mode's Exit Game is terminated with
SIGTERM, which counts as an ordinary exit and publishes normally. Any
other non-zero exit is captured and marked pending but not published,
so a crashed session cannot reach your other devices unasked:

```
! Game exited with code 1. The save was kept locally but not
  uploaded; run `savecloud sync hollow-knight` to publish it.
```

`wrap` forwards those signals to the game rather than dying on them,
so the game flushes its save and SaveCloud is still alive to capture
it. SIGKILL cannot be survived; if Steam escalates, the session is
lost.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Command failed (unregistered game, conflict, unavailable storage) |
| 2 | Usage error (contradictory options) |
| 127 | For `wrap`, the command could not be executed |
| other | For `play` and `wrap`, the game's own exit code |

---

## Environment

| Variable | Effect |
|----------|--------|
| `SAVECLOUD_HOME` | Override the installation directory |
| `SAVECLOUD_STEAM_ROOT` | Override Steam's location |

---

## Storage Backends

| Backend | Needs setup | Notes |
|---------|-------------|-------|
| `local` | No | A directory on this machine or a mounted drive |
| `syncthing` | No | A folder Syncthing replicates; refuses one it does not manage |
| `dropbox` | Yes | `savecloud config provider dropbox` |

For Dropbox, `config root` names a folder inside Dropbox rather
than a local path. Only the last component is used, so a root of
`~/SaveCloudRemote` becomes `/SaveCloudRemote` in Dropbox.
