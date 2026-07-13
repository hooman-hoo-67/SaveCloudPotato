# SaveCloud Architecture

## Overview

SaveCloud is a save management platform that synchronizes game saves across devices.

Unlike traditional cloud save systems, SaveCloud maintains its own canonical save library. Games only interact with working copies of saves.

## Core Philosophy

The SaveCloud Library is the source of truth.

Games never synchronize directly.

Every save passes through the SaveCloud Library.

## Components

CLI
│
▼
Services
│
├── RegistryService
├── LibraryService
├── DeviceService
├── SyncService
├── AutoSyncService
└── LaunchService
│
├──────────────┐
▼              ▼
Adapters    Launchers
│              │
▼              ▼
Storage Backends
│
▼
SaveCloud Library

## Storage Backends

Current:

- Local

Planned:

- Syncthing
- Google Drive
- Dropbox
- Nextcloud

## Workflow

Launch

↓

Import latest save from SaveCloud Library

↓

Launch game

↓

Wait for game exit

↓

Create version

↓

Update SaveCloud Library

↓

Trigger Storage Backend
