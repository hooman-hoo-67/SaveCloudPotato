# SaveCloudPotato
# SaveCloud Potato

Steam Cloud for everything.

## Goals

- Sync emulator saves
- Sync Proton saves
- Sync non-Steam games
- Steam Deck support
- Automatic backups
- Conflict detection

## Current Status

🚧 Early development Architecture

                GAME
                  │
                  │ writes saves
                  ▼
        Game Save Folder (Working Copy)
                  │
                  │ Import
                  ▼
         SaveCloud Library (Canonical)
                  │
                  ├──────────────┐
                  │              │
                  ▼              ▼
            Local Backup     Metadata
                  │
                  ▼
          Storage Backend
                  │
        ┌─────────┴──────────┐
        │                    │
    Syncthing          Google Drive
        │                    │
        └─────────┬──────────┘
                  ▼
      Other Device SaveCloud Library
                  │
                  ▼
      Game Save Folder (Working Copy)
