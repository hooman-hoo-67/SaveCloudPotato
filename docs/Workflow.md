# SaveCloud Workflow

---

# Workflow 1 — Register Game

```
User

↓

savecloud register

↓

Display Name

↓

Game ID

↓

Launch Type

↓

Platform

↓

Adapter

↓

Storage Backend

↓

Launcher

↓

Launch Command

↓

Adapter discovers save

↓

Create Registry

↓

Create Device Profile
```

---

# Workflow 2 — Launch Game

```
Steam

↓

SaveCloud CLI

↓

Registry

↓

Device Profile

↓

Launcher Registry

↓

Selected Launcher

↓

Game Process

---

# Workflow 3 — Exit Game

```
Game exits

↓

Detect process exit

↓

Import Working Save

↓

Create Version

↓

Update metadata

↓

Update runtime.json

↓

Synchronize Library

↓

Done
```

---

# Workflow 4 — New Device

```
Install SaveCloud

↓

Connect Storage Backend

↓

Download Library

↓

Download Registry

↓

User links local save folder

↓

Create Device Configuration

↓

Ready
```

---

# Workflow 5 — Restore Version

```
User

↓

Select Version

↓

Backup Current Save

↓

Restore Selected Version

↓

Update runtime.json

↓

Synchronize Library
```

---

# Workflow 6 — First-Time Pairing

```
Desktop

↓

Register Game

↓

Create manifest.json

↓

Create runtime.json

↓

Synchronize Registry

↓

Steam Deck

↓

Import Registry

↓

User links local save folder

↓

Create Device Configuration

↓

Done
```

---

# Design Principles

1. Every game is explicitly registered by the user.

2. The Library is the canonical source of truth.

3. Runtime state and configuration are stored separately.

4. Device configuration is always local.

5. Games never synchronize directly with cloud providers.

6. SaveCloud always synchronizes the Library, never the game's save folder.

7. Every save operation creates a recoverable history.
