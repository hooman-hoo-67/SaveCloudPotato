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
| 11 | Cloud Providers | ☐ |

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

- [ ] Google Drive
- [ ] Dropbox
- [ ] Nextcloud / WebDAV

Builds on the existing backend interface. None should require changes
to `SyncService`.

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
