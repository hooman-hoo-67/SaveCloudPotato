# SaveCloud Potato

Steam Cloud for everything.

SaveCloud gives cloud saves to games that do not have them: emulators,
Proton games, native Linux games, and anything else you can launch.
It works the same regardless of where a game came from.

## Goals

- Sync emulator saves
- Sync Proton saves
- Sync non-Steam games
- Steam Deck support
- Automatic backups
- Conflict detection

## Current Status

Milestones 1-10 complete. Desktop ↔ Steam Deck synchronization works
today over a shared folder or Syncthing, and games can be launched
from Steam.

Cloud storage providers are next.

## How it works

Game save folders are never synchronized directly. SaveCloud keeps its
own library, and that library is what travels between devices.

```
                GAME
                  │
                  │ writes saves
                  ▼
        Game Save Folder (Working Copy)
                  │
                  │ import
                  ▼
         SaveCloud Library (Canonical)
                  │
                  ├──────────────┐
                  │              │
                  ▼              ▼
             Versions        Metadata
                  │
                  ▼
           Storage Backend
                  │
        ┌─────────┴──────────┐
        │                    │
    Syncthing            Local folder
        │                    │
        └─────────┬──────────┘
                  ▼
      Other Device SaveCloud Library
                  │
                  ▼
      Game Save Folder (Working Copy)
```

The indirection is what buys version history, offline operation,
provider independence, and the ability to tell a one-sided change from
a genuine conflict.

## Install

```
pip install -e .
```

Requires Python 3.11 or newer.

## Getting started

```bash
savecloud init
savecloud config root ~/Sync/SaveCloud
savecloud register
savecloud play <game-id>
```

`play` synchronizes, launches the game, waits for it to exit, captures
the save, and uploads it.

## Steam games

Let Steam do the launching. Set the game's Launch Options to:

```
savecloud wrap <game-id> -- %command%
```

Steam starts SaveCloud, SaveCloud syncs and runs the game, then
captures the save when it exits. Works for native and Proton games
alike, because Steam supplies the command.

**Use the absolute path** if SaveCloud is installed in a virtualenv.
Steam does not run launch options through a shell that has it
activated, so a bare `savecloud` will not be found:

```
/home/you/SaveCloudPotato/.venv/bin/savecloud wrap <game-id> -- %command%
```

Other wrappers can be chained after the `--`, and nesting is fine:

```
... savecloud wrap <game-id> -- mangohud %command%
```

For Proton games, register with the `steam-proton` adapter: it finds
the Proton prefix from the App ID and offers the save directories
inside it.

## Adding a second device

Nothing is registered twice. The game's configuration travels with its
save.

```bash
savecloud init
savecloud config root ~/Sync/SaveCloud
savecloud pair --list
savecloud pair <game-id>
```

Pairing asks only for what cannot be synchronized: where the save lives
on this machine and how the game starts here.

## Conflicts

If two devices both played without synchronizing in between, SaveCloud
stops rather than choosing:

```
✗ Save conflict for "pokemon-scarlet": this device and the remote
  have both changed since the last synchronization.

Nothing has been overwritten. Resolve it with one of:

  savecloud sync pokemon-scarlet --keep-local
  savecloud sync pokemon-scarlet --keep-remote
```

Whichever save loses is kept in version history, so the choice is
reversible.

## Commands

| Command | Purpose |
|---------|---------|
| `init` | Create the installation |
| `config` | Storage backend and root |
| `register` / `unregister` | Manage games |
| `list` / `info` | Inspect games |
| `play` | Sync, launch, capture, upload |
| `wrap` | Same, but launched from Steam |
| `sync` | Synchronize one game or all of them |
| `pair` | Adopt a game onto this device |
| `upload` / `download` | Force a direction |
| `import` / `export` | Move saves in and out of the library |
| `snapshot` / `history` / `restore` | Version history |
| `doctor` | Check the installation for problems |

Full reference in [`docs/API.md`](docs/API.md).

## Development

```bash
pip install -e . pytest
pytest
```

Tests run against a temporary installation and never touch your real
one. Set `SAVECLOUD_HOME` to point SaveCloud somewhere else manually.

## Documentation

| Document | Contents |
|----------|----------|
| [Architecture](docs/Architecture.md) | Layers, frameworks, synchronization |
| [Project Scope](docs/Project_Scope.md) | What SaveCloud is and is not |
| [Filesystem Layout](docs/Filesystem_Layout.md) | On-disk and remote structure |
| [Data Model](docs/DATA_Model_v0.4.md) | Domain objects |
| [Decisions](docs/DECISIONS.md) | Why things are the way they are |
| [Roadmap](docs/RoadMap.md) | Milestones |
| [Contributing](docs/Contributing.md) | Conventions |

## License

See [LICENSE](LICENSE).
