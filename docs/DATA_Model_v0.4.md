# SaveCloud Data Model v0.4

Supersedes v0.3.

## What changed

| Change | Reason |
|--------|--------|
| `GameManifest.storage_backend` removed | Moved to `InstallationConfig`; every game held the same value |
| `InstallationConfig` added | Installation-wide settings need an owner |
| `GameRuntime.last_sync_checksum` added | Conflict detection needs a common ancestor |
| `RemoteState` added | Describes what a backend holds, without downloading it |

---

## Overview

```
InstallationConfig          (this installation, never synchronized)
        │
        ▼
Storage Backend
        │
        ▼
     Library ──────── Version (immutable history)
        ▲
        │
      Game
        │
        ├──────────────┬──────────────┐
        ▼              ▼              ▼
   GameManifest   GameRuntime   DeviceProfile
   (synchronized) (synchronized) (never synchronized)
```

`InstallationConfig` sits outside the game hierarchy deliberately: it
applies equally to every game, so placing it inside any one of them
would duplicate it across all of them.

---

## Game

The logical title SaveCloud manages. Not a Steam installation, an
emulator, a launcher, or a machine.

Identified by a **Game ID**.

Owns exactly one `GameManifest` and one `GameRuntime`.

Does not launch games or locate saves. Those belong to launchers and
adapters.

---

## GameManifest

Configuration describing how a game is managed. Changes rarely.
Synchronized, because every device should agree on it.

| Field | Type |
|-------|------|
| `game_id` | `str` |
| `display_name` | `str` |
| `launch_type` | `LaunchType` |
| `platform` | `Platform` |
| `adapter` | `str` |
| `backup_enabled` | `bool` |
| `sync_enabled` | `bool` |

Frozen. Configuration that changes this rarely should not be mutable
in memory.

`LaunchType` — `steam`, `heroic`, `lutris`, `manual`
`Platform` — `emulator`, `proton`, `native`

Manifests written before v0.4 include `storage_backend`. It is ignored
on load.

---

## GameRuntime

What is happening now. Changes constantly. Synchronized.

| Field | Type |
|-------|------|
| `current_version` | `int` |
| `last_device` | `str \| None` |
| `last_sync` | `datetime \| None` |
| `last_launch` | `datetime \| None` |
| `last_exit` | `datetime \| None` |
| `last_exit_code` | `int \| None` |
| `status` | `SyncStatus` |
| `pending_upload` | `bool` |
| `last_error` | `str \| None` |
| `last_sync_checksum` | `str \| None` |
| `created_at` | `datetime` |

`SyncStatus` — `unknown`, `running`, `synced`, `pending`, `conflict`,
`error`

### last_sync_checksum

The save contents at the last successful synchronization: the common
ancestor of this device's save and the backend's.

Two-way comparison can only report *that* two saves differ. Comparing
both against a shared ancestor reports *which* of them moved, which is
the difference between applying a change automatically and overwriting
someone's afternoon.

### Transitions

| Method | Effect |
|--------|--------|
| `mark_running()` | Game launched |
| `mark_exited(code)` | Game exited |
| `mark_pending()` | Local changes await upload |
| `mark_synced(device, checksum)` | Synchronized; records the ancestor |
| `mark_conflict()` | Both sides changed |
| `mark_error(message)` | Something failed |

---

## DeviceProfile

How one machine reaches one game. **Never synchronized.**

| Field | Type |
|-------|------|
| `device_id` | `str` |
| `device_name` | `str` |
| `game_id` | `str` |
| `working_save_path` | `Path` |
| `launch_command` | `str` |
| `launcher` | `str` |
| `last_local_sync` | `datetime \| None` |
| `enabled` | `bool` |

Save locations differ per machine:

```
Desktop     /home/user/.steam/steamapps/compatdata/...
Steam Deck  /home/deck/.local/share/Steam/steamapps/compatdata/...
Windows     C:\Users\User\AppData\...
```

All three manage the same game. Synchronizing these paths would
overwrite valid local configuration with another machine's.

`enabled` is this device's automatic-sync switch. `play`, `wrap`, and
a bare `savecloud sync` skip a game it is off for; naming the game
explicitly still synchronizes it. Because the profile never travels,
one device can stop uploading without changing anything for the others
- which `GameManifest.sync_enabled`, being synchronized, cannot do.

---

## InstallationConfig

Settings belonging to the installation. Stored in `config.json`. Never
synchronized.

| Field | Type | Default |
|-------|------|---------|
| `storage_backend` | `str` | `"local"` |
| `storage_root` | `Path` | `~/SaveCloudRemote` |
| `version_retention` | `int` | `2` |

Before v0.4 every manifest carried its own backend:

```
Game A   storage_backend = local
Game B   storage_backend = local
Game C   storage_backend = local
```

Changing provider meant editing all of them, and nothing stopped them
drifting into disagreement — a state with no coherent meaning, since
one installation has one storage location.

Unknown keys are ignored on load, so configuration written by a newer
version stays readable.

---

## LibraryMetadata

Describes a game's library. Synchronized with it.

| Field | Type |
|-------|------|
| `current_version` | `int` |
| `latest_version` | `int` |
| `created_at` | `str` |
| `last_import` | `str \| None` |
| `last_export` | `str \| None` |

---

## RemoteState

What a storage backend currently holds. Written as `state.json` beside
the uploaded save.

| Field | Type |
|-------|------|
| `game_id` | `str` |
| `checksum` | `str` |
| `version` | `int` |
| `device_id` | `str` |
| `device_name` | `str` |
| `updated_at` | `str` |

Reading it is cheap, so SaveCloud can decide whether a transfer is
needed without downloading the save first. A remote with no state
document — written by an older version, or by a plain file copy — has
one derived from its contents on read, so conflict detection still has
something to compare.

`device_name` and `updated_at` are what a conflict is described with.
Choosing between two saves means knowing which machine the other came
from and how recently someone played on it; a checksum answers
neither. A derived state has no name to report, and is described as
"another device" rather than given one.

---

## Version

An immutable snapshot of a save, numbered sequentially and zero-padded
(`000001`).

Sequential numbers rather than timestamps: version identity must not
depend on two devices agreeing about the clock.

Created when a changed save is captured, when a restore replaces the
current save, and when a conflict resolution discards one side.

Never modified after creation.

---

## Save

The current playable state: one file, several files, or a directory
tree. SaveCloud treats it as one logical unit and never interprets its
contents.

Identified by a SHA-256 checksum over the tree, covering each file's
relative path and its contents. Paths are included so a rename is
detected; timestamps are excluded because they survive neither copying
nor crossing between filesystems.

---

## Design Rules

1. Every Game has exactly one Manifest and one Runtime.
2. Every device maintains its own DeviceProfile.
3. DeviceProfiles are never synchronized.
4. InstallationConfig belongs to the installation, not to any game.
5. Runtime changes frequently; Manifest changes rarely.
6. The Library is the canonical owner of save data.
7. Versions are immutable.
8. Services operate on these models but do not own them.
