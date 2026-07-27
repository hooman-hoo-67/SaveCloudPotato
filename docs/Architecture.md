# SaveCloud Architecture

## Overview

SaveCloud is a save management platform that synchronizes game saves
across devices.

Unlike traditional cloud save systems, SaveCloud maintains its own
canonical save library. Games only interact with working copies of
saves.

## Core Philosophy

The SaveCloud Library is the source of truth.

Games never synchronize directly.

Every save passes through the SaveCloud Library.

## Layers

```
CLI
 │
 ▼
Commands
 │
 ▼
Services
 │
 ├── RegistryService        registered games
 ├── SaveCloudLibrary       canonical save data
 ├── SaveService            import, export, versions
 ├── DeviceService          machine-specific profiles
 ├── ConfigurationService   installation settings
 ├── SyncService            transfer and conflict detection
 ├── AutoSyncService        the play lifecycle
 └── LaunchService          starting games
 │
 ├──────────────┬──────────────┐
 ▼              ▼              ▼
Adapters    Launchers    Storage Backends
 │              │              │
 ▼              ▼              ▼
Save paths  Game process  Remote storage
```

Dependencies flow downward. Commands may call services; services may
use models and framework components; the three frameworks never depend
on one another. Commands never import other commands - anything shared
between them lives in `savecloud/utils/`.

## Frameworks

Each framework answers exactly one question.

| Framework | Question | Implementations |
|-----------|----------|-----------------|
| Adapters | Where are this game's saves? | Manual, Eden |
| Launchers | How is this game started? | Native, AppImage |
| Storage Backends | How is the library synchronized? | Local, Syncthing |

All three follow the same shape: an abstract base class, concrete
implementations, and a registry that services look them up in. Adding a
provider means implementing an interface and registering it. No service
changes.

## Configuration

Storage selection belongs to the installation, not to a game.

```
config.json
    ↓
ConfigurationService
    ↓
InstallationConfig
    ↓
StorageRegistry.resolve()
    ↓
Selected backend
```

`SyncService` never names a provider. It asks the registry which one is
configured and uses whatever it gets back.

## Synchronization

A save exists in three places, and SaveCloud compares all three before
moving anything:

```
working save (this device)
canonical save (the backend)
last_sync_checksum (the common ancestor)
```

| Local | Remote | Result |
|-------|--------|--------|
| unchanged | unchanged | up to date |
| changed | unchanged | upload |
| unchanged | changed | download |
| changed | changed | conflict |

Without a recorded ancestor there is no basis for attributing a
difference to either side, so that case is treated as a conflict too.

A conflict aborts by default. `--keep-local` and `--keep-remote`
resolve it explicitly, and the losing save is written to version
history first, so no resolution destroys progress.

## Workflow

```
Play
 ↓
Synchronize (download newer remote progress)
 ↓
Launch game
 ↓
Wait for exit
 ↓
Capture working save into the library
 ↓
Create version
 ↓
Upload
```

Capturing is deliberately separate from uploading. The library is the
source of truth whether or not a backend can be reached, so a session
played offline is preserved locally and marked pending; the next
successful sync pushes it.

A non-zero exit code skips the upload. A crashed game may have written
a half-finished save, so it is captured locally but not published to
other devices.

## Pairing

A second device does not re-register anything. Manifests and runtimes
travel with the save, so the only thing a new device supplies is what
cannot be synchronized: where the save lives locally and how the game
starts.

```
savecloud pair --list      what storage holds
savecloud pair <game-id>   adopt it here
```
