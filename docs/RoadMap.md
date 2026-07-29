# Roadmap

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Library | ✓ |
| 2 | Registry | ✓ |
| 3 | Sync | ✓ |
| 4 | AutoSync | ✓ |
| 5 | Adapter Framework | ✓ |
| 6 | Launcher Framework | ✓ |
| 7 | Storage Framework | ✓ |
| 8 | Installation Configuration | ✓ |
| 9 | Filesystem Synchronization | ✓ |
| 10 | Steam Integration | ✓ |
| 11 | Cloud Providers | ✓ |
| 12 | Desktop Interface | ◐ |

---

## Delivered

### Milestone 8 - Installation Configuration

Storage selection moved out of every game manifest into a single
`InstallationConfig`, stored in `config.json` and owned by
`ConfigurationService`.

- `config show`, `config backend`, `config root`, `config validate`
- `storage_backend` removed from `GameManifest`
- legacy manifests adopted automatically on `init`
- prompt helpers extracted to `savecloud/utils/prompt.py`

### Milestone 9 - Filesystem Synchronization

- `BaseStorageBackend` interface and shared `FilesystemStorageBackend`
- `StorageRegistry.resolve()` selects the configured provider
- Syncthing backend, including conflict-file reporting
- registry documents synchronized alongside the library
- three-way conflict detection with explicit resolution
- `pair` command for adopting games onto a new device
- desktop ↔ Steam Deck interoperability, covered end to end by tests

Validated against real Syncthing on two physical devices. See
`docs/DECISIONS.md` for the acceptance test, including what remains
unverified about synchronizing mid-replication.

### Milestone 10 - Steam Integration

- `steam-proton` adapter, resolving the Proton prefix from an App ID
  and offering the save directories inside it
- `SteamLauncher`, and `tracks_process_exit()` so a launcher can
  declare that it cannot observe the game
- `savecloud wrap`, which inverts control so Steam starts SaveCloud

Steam supplies the command through `wrap`, so both native and
Proton games work without SaveCloud knowing how to start either.

Validated on a BC250: Steam launching an emulated game through
mangohud and an Eden AppImage, with the save captured on exit. See
`docs/DECISIONS.md` for what that run confirmed and what it did not.

---

## Next

### Milestone 11 - Cloud Providers

- [x] Dropbox
- [ ] Google Drive
- [ ] Nextcloud / WebDAV

Dropbox is implemented, covered by tests against an in-memory fake,
and accepted against the real API: a save uploaded from the BC250 was
downloaded onto a Steam Deck through a Dropbox account shared by both,
and edits made on either device reached the other.

Google Drive and WebDAV stay open. Neither is needed for the app to
work, and the storage framework means adding one changes no service.

It required no change to `SyncService`, which was the point of the
storage framework.

### Milestone 12 - Desktop Interface

- [x] service facade and threading
- [x] read-only viewer: games, state, history, health
- [ ] sync, play, and conflict resolution
- [ ] register and pair
- [ ] AppImage and Windows packaging

PySide6, importing services in-process. Optional: `pip install
savecloud[gui]`, then `savecloud-gui`. The CLI runs without Qt.

Read-only deliberately. The threading, progress, and error paths are
exercised on something that cannot destroy a save before any button
that could is added.

### Not planned

- non-Steam shortcut creation (`shortcuts.vdf`)

Dropped rather than deferred. Steam ROM Manager writes the same file,
Steam discards edits made while it is running, and a malformed write
loses every non-Steam shortcut. Launch options set by hand achieve the
same result with none of that. See `docs/DECISIONS.md`.

---

## Later

### Adapters

- [ ] Ryujinx
- [ ] Dolphin
- [ ] PCSX2
- [ ] RPCS3
- [ ] RetroArch
- [ ] PPSSPP
- [ ] Cemu

### Launchers

- [ ] Heroic
- [ ] Lutris
- [ ] Wine
- [ ] Flatpak

### Platform Features

- [ ] Decky Loader plugin
- [ ] Millennium plugin
- [ ] automatic game discovery
- [ ] snapshot browser
- [ ] graphical interface

### Platforms

- [ ] Windows
- [ ] macOS
