# Data Model

## SaveCloud Library

~/.local/share/savecloud/

library/

configs/

logs/

cache/

providers/

## Game Folder

library/

pokemon-scarlet/

current/

versions/

metadata.json

## Metadata

Each game stores:

- Game ID
- Display Name
- Save Version
- Last Device
- Last Sync
- Storage Backend
- Checksums

## Configuration

Configuration is split into:

Shared Configuration
Device Configuration

# SaveCloud Data Model

## Overview

The SaveCloud data model defines every object managed by SaveCloud.

The goal is to separate:

- Shared game information
- Device-specific configuration
- Save data
- Version history
- Storage providers

Every component of SaveCloud operates on these objects.

# Game

A Game represents a single playable title managed by SaveCloud.

A Game is independent of:

- Device
- Storage backend
- Emulator
- Operating system

A Game is identified by a globally unique Game ID.

Required properties

| Field        | Purpose                  |
| ------------ | ------------------------ |
| Game ID      | Internal identifier      |
| Display Name | User-visible name        |
| Launch Type  | Steam, Heroic, Lutris    |
| Platform     | Emulator, Proton, Native |
| Adapter      | Eden, Dolphin, PCSX2     |

#Device
Desktop

Steam Deck

Laptop

Windows PC

#Library
The SaveCloud Library stores the canonical copy of every managed save.

Games only interact with working copies.

Storage backends synchronize the library.

#Save
A Save represents:

Files, Folder, Timestamp,Version, Checksum

Eventually maybe:

Playtime, Screenshot, Notes

#Version 
Every import creates a new version.

Version
↓
Immutable
↓
Never edited

#Storage Backend Examples
Syncthing, Google Drive, Dropbox, Nextcloud

#Adapter
Adapters will verify how different emulators save games. e.g. an Eden Adapter will contain daa for how/where the Eden Emulator saves files

#Relationships
Game
 │
 ├──────────────┐
 │              │
 ▼              ▼
Device      Library
 │              │
 ▼              ▼
Working Copy  Versions
        │
        ▼
Storage Backend
