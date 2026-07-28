# Architectural Decisions

## 2026-07-09

### SaveCloud owns the canonical save copy

Decision

Games use working copies.

The SaveCloud Library stores the canonical save.

Reason

Allows:

- Version history
- Offline synchronization
- Multiple storage providers
- Conflict detection

Launcher Integration Finding (Acceptance Test)

Manual execution of Eden with the current command line reproduces the same behavior observed through SaveCloud: the emulator launches but does not immediately start the selected game. Since the behavior is identical outside SaveCloud, this is not considered a LaunchService defect. Emulator-specific launch semantics should be encapsulated by the Eden adapter in a future launcher integration milestone.

Status

Accepted

Decision

Adapters are responsible only for save discovery
and save validation.

They never launch games.

Decision

Launch methods are encapsulated by launchers.

Launchers are independent of emulators.

---

## 2026-07-27

### Storage configuration belongs to the installation

Decision

Storage backend and storage root move from `GameManifest` into
`InstallationConfig`, stored in `config.json`.

Reason

Every registered game held an identical `storage_backend` value.
Changing provider meant editing every manifest, and nothing prevented
them drifting apart into a state with no meaningful interpretation.

Manifests carrying the old field still load; the value is ignored, and
`init` adopts it as the installation default when every manifest
agrees. When they disagree, nothing is adopted - picking one
arbitrarily could silently redirect a game's saves.

Status

Accepted

---

### Save identity is content, not modification time

Decision

Saves are identified by a SHA-256 checksum over the directory tree,
covering each file's relative path and contents.

Reason

Timestamps are unreliable across devices, filesystems, and copy
operations; a plain copy can produce a "newer" file with identical
contents. Including relative paths means a rename is detected as a
change, which content-only hashing would miss.

Status

Accepted

---

### Conflicts are detected against a recorded ancestor

Decision

`GameRuntime` records `last_sync_checksum` at every successful
synchronization. Synchronization compares three values: this device's
save, the backend's save, and that ancestor.

Reason

Comparing only two sides cannot distinguish "the remote advanced" from
"this device advanced" - both look like a difference. The ancestor is
what makes a one-sided change safe to apply automatically and a
two-sided change identifiable as a conflict.

Where no ancestor exists, the difference is treated as a conflict
rather than resolved by guessing.

Status

Accepted

---

### A conflict aborts rather than choosing

Decision

Synchronization refuses to resolve a conflict on its own. `--keep-local`
and `--keep-remote` make the choice explicit, and the losing save is
written to version history before being replaced.

Reason

Both sides represent real play time. Only the person who played knows
which matters. Last-write-wins would silently discard a session.

`play` extends this: an unresolved conflict prevents launching, because
playing would build new progress on top of a contested save.

Status

Accepted

---

### Capturing a save is independent of any storage backend

Decision

`SyncService.capture()` imports the working save into the library and
versions it without involving a backend. `upload()` calls it, and
`AutoSyncService` calls it directly before attempting to push.

Reason

An earlier implementation resolved the backend first, so a session
played while storage was unreachable was never captured at all - the
save existed only in the game's working directory, where the next
session would overwrite it. The library is the source of truth whether
or not a backend can be reached.

Status

Accepted

---

### The Syncthing backend refuses folders Syncthing does not manage

Decision

The Syncthing backend reports itself unavailable unless the storage
root contains Syncthing's `.stfolder` marker, and never creates the
root itself.

Reason

Creating a missing directory would produce somewhere that looks correct
and silently never replicates. Failing loudly is better than a backup
that does not exist.

Status

Accepted

---

### Single-action commands are commands, not sub-applications

Decision

`cli.py` registers plain functions with `app.command()`. Only `config`,
which has genuine subcommands, is mounted with `add_typer()`.

Reason

Mounting a single-action command as a sub-Typer makes it a Click group,
so anything following its positional argument is parsed as a
subcommand. `savecloud sync <game> --check` failed with "No such
command". The same ambiguity ruled out giving `pair` both a default
action and a `list` subcommand; it takes a `--list` flag instead.

Status

Accepted

---

### Tests run against a temporary installation

Decision

Filesystem paths are resolved at call time from `SAVECLOUD_HOME` rather
than fixed at import. An autouse fixture points every test at a
temporary directory.

Reason

The previous test scripts wrote to the developer's real installation
and to `~/SaveCloudRemote`, so running them mutated live data and left
tests depending on each other's leftovers. Runtime resolution also
gives the installation-wide storage root somewhere to take effect.

Status

Accepted

---

## 2026-07-28

### Milestone 9 acceptance test: real Syncthing, two devices

Context

Until this point the Syncthing backend had unit test coverage but had
never run against an actual Syncthing installation. The two-device
tests in `tests/test_multi_device.py` use two SaveCloud installations
sharing one directory, which exercises the synchronization logic but
not the replication underneath it.

Setup

- Two physical devices, each with its own SaveCloud installation.
- Syncthing sharing one folder between them, used as `storage_root`.
- `savecloud config backend syncthing` on both.
- `~/.local/share/savecloud/` deliberately NOT shared, so device
  profiles and `config.json` stay machine-local.

Result

The full workflow behaved as designed: registering on the first
device, `pair` adopting the game on the second without re-registering
it, and progress moving in both directions.

Finding: synchronizing before replication completed

`savecloud sync` was run on the second device before Syncthing
reported the folder "Up to Date", and the outcome was still correct.

This was the failure mode expected to surface first. SaveCloud reads
the storage root as though it reflects the other device's state, and
Syncthing updates it asynchronously, so a sync issued mid-replication
could in principle read a stale or partially written save, record a
stale checksum as the common ancestor, and manufacture a phantom
conflict on a later sync.

The likely reason it held: `state.json` is small and written after the
save it describes, so a partially replicated game usually presents
either the previous consistent state or the new one, and a checksum
mismatch resolves to a transfer rather than to corruption.

Status

Observed, not proven.

This is a single successful observation, not a systematic test. It has
not been run against large saves, slow or interrupted links, or
simultaneous writes from both devices - the cases where a partially
replicated directory is most likely to be read as though it were
complete. Treat mid-replication synchronization as unverified until
those are covered.

Known gap

`SyncthingStorageBackend.conflicts()` detects the `*.sync-conflict-*`
files Syncthing writes when it resolves simultaneous edits, but no
command surfaces them. If Syncthing produces one, SaveCloud currently
stays silent about it.

---

### Backends report their own problems

Decision

`BaseStorageBackend.provider_warnings()` returns a list of strings and
defaults to empty. `savecloud doctor` prints whatever the configured
backend returns, without knowing which backend it is.

Reason

The Syncthing acceptance test above recorded a gap: Syncthing writes
`*.sync-conflict-*` files when two devices edit the same file at once,
SaveCloud never reads them, and nothing reported they existed. The save
they duplicate looks perfectly healthy.

The obvious fix - have diagnostics check for conflict files - would put
Syncthing-specific knowledge in a service, which is exactly what the
framework layer exists to prevent. Asking the backend instead keeps
that knowledge where the rest of Syncthing's behaviour already lives,
and means a future provider can report an expired token or an exceeded
quota through the same path with no change to diagnostics.

A provider that raises while reporting is itself reported, rather than
taking diagnostics down. Diagnostics runs against broken installations
by definition.

Status

Accepted. Closes the known gap recorded in the milestone 9 acceptance
test.

---

### A launcher may declare that it cannot observe the game

Decision

`BaseLauncher.tracks_process_exit()` defaults to True. `SteamLauncher`
returns False, and `AutoSyncService.play()` refuses any launcher that
does.

Reason

`steam -applaunch` returns as soon as Steam has been told to start the
game, not when the game exits. Waiting on that process therefore
proves nothing. `play` would capture the save immediately, upload the
state from *before* the session, and mark it synchronized - so the
session's progress would be silently discarded on the next sync, and
the runtime would claim everything was fine.

Refusing is the only safe option. Warning would not be enough: the
default path would still destroy progress, and the warning would
appear before the damage rather than after.

Status

Accepted

---

### Steam starts SaveCloud, not the reverse

Decision

`savecloud wrap <game-id> -- %command%` goes in a game's Steam launch
options. Steam runs SaveCloud, SaveCloud synchronizes, runs the command
Steam supplied, waits, and captures the save.

Reason

It fixes the process tree. The game becomes a child of SaveCloud rather
than of Steam, so its exit is observable and the save can be captured
afterwards - exactly what the Steam launcher cannot do.

It also removes a whole class of knowledge SaveCloud would otherwise
need. Steam already knows how to start the game, which Proton build to
use, and which runtime to inject. `%command%` carries all of it, so
native and Proton games work identically and no launcher is consulted
at all.

The command's exit code is passed through, so Steam reports what the
game did rather than what SaveCloud thought of it.

Consequence

Click must not interpret the game's own options. Pass-through parsing
is enabled, which means option parsing stops at the game ID, so
SaveCloud's own flags only work before it. Placing one after would
otherwise be handed to the game; that case is detected and rejected
rather than left to fail obscurely.

Status

Accepted

---

### The Proton adapter finds the prefix but asks about the save

Decision

`steam-proton` resolves an App ID to its Proton prefix automatically,
then presents the directories inside it and asks which holds the save.
The choice is recorded as `<app-id>:<relative-path>`.

Reason

The prefix is deterministic - `steamapps/compatdata/<app-id>/pfx` - so
guessing it is safe. What lives inside is not: Windows games use
AppData/Roaming, AppData/LocalLow, Documents/My Games, and Saved Games
more or less interchangeably, and plenty invent their own.

Choosing wrong would synchronize the wrong directory and look like it
was working, which is worse than one extra question during
registration. This is the project principle that manual configuration
beats incorrect automation, applied where it actually bites.

Status

Accepted

---

### Milestone 10 acceptance test: Steam launching an emulated game

Context

`wrap` had been exercised against synthetic commands and a simulated
Steam directory layout, but never against a real Steam client, a real
launch-options string, or a real emulator.

Setup

- BC250 running the game through Steam.
- The Steam entry created by Steam ROM Manager, so `%command%` expands
  to an Eden AppImage invocation with a ROM path.
- Steam launch options:

      /home/hooman/SaveCloudPotato/.venv/bin/savecloud wrap <game-id> \
          -- mangohud %command%

- The game registered with the `eden` adapter.

Result

The full chain worked: Steam started SaveCloud, SaveCloud synchronized
and ran mangohud, mangohud ran Eden, and the save was captured when
Eden exited.

Finding: the wrapper must be an absolute path

SaveCloud is installed in a virtualenv. Steam does not run launch
options through a shell that has that virtualenv activated, so a bare
`savecloud` is not on PATH and the game fails to start with no useful
error. The absolute path to the virtualenv's script works, because its
shebang points at the virtualenv's own interpreter.

Worth remembering for any future installation instructions: a wrapper
invoked by another program cannot assume the environment a terminal
would have.

Finding: nesting wrappers is fine

`savecloud wrap ... -- mangohud %command%` puts three processes in a
chain. Each is a child of the last, so Eden's exit still propagates
back to SaveCloud and the save is captured. Nothing about `wrap`
assumes it is the immediate parent of the game.

Status

Confirmed for this configuration.

Still untested

- The `steam-proton` adapter against a real Proton game. Prefix
  discovery and save-directory selection have only been exercised
  against a constructed directory layout.
- `wrap` on the Steam Deck.
- A game that forks and detaches rather than exiting, where the
  captured save would be taken while the game was still running.

---

### SaveCloud does not write Steam's shortcuts.vdf

Decision

SaveCloud will not create or modify non-Steam shortcuts. Steam
integration is achieved entirely through launch options the user sets
themselves.

Reason

`shortcuts.vdf` holds every non-Steam game, including its
LaunchOptions, so writing it would let `register` add a game to Steam
and configure the wrapper in one step. Three things make that a bad
trade.

Steam is not the only writer. Steam ROM Manager manages the same file
and regenerates entries on its runs. Two uncoordinated writers means
either program can silently undo the other's work, and the first real
installation this was tested against uses exactly that combination.

Steam caches the file in memory and rewrites it on exit, so any edit
made while Steam is running is discarded. A CLI would have to demand
Steam be closed, which is a poor thing to require of a command run
before playing.

The blast radius is disproportionate. The format is binary, and a
malformed write loses every non-Steam shortcut rather than just the
one being added - for a ROM library, that is hundreds of entries in
exchange for saving one paste.

Alternative considered

Reading the file to check whether a game's launch options actually
invoke SaveCloud, and warning from `doctor` if not. Rejected for now:
it needs a binary VDF reader to verify a single string, and the failure
it would catch is already self-announcing - a game launched from Steam
without the wrapper simply never updates `Last Sync`.

Status

Accepted. Reconsider only if Steam gains a supported way to set launch
options, or if a read-only check turns out to be worth its machinery.
