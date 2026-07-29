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
| 12 | Desktop Interface | ✓ |

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
- [x] sync, play, snapshot, restore, auto-sync toggle
- [x] conflict resolution
- [x] register, pair, edit, and remove
- [x] installation settings, including Dropbox credentials
- [x] AppImage and Windows packaging

PySide6, importing services in-process. Optional: `pip install
savecloud[gui]`, then `savecloud-gui`. The CLI runs without Qt.

Actions run on worker threads with the controls locked, because the
services expect one caller and the interface is the only thing that
can enforce it. Anything that discards a save asks first.

Forms validate through the facade and report failures inside the
dialog, so a refusal never discards what was typed.

Nothing in the interface is CLI-only any more, apart from `doctor
--strict` and the deliberate `upload`/`download` overrides.

Packaged as a single file that is both: opened from a menu it shows a
window, given arguments it is the command line. `packaging/build-
appimage.sh` builds it; the release workflow builds Linux and Windows
on tagged pushes, since a Windows binary cannot be produced on Linux.

An AppImage stays where it is put, which a virtual environment does
not - so Steam launch options written against one keep working.

### Proton

- [x] prefix discovery from an App ID
- [x] game picker and save folder picker in the interface
- [x] verified against a real Proton game
- [ ] Proton saves shared between two devices

The prefix is found; the save inside it is offered rather than
guessed, because Windows games follow no convention. AppData/Roaming,
AppData/Local, AppData/LocalLow, Documents/My Games, Documents and
Saved Games are all scanned, ordered by how recently each was written.

Verified against a real Proton game on a BC250. Cross-device
compatibility of a Proton save has not been tested.

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
