# SaveCloud Data Model v0.3

## Overview

The SaveCloud data model defines every object managed by SaveCloud.

The primary goals are:

- Separate synchronized data from device-specific data.
- Keep the SaveCloud Library as the canonical source of truth.
- Separate configuration from runtime state.
- Separate save management from game launching.
- Support multiple storage providers, adapters, launchers, and operating systems.
- Keep every subsystem modular and replaceable.

Every component of SaveCloud operates on these objects.

---

# SaveCloud Home

All application data is stored inside the SaveCloud application directory.

Linux

```
~/.local/share/savecloud/
```

Directory layout

```
savecloud/

library/
registry/
device/
cache/
logs/
providers/
```

---

# Game

A Game represents a single playable title managed by SaveCloud.

A Game is independent of:

- Device
- Storage Backend
- Adapter
- Launcher
- Operating System

A Game is uniquely identified by its **Game ID**.

## Responsibilities

- Represent a managed game.
- Store shared configuration.
- Store synchronized runtime state.

A Game owns:

- Manifest
- Runtime

---

# Manifest

The Manifest contains configuration that is shared across every device.

## Responsibilities

- Describe the game.
- Describe how SaveCloud manages the game.

Example fields

- Game ID
- Display Name
- Launch Type
- Platform
- Adapter
- Storage Backend

The Manifest changes infrequently.

The Manifest is synchronized.

---

# Runtime

Runtime stores synchronized state.

## Responsibilities

- Track synchronization.
- Track version history.
- Track game activity.

Example fields

- Current Version
- Last Device
- Last Sync
- Last Launch
- Last Exit
- Exit Code
- Sync Status
- Pending Upload
- Last Error

Runtime changes frequently.

Runtime is synchronized.

---

# Device Profile

A Device Profile stores configuration unique to one physical device.

Device Profiles are NEVER synchronized.

Each device maintains its own profile for every registered game.

## Responsibilities

- Store the working save location.
- Store launch configuration.
- Track local synchronization state.

Example fields

- Device ID
- Device Name
- Working Save Path
- Launcher
- Launch Command
- Last Local Sync
- Enabled

---

# Library

The Library stores the canonical copy of every managed save.

Games never synchronize directly.

Every save passes through the Library.

## Responsibilities

- Store the latest playable save.
- Store save history.
- Store save metadata.

Example

```
library/

pokemon-scarlet/

current/

versions/

metadata.json
```

---

# Save

A Save represents the latest playable save.

A Save may consist of one or more files.

Responsibilities

- Store current save data.
- Store timestamps.
- Store checksums.

Future metadata may include

- Playtime
- Screenshot
- Notes

---

# Version

Every imported save creates a new immutable Version.

Responsibilities

- Preserve history.
- Enable restoration.
- Prevent accidental data loss.

Example

```
versions/

2026-07-09T18-23-51/

2026-07-08T14-02-17/

2026-07-07T09-51-12/
```

Versions are never modified.

---

# Storage Backend

A Storage Backend synchronizes the SaveCloud Library.

Storage Backends never interact directly with game save folders.

Current

- Local

Future

- Syncthing
- Google Drive
- Dropbox
- Nextcloud

Responsibilities

- Upload Library
- Download Library
- Synchronize canonical data

---

# Adapter

Adapters encapsulate save-management behaviour for specific platforms.

Examples

- Eden
- Dolphin
- Ryujinx
- PCSX2
- Manual

Responsibilities

- Locate working save folders.
- Validate save locations.
- Discover platform-specific save layouts.

Adapters NEVER launch games.

---

# Launcher

Launchers encapsulate execution behaviour.

Examples

- Native
- AppImage
- Steam
- Heroic
- Lutris

Responsibilities

- Validate launch configuration.
- Launch game processes.
- Encapsulate execution method.

Launchers NEVER locate save folders.

---

# Services

Services implement the SaveCloud workflow.

Current services

- RegistryService
- DeviceService
- LibraryService
- SyncService
- AutoSyncService
- LaunchService

Services coordinate components.

Services do not contain emulator-specific or launcher-specific behaviour.

---

# Relationships

```
Game
│
├─────────────┐
│             │
▼             ▼
Manifest    Runtime
│
▼
Registry
│
▼
Device Profile
│
├──────────────┐
│              │
▼              ▼
Adapter     Launcher
│              │
│              ▼
│        Running Game
│
▼
Working Save Folder
│
▼
Library
│
▼
Versions
│
▼
Storage Backend
```

---

# Design Principles

1. The Library is the canonical source of truth.

2. Games only interact with working copies.

3. Device-specific information is never synchronized.

4. Configuration and runtime state are stored separately.

5. Save versions are immutable.

6. Storage Backends never access working save folders.

7. Adapters own save discovery and validation.

8. Launchers own process execution.

9. Services coordinate components rather than implementing platform-specific behaviour.

10. Every synchronized save must pass through the Library before reaching a storage backend.

11. New adapters, launchers, and storage backends should be addable without modifying core services.
