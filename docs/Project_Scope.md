# SaveCloud Project Scope

## Mission

SaveCloud is a save management platform designed to provide seamless cloud save functionality for games that do not natively support it.

SaveCloud manages, versions, backs up, and synchronizes game save files across multiple devices while remaining independent of any specific storage provider.

The primary goal is to make switching between devices (Desktop, Steam Deck, Laptop, etc.) as seamless as using Steam Cloud.

---

# Core Principles

1. SaveCloud owns the canonical copy of every save.

2. Games only interact with temporary working copies.

3. Every save operation must be recoverable.

4. SaveCloud must remain storage backend agnostic.

5. Save synchronization should require minimal user interaction.

6. Device-specific information should never be synchronized.

7. Manual configuration is preferred over incorrect automation.

8. SaveCloud should continue functioning even if a storage backend is unavailable.

9. Steam is the primary frontend.

10. The project should be modular, allowing support for new emulators, launchers, and storage providers without modifying the core architecture.

---

# What SaveCloud Is

- A save management platform.
- A launcher wrapper.
- A save synchronization system.
- A versioning system for game saves.
- A backup manager.
- A storage backend abstraction layer.
- A Steam-first experience for non-Steam games and emulators.

---

# What SaveCloud Is NOT

SaveCloud is NOT:

- A ROM manager.
- A game launcher.
- A game installer.
- A replacement for Steam.
- A replacement for Steam Cloud.
- A replacement for Syncthing.
- A save editor.
- A cheat manager.
- A game library manager.
- A cloud storage provider.

---

# Supported Content

The project is intended to support:

- Emulator saves
- Native Linux game saves
- Proton game saves
- Non-Steam games added to Steam

Future support may include:

- Windows
- Heroic Launcher
- Lutris
- Additional launchers and emulators

---

# Storage Philosophy

SaveCloud does not synchronize game save folders directly.

Instead:

Game Save Folder

↓

SaveCloud Library (Canonical Copy)

↓

Storage Backend

↓

SaveCloud Library (Other Device)

↓

Game Save Folder

This separation allows:

- Multiple storage providers
- Version history
- Automatic backups
- Offline synchronization
- Conflict resolution
- Data integrity verification

---

# Design Goals

- Reliability over speed.
- Explicit configuration over implicit assumptions.
- Data integrity over convenience.
- Modular architecture.
- Cross-platform compatibility.
- Minimal user interaction after initial setup.
- Easy extensibility for future plugins and storage providers.

---

# Long-Term Vision

SaveCloud aims to provide a Steam Cloud–like experience for every game, regardless of launcher, emulator, or platform.

Users should be able to launch a game from Steam on one device, continue playing on another device, and have their saves synchronized automatically with backups, version history, and minimal manual intervention.
