# SaveCloud Command Reference

Every command delegates to a service. Nothing below implements a
workflow itself.

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

### `savecloud play GAME_ID`

Synchronize, launch, wait for exit, capture the session, and upload.

| Option | Effect |
|--------|--------|
| `--keep-local` | Resolve a pre-launch conflict in favour of this device |
| `--keep-remote` | Resolve a pre-launch conflict in favour of the remote |

An unresolved conflict prevents launching: playing would build new
progress on top of a save that is already contested.

Unreachable storage does not prevent playing. The session is captured
into the library and marked pending, and the next successful sync
uploads it.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Command failed (unregistered game, conflict, unavailable storage) |
| 2 | Usage error (contradictory options) |
| other | For `play`, the game's own exit code |

---

## Environment

| Variable | Effect |
|----------|--------|
| `SAVECLOUD_HOME` | Override the installation directory |
