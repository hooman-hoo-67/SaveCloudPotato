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
| 10 | Steam Integration | ☐ |
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

---

## Next

### Milestone 10 - Steam Integration

- [ ] Steam launcher
- [ ] Steam Proton adapter
- [ ] non-Steam shortcut creation
- [ ] launch wrapper suitable for Steam's launch options

### Milestone 11 - Cloud Providers

- [ ] Google Drive
- [ ] Dropbox
- [ ] Nextcloud / WebDAV

Both build on existing framework interfaces. Neither should require
changes to `SyncService`.

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
