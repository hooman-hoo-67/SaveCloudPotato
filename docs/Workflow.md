# SaveCloud Workflow

---

# Workflow 1 — Register Game

```
savecloud register
        ↓
Display Name
        ↓
Game ID          (rejected here if already registered)
        ↓
Launch Type
        ↓
Platform
        ↓
Adapter
        ↓
Adapter identifier  →  adapter locates and validates the save
        ↓
Launcher
        ↓
Launch Command
        ↓
Create manifest.json
        ↓
Create runtime.json
        ↓
Create library
        ↓
Create device profile
```

Storage backend is not asked for. It belongs to the installation and is
set once with `savecloud config backend`.

---

# Workflow 2 — Play

```
savecloud play <game-id>
        ↓
Synchronize          (see Workflow 4)
        ↓
Device Profile  →  Launcher Registry  →  Selected Launcher
        ↓
Game Process
        ↓
Wait for exit
```

Two things can stop a launch:

- An **unresolved conflict**. Playing would build new progress on top
  of a save that is already contested.
- Nothing else. Unreachable storage produces a warning and the game
  starts anyway.

---

# Workflow 3 — Exit

```
Game exits
        ↓
Record exit code
        ↓
   exit != 0 ──→  capture nothing, report, stop
        ↓
Capture working save into the library
        ↓
Create version
        ↓
Update metadata.json and runtime.json
        ↓
Upload  ──→  fails?  ──→  mark pending, keep the save locally
        ↓
Done
```

Capturing is separate from uploading on purpose. The library is the
source of truth whether or not a backend can be reached, so a session
played offline is preserved and pushed by the next successful sync.

A non-zero exit skips both steps: a crashed game may have written a
half-finished save.

---

# Workflow 4 — Synchronize

```
savecloud sync <game-id>
        ↓
Resolve backend from config.json
        ↓
Read remote state.json
        ↓
Compare three checksums:
    this device's save
    the backend's save
    last_sync_checksum   (the common ancestor)
```

| Local | Remote | Action |
|-------|--------|--------|
| unchanged | unchanged | up to date |
| changed | unchanged | upload |
| unchanged | changed | download |
| changed | changed | conflict |
| — | no ancestor recorded | conflict |

---

# Workflow 5 — Resolve a Conflict

```
Conflict detected
        ↓
Abort by default — nothing is overwritten
        ↓
User chooses
        ↓
    ┌───────────────┴───────────────┐
    ▼                               ▼
--keep-local                   --keep-remote
    ↓                               ↓
Archive remote as a version    Archive local as a version
    ↓                               ↓
Upload local                   Download remote
```

Whichever save loses is written to version history before it is
replaced, so the choice is reversible.

---

# Workflow 6 — New Device

```
savecloud init
        ↓
savecloud config root <shared folder>
        ↓
savecloud pair --list        what storage holds
        ↓
savecloud pair <game-id>
        ↓
Download library and registry
        ↓
User supplies the local save folder
        ↓
User supplies launcher and launch command
        ↓
Export save to the working folder
        ↓
Ready
```

The game is not registered again. Its manifest and runtime travel with
the save; only the device profile is created locally, because only this
machine knows where its save lives.

---

# Workflow 7 — Restore a Version

```
savecloud history <game-id>
        ↓
savecloud restore <game-id> <version>
        ↓
Current save preserved as a new version
        ↓
Selected version becomes current
        ↓
Update metadata.json
```

The restore is itself reversible: the save it replaced is still in
history.

---

# Design Principles

1. Every game is explicitly registered by the user.

2. The Library is the canonical source of truth.

3. Runtime state and configuration are stored separately.

4. Device configuration is always local.

5. Games never synchronize directly with storage providers.

6. SaveCloud always synchronizes the Library, never the game's save
   folder.

7. Every save operation creates a recoverable history.

8. A save is captured into the Library whether or not storage is
   reachable.

9. A conflict is never resolved by guessing.
