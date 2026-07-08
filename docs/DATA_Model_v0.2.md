# SaveCloud Data Model v0.1

## Overview

The SaveCloud data model defines every object managed by SaveCloud.

The primary goals are:

- Separate synchronized data from device-specific data.
- Keep the SaveCloud Library as the canonical source of truth.
- Separate configuration from runtime state.
- Support multiple storage providers, emulators, launchers, and operating systems.
- Keep every component modular and replaceable.

Every component of SaveCloud operates on these objects.

---

# SaveCloud Home

SaveCloud stores all application data inside its own application directory.

Linux

```
~/.local/share/savecloud/
```

Directory structure

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
- Emulator
- Operating System

A Game is uniquely identified by its **Game ID**.

## Responsibilities

- Represent a playable title.
- Provide a globally unique identifier.
- Define how SaveCloud manages the game.

## Does NOT own

- Save paths
- ROM paths
- Steam shortcut IDs
- Launch commands
- Emulator installation paths

## Required Properties

| Field | Purpose |
|-------|---------|
| Game ID | Internal unique identifier |
| Display Name | User-visible name |
| Launch Type | Steam, Heroic, Lutris |
| Platform | Emulator, Proton, Native |
| Adapter | Eden, Dolphin, PCSX2 |

---

# Library

The Library stores the canonical copy of every managed save.

Games never synchronize directly with storage providers.

Every save passes through the Library.

## Responsibilities

- Store the latest canonical save.
- Store save history.
- Store metadata.
- Act as the synchronization source.

Example

```
library/

pokemon-scarlet/

current/

versions/

metadata.json
```

---

# Registry

The Registry stores synchronized information about every managed game.

Each game owns its own registry directory.

Example

```
registry/

pokemon-scarlet/

manifest.json

state.json
```

---

# Manifest

The Manifest stores information that rarely changes.

## Responsibilities

- Describe the game.
- Describe how SaveCloud should manage the game.

Example Fields

- Game ID
- Display Name
- Launch Type
- Platform
- Adapter
- Storage Backend
- Backup Enabled
- Sync Enabled

The Manifest is synchronized between devices.

---

# State

The State stores runtime information.

## Responsibilities

- Track synchronization.
- Track versions.
- Track runtime status.

Example Fields

- Current Version
- Last Device
- Last Sync
- Sync Status
- Pending Upload
- Last Error

The State is synchronized between devices.

---

# Device Configuration

Device Configuration stores information unique to one physical device.

This data is NEVER synchronized.

Example

```
device/

desktop/

pokemon-scarlet.json

steamdeck/

pokemon-scarlet.json
```

Example Fields

- Save Path
- Steam Shortcut ID
- ROM Path
- Emulator Path
- Launch Command

---

# Save

A Save represents the current playable save for a game.

A Save may consist of one or more files.

## Responsibilities

- Represent the current save.
- Store timestamps.
- Store checksums.

Future metadata may include:

- Playtime
- Screenshot
- Notes

---

# Version

Every imported save creates a new immutable Version.

## Responsibilities

- Preserve save history.
- Enable restoration.
- Prevent accidental data loss.

Example

```
versions/

2026-07-09T18-23-51/

2026-07-08T14-02-17/

2026-07-07T09-51-12/
```

Versions are never modified after creation.

---

# Storage Backend

A Storage Backend synchronizes the SaveCloud Library between devices.

Examples

- Syncthing
- Google Drive
- Dropbox
- Nextcloud

Storage Backends never interact directly with game save folders.

---

# Adapter

An Adapter contains emulator- or launcher-specific behavior.

Examples

- Eden
- Dolphin
- PCSX2
- Ryujinx

## Responsibilities

- Locate save files.
- Understand save formats.
- Provide launch information.
- Handle emulator-specific operations.

The SaveCloud core should never contain emulator-specific logic.

---

# Relationships

```
Game
│
├──────────────┐
│              │
▼              ▼
Registry     Library
│              │
│              ▼
│         Save Versions
│
▼
Device Configuration
│
▼
Working Save Folder

Library

↓

Storage Backend

↓

Library (Other Device)

↓

Working Save Folder
```

---

# Design Principles

1. The Library is the canonical source of truth.

2. Games only interact with working copies.

3. Device-specific information is never synchronized.

4. Configuration and runtime state are stored separately.

5. Save versions are immutable.

6. Storage Backends never access game save folders directly.

7. Adapters contain all emulator-specific logic.

8. Every synchronized save must exist inside the Library before it can be uploaded.
