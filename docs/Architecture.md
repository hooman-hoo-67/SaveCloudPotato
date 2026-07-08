# SaveCloud Architecture

## Overview

SaveCloud is a save management platform that synchronizes game saves across devices.

Unlike traditional cloud save systems, SaveCloud maintains its own canonical save library. Games only interact with working copies of saves.

## Core Philosophy

The SaveCloud Library is the source of truth.

Games never synchronize directly.

Every save passes through the SaveCloud Library.

## Components

- SaveCloud CLI
- SaveCloud Library
- Storage Backend
- Backup Manager
- Metadata Manager
- Emulator/Game Adapters
- Steam Integration

## Storage Backends

Current:

- Syncthing

Planned:

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
