# SaveCloud Filesystem Layout

## Overview

SaveCloud separates synchronized data from device-specific data.

Only data required for cross-device synchronization is synchronized.
Machine-specific information is always stored locally.

---

# Root Directory

Linux

```
~/.local/share/savecloud/
```

The location is resolved at runtime and can be overridden with the
`SAVECLOUD_HOME` environment variable. This is what allows a single
machine to hold more than one installation, and what keeps the test
suite away from a developer's real data.

Future platforms will use their platform-specific application data
directory.

---

# Directory Layout

```
savecloud/
    savecloud.json
    config.json
    library/
    registry/
    device/
    cache/
    logs/
    providers/
```

---

# savecloud.json

Installation metadata created during `savecloud init`.

Fields

- `schema_version`
- `savecloud_version`
- `device_id`
- `device_name`
- `created_at`

The `device_id` identifies this machine to every other device. It is
generated once and never regenerated, since doing so would orphan the
device's synchronization history.

---

# config.json

Installation-wide configuration, owned by `ConfigurationService`.

```json
{
    "storage_backend": "local",
    "storage_root": "/home/user/SaveCloudRemote"
}
```

This file is never synchronized. Storage configuration describes this
installation, not the games it manages, so each device chooses its own
backend and root.

Unknown keys are ignored on load, so a configuration written by a newer
version of SaveCloud stays readable.

---

# library/

## Purpose

Stores the canonical copy of every managed game's save data.

The library is synchronized between devices.

```
library/
    pokemon-scarlet/
        current/
        versions/
        metadata.json
```

---

# current/

Contains the latest playable save.

Before launching a game, SaveCloud copies the contents of `current/`
into the game's working save folder.

---

# versions/

Stores immutable historical save versions, numbered sequentially and
zero-padded.

```
versions/
    000001/
    000002/
    000003/
```

Versions are never modified after creation. Sequential numbering means
version identity does not depend on a clock, which matters when two
devices disagree about the time.

A version is created whenever a changed save is captured, whenever a
restore replaces the current save, and whenever a conflict resolution
discards one side.

History is bounded by `version_retention` in `config.json`, which
defaults to the two most recent. Nothing SaveCloud overwrites is
unrecoverable within that window; set the retention to zero to keep
every version instead.

Versions are trimmed as they are created, and again whenever the
window is set, since a game whose save has not changed would otherwise
keep history the window no longer allows.

---

# metadata.json

Describes the game's library.

Fields

- `current_version`
- `latest_version`
- `created_at`
- `last_import`
- `last_export`

---

# registry/

## Purpose

Stores synchronized information about every managed game. It contains
no save data.

```
registry/
    pokemon-scarlet/
        manifest.json
        runtime.json
```

---

# manifest.json

Configuration describing how a game is managed. Changes rarely.

Fields

- `game_id`
- `display_name`
- `launch_type`
- `platform`
- `adapter`
- `backup_enabled`
- `sync_enabled`

`storage_backend` was removed in Milestone 8. It now lives in
`config.json`, because every game on an installation used the same
value. Manifests that still carry the field load correctly; the value
is ignored, and `savecloud init` adopts it as the installation default.

---

# runtime.json

Frequently changing state describing what is happening now.

Fields

- `current_version`
- `last_device`
- `last_sync`
- `last_launch`
- `last_exit`
- `last_exit_code`
- `status`
- `pending_upload`
- `last_error`
- `last_sync_checksum`

`last_sync_checksum` records the save contents at the last successful
synchronization. It is the common ancestor conflict detection compares
against; without it, a difference between two devices cannot be
attributed to either side.

---

# device/

## Purpose

Stores machine-specific configuration. Never synchronized.

```
device/
    <device-id>/
        pokemon-scarlet.json
```

Fields

- `device_id`
- `device_name`
- `game_id`
- `working_save_path`
- `launch_command`
- `launcher`
- `last_local_sync`
- `enabled`

Save paths and launch commands differ between machines. Synchronizing
them would overwrite valid local configuration with another device's.

---

# cache/

Temporary runtime data. Nothing here is required for recovery, and it
is always safe to delete.

---

# logs/

What SaveCloud did, in `savecloud.log`, rotated at 1MB with three
kept. Never synchronized.

`wrap` runs inside Steam with no terminal, so anything it prints goes
nowhere. This is where a failed pre-launch sync or a failed upload
after a session survives long enough to be read.

Credentials are never written to it, so it can be attached to a bug
report unedited.

---

# providers/

Provider-specific configuration and credentials. Never synchronized.

---

# Remote Layout

Storage backends do not mirror the local layout. They own their own
structure beneath the configured storage root:

```
<storage_root>/
    games/
        pokemon-scarlet/
            current/
            versions/
            manifest.json
            runtime.json
            state.json
```

The registry documents travel with the save, which is what allows a new
device to adopt a game without registering it again.

`state.json` records what the backend currently holds:

- `checksum` of the uploaded save
- `version` it corresponds to
- `device_id` and `device_name` that uploaded it
- `updated_at`

Reading it is cheap, so SaveCloud can decide whether a transfer is
needed without downloading the save first.

---

# Synchronization Rules

Synchronized

```
library/
registry/
```

Never synchronized

```
device/
cache/
logs/
providers/
config.json
savecloud.json
```
