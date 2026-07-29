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

---

## 2026-07-29

### Provider credentials never leave the device that holds them

Decision

Credentials live in `providers/<name>.json`, written with owner-only
permissions, in the part of the SaveCloud home that is never
synchronized. Each device authorizes separately.

Reason

The registry and library are synchronized precisely so a second device
needs no setup. Extending that to credentials would be the obvious
convenience and the wrong one: a refresh token grants full access to
someone's cloud storage, and replicating it means every device, and
every backup of every device, holds a copy. Losing one device would
mean revoking access everywhere.

Setting up a new device costs one authorization. That is a small price
for a secret that does not travel.

Status

Accepted

---

### Dropbox authenticates with a refresh token, not an access token

Decision

Setup exchanges a one-time authorization code for a refresh token,
which is what gets stored. Access tokens are obtained from it as
needed and cached in memory for the process lifetime.

Reason

Dropbox access tokens expire after about four hours. Storing one would
mean synchronization silently stopping partway through the same day,
with an authentication error that looks like a bug rather than an
expiry. Refresh tokens do not expire unless revoked.

This is why the authorization URL must carry
`token_access_type=offline`. Without it Dropbox returns only a
short-lived token, so setup checks for the refresh token explicitly and
fails with that explanation rather than storing something that will
stop working.

Status

Accepted

---

### A backend prepares itself

Decision

`BaseStorageBackend.requires_setup()` and `setup()` join
`provider_warnings()` as extension points. `savecloud config provider`
calls them without knowing which provider it is talking to, and the
Dropbox setup walkthrough lives beside the Dropbox backend.

Reason

The alternative is a command that grows a branch per provider, which is
what the framework layer exists to prevent. Setup is provider
knowledge, so it belongs with the provider - the same reasoning that
put conflict-file detection in the Syncthing backend rather than in
diagnostics.

The consequence is that a storage module imports typer, which the
dependency rules would otherwise discourage. That is accepted
deliberately: setup is inherently interactive, and the alternative
puts provider knowledge in the command layer, which is worse.

Status

Accepted

---

### storage_root names a folder, not a path, for Dropbox

Decision

For Dropbox, only the last component of `storage_root` is used, giving
a folder at the root of the app's Dropbox space.

Reason

`storage_root` is a filesystem path for the local and Syncthing
backends. Someone switching an existing installation to Dropbox
carries over a value like `/home/you/SaveCloudRemote`, and using it
verbatim would build a chain of empty folders inside Dropbox mirroring
their home directory.

Taking the final component means switching backends does something
sensible without a separate setting, and `config root SaveCloud`
reads naturally.

Status

Accepted. Revisit if a provider ever needs genuinely nested remote
paths.

---

### Version history is bounded by default

Decision

`InstallationConfig.version_retention` caps how many historical
versions each game keeps, defaulting to the two most recent. Zero keeps
everything. The limit is applied in the library and in storage alike.

Reason

Every synchronization that finds a change creates a version, and
`play` synchronizes twice per session. History therefore grew without
limit - and once a cloud backend was in use, every one of those
versions was uploaded, costing a network round trip per file.

Two is enough for what history is actually used for: undoing a bad
session, and the one before it.

This narrows an earlier principle. "Nothing SaveCloud overwrites is
unrecoverable" now holds within the retention window rather than
forever. That is a real trade, which is why it is configurable and why
zero remains available.

Consequences found while implementing

Pruning must happen in `create_version_from`, the single point where
versions are created. Doing it at call sites would eventually mean a
path that creates a version and forgets to trim.

`restore_version` had to be reordered. It preserved the current save
first, which creates a version, which prunes - and the version being
restored is among the oldest, so it could be deleted moments before
being read. The version is now copied aside before anything else
happens.

Storage must be trimmed too, and after uploading rather than before.
Trimming only locally would leave a device that still holds older
history re-uploading what another device had just pruned, and the two
would never agree.

Status

Accepted

---

## Proton asks two questions, not one

Date: 2026-07-29

Context

Registering a Proton game through the interface meant typing a Steam
App ID into a text field. The adapter already knew better - its CLI
prompt lists installed games and then offers the plausible save
folders inside the prefix - but none of that was reachable from a
window, because `prompt_identifier()` is interactive terminal code.

Decision

Choosing the `steam-proton` adapter replaces the identifier field with
two controls: which installed game, and which folder inside its
prefix.

Both come from Steam's own files - `libraryfolders.vdf` for what is
installed, `compatdata/<app-id>/pfx` for the prefix. Nothing needs
Steam to be running, and no account or API is involved.

The save folder is offered rather than decided. Windows games use
AppData/Roaming, AppData/Local, AppData/LocalLow, Documents/My Games,
Saved Games, and plenty of inventions of their own; all are scanned,
and silently synchronizing the wrong directory is worse than one more
question. The field is editable and has a Browse button that opens
inside the prefix, because a guess can be wrong.

Candidates are ordered by how recently something inside was written,
with empty folders last. Ordering them by the list of locations
instead meant AppData/Roaming was always preselected - which looks
like a recommendation while being nothing more than which line came
first. A game that has just been played has touched its save, and
folders left empty on first launch are exactly the ones to rank down.

Each is labelled by its place in the prefix and when it was last
written, because an absolute path here is ninety characters of prefix
nobody needs to read, and "written yesterday" against "empty" is what
actually distinguishes the save from the folders beside it.

Consequences

The recorded identifier is `<app-id>:<path relative to the prefix
user directory>`. Steam moves prefixes between libraries when a game
changes drive, so an absolute path would not survive it.

A folder outside the prefix is refused. It would be a mistake this
could have caught, and synchronizing the wrong tree is exactly the
failure the adapter exists to avoid.

A game with no prefix is reported as needing to be launched once,
rather than as an error. That is what a game that has been installed
and never played looks like.

Found while building: a combo box owns its own line edit, and moving
that into the shared directory row took it out of the combo box, which
then rendered empty with the field on the line below. Browse is a
separate helper for that case.

Status

Accepted

---

## A downloaded AppImage is not an installed program

Date: 2026-07-29

Context

An AppImage is a file that has been downloaded. It is called
`SaveCloud-x86_64.AppImage`, it is wherever the browser put it, it is
not on PATH, and nothing knows it exists.

So `savecloud sync` in a terminal finds nothing, and the only way to
open the interface is to find the file. For a beta that is the
difference between something usable and something that technically
works.

Decision

`savecloud install` links `~/.local/bin/savecloud` to wherever the
build is, writes a desktop entry naming the real file, and installs
the icon. `--remove` undoes it. The interface offers the same under
Settings.

Offered rather than performed. The AppImage works without any of it,
and writing to someone's home directory because they opened a program
is not a reasonable default.

Consequences

A symlink rather than a copy, so replacing the AppImage updates the
command.

Steam launch options prefer the link once it exists. Steam keeps them
until they are edited by hand, so the path written in should outlive
an update - which a direct path to a file named after its version does
not. The link is only trusted when it leads back to this build; one
left by another installation would send Steam somewhere unexpected.

The desktop entry's `Exec` names the file rather than `savecloud`,
because a desktop entry is read by things that do not share this
process's PATH.

`~/.local/bin` not being on PATH is a warning rather than a failure.
The link is still correct, and saying so is better than refusing.

Found while testing against the real artifact: the icon was never
installed, because it was not among the bundle's data files. The
command reported success and the menu entry had no icon.

Status

Accepted

---

## One packaged file, two behaviours

Date: 2026-07-29

Context

SaveCloud has two entry points, and packaging usually means choosing
one. Steam launch options invoke a command line; someone opening the
application expects a window.

Shipping two artifacts would mean two things to install, two paths to
keep straight, and a launch option pointing at the one nobody opens.

Decision

One binary, dispatching on arguments: with them it is the CLI, without
them the interface.

Built with PyInstaller, wrapped as an AppImage on Linux and a zipped
directory on Windows.

Consequences

`savecloud_executable()` had to learn about packaged builds. Inside an
AppImage, `sys.executable` points into a temporary mount that differs
on every run - writing it into Steam would produce launch options that
work exactly once. The `APPIMAGE` variable names the real file and is
checked first, with a frozen build's own `sys.executable` next.

That variable can be inherited by a process that is not an AppImage,
so it is only believed when it names something that exists.

Adapters, launchers, and storage backends are reached through
registries, so nothing imports them by name and PyInstaller cannot
see them. They are declared as hidden imports; without that the build
succeeds and then reports no adapters at all.

The artifact is 56MB compressed, most of it Qt. `libicudata` alone is
31MB uncompressed and could be dropped, but Qt uses ICU for text
handling and save paths are arbitrary - so it stays.

Windows binaries cannot be produced on Linux, so each platform builds
on itself in CI. Manual runs leave artifacts without creating a
release, which makes it possible to test a build before promising one.

Status

Accepted

---

## Launch options name the executable by path

Date: 2026-07-29

Context

The line offered for Steam was `savecloud wrap <game> -- %command%`,
which assumes `savecloud` is on the PATH Steam runs with.

For a pipx or system installation it is. For a virtual environment -
the way SaveCloud is actually installed today - it is not: Steam is
not started from a shell that activated anything. The bare name
resolves to nothing, and the game fails to start with no explanation
of why.

Decision

The line names the executable by absolute path, resolved on the device
the options are being written for. That is the only device they will
ever be pasted into, so there is nothing to make portable.

Resolution tries, in order: how this process was started, the
directory beside the running interpreter, `sys.prefix`, and finally
PATH. A bare name remains the fallback when none of those find
anything, which happens when SaveCloud is run as a module from a
source checkout.

Consequences

`sys.executable` is deliberately not resolved. A virtual environment's
`python` is usually a symlink to the system interpreter, and following
it lands outside the environment - where SaveCloud is not installed.
This was found by writing the check and watching it return the wrong
answer.

The path is shell-quoted. Steam splits the line, so a path containing
a space would arrive as two arguments and nothing would run.

`savecloud-gui` resolves to `savecloud` beside it, since the interface
is a different script in the same directory.

The line is computed rather than stored, so it stays correct if the
installation moves - but launch options already pasted into Steam do
not. Moving a virtual environment means pasting them again.

Status

Accepted

---

## A launch command is optional

Date: 2026-07-29

Context

Registration required a launch command, and writing one is fiddly -
quoting an AppImage path and a ROM path correctly, by hand, before
anything can be registered.

It buys almost nothing. `savecloud play` is the only thing that uses
it, and `play` is not how these games get started: Steam is. Steam
runs `savecloud wrap`, hands over the real invocation as `%command%`,
and SaveCloud never has to know how to launch anything.

Decision

`DeviceProfile.launch_command` defaults to empty, and nothing requires
it. What the interface offers instead is the line to paste into
Steam - shown in the detail pane, in the game's settings with a Copy
button, and in a dialog the moment a game is registered, which is when
someone is about to go and add it to Steam anyway.

Consequences

`play` refuses without one, and names `wrap` when it does. Refusing is
right; refusing without saying what to do instead is not.

`doctor` reports a missing command as OK rather than a warning, with
the Steam line as its remedy. It is a configuration, not a fault.

Profiles written before this load with an empty command rather than
raising, since the key simply will not be there.

The line is read-only wherever it is shown. It is derived from the
game ID, so editing it could only produce one that does not work.

Status

Accepted

---

## Forms validate in place

Date: 2026-07-29

Context

Registering a game asks for eight things, and the one most likely to
be wrong - where the save lives - cannot be checked without asking an
adapter.

A dialog that closes and then reports a failure has thrown away seven
correct answers along with the wrong one.

Decision

Forms submit through the facade and stay open when it refuses, showing
the reason inside the dialog with every field still populated.

`locate_save` is exposed separately from `register` for the same
reason: the save path can be confirmed before anything is written.

Consequences

Dialogs run their work on the interface thread rather than a worker.
A modal dialog is already blocking, and the alternative is a dialog
that must survive across a thread boundary to receive its own result.
Registering is local work; the only slow one is pairing, which
downloads a library.

The forms read their choices from the registries, so a new adapter or
launcher appears without the interface being changed. The identifier
label follows the adapter, because "Title ID" and "Save Folder" are
not the same question.

The adapter defaults to `manual` rather than whichever sorts first.
Reading a folder path as a Title ID fails in a way that blames the
person for the default.

The game ID is suggested from the display name until someone edits it,
then left alone. A suggestion that overwrites what was typed is not a
suggestion.

Removing a game asks first and says what is deleted. "Remove" sounds
reversible; deleting the library is the one action in the interface
that is not.

Adapters declare whether their identifier is a filesystem path, and
the form offers Browse only when it is. A Title ID and a save folder
are not the same question, and a Browse button beside a Title ID field
sends people looking through their filesystem for a number - reported
from the field. It defaults to False, so an adapter that says nothing
gets a plain field: a missing Browse button is a smaller mistake than
a misleading one.

Pairing cannot know which to ask for. The adapter arrives with the
manifest, and the manifest arrives when the game is adopted, so the
field is labelled neutrally until then and corrected the moment
adopting succeeds - which happens before locating the save, so a first
failed attempt still leaves the form asking the right question.

The directory picker is built rather than taken from the convenience
function, so hidden directories can be shown. Emulator saves live
under `~/.local/share`, and every component after the home directory
is hidden - a picker with Qt's default filter cannot reach a single
Linux save. Qt's own dialog is used rather than the desktop's, because
the native one keeps a notion of hidden files this cannot set.
Reported from the field: an Eden save path could not be selected at
all.

Dropbox authorization opens a real browser rather than embedding one.
The browser someone already trusts with their password is not one this
application should be reimplementing, and Dropbox hands back a code to
paste anyway. A reused code is the most common failure and the least
obvious, so it is named explicitly.

Status

Accepted

---

## Interface actions return outcomes, not exceptions

Date: 2026-07-29

Context

Adding buttons to the read-only window meant deciding how a failure
crosses back from a worker thread.

A window cannot wrap a call in `try` when the call happens on another
thread. The exception surfaces inside the worker, and whatever
arrives at the interface is whatever the worker chose to send.

Decision

Facade readers may raise. Facade actions return an `Outcome` -
`ok`, `message`, and `conflict` - and never raise.

`conflict` is a separate field rather than an error string because it
is not a failure. Both sides hold real play time, and the interface
must ask which to keep rather than report that something went wrong.
The dialog offers both saves by name and says the losing one is kept
as a version, which is what makes the choice safe to offer at all.

Consequences

The interface locks its controls while an action runs. The services
are written for one caller; nothing below the interface prevents a
second sync starting on top of the first, so the interface has to.

Every action refreshes when it finishes, and refreshing rebuilds the
game list. The selection is restored explicitly - without that, the
buttons would be unusable after the first action, because the game
they act on would no longer be selected.

Setting the auto-sync checkbox from stored state has its signals
blocked. Otherwise displaying a game would write back the value just
read, and selecting a game would run an action.

A game not paired on this device disables every per-game control:
nothing knows where its save lives here.

Restoring asks first. It is reversible - what it replaces becomes a
version - and the dialog says so, because a confirmation that does not
explain the stakes only teaches people to dismiss it.

Status

Accepted

---

## The desktop interface imports services; the plugin will not

Date: 2026-07-29

Context

Two front ends are planned. The desktop application is Python, so it
can import SaveCloud directly. A Decky Loader plugin is React running
under a different runtime, and cannot.

Decision

The desktop interface calls services in-process, through a facade.
`--json` stays for front ends that cannot do that.

Two integration paths sounds like the drift this was meant to avoid,
but they meet at the service layer rather than diverging below it.
Spawning a subprocess and parsing JSON to ask a question answerable by
a function call in the same interpreter would buy nothing and cost a
process launch per refresh.

Widgets never import a service. `GuiFacade` returns plain dataclasses,
so a view can be tested without an installation, and the questions the
interface asks are visible in one file rather than scattered across
windows.

Consequences

PySide6 is an optional dependency. The CLI installs and runs without
Qt, which matters for a headless machine and for a Deck running only
the plugin. `savecloud.gui.app` imports Qt inside `main()` so a missing
install produces an instruction rather than a traceback.

Anything that touches the network runs on a thread. Qt redraws nothing
while a slot executes, so probing a cloud provider on the interface
thread would freeze the window - the desktop equivalent of the silent
minute progress reporting was added to explain.

The first version is read-only. Threading, progress, and error
rendering are exercised on something that cannot destroy a save before
any button can.

Findings while implementing

`QThreadPool` deletes a runnable as soon as `run()` returns, taking its
signals object with it, while queued deliveries to the interface
thread may still be in flight. This segfaulted under test rather than
failing. Workers now disable auto-deletion and are released after
delivery instead.

`GameRuntime.current_version` is written at registration and never
updated - it reads 0 forever. `LibraryMetadata.latest_version` is the
real number, and `current_version` there means something else again:
which version the current save was restored from. `info` had been
displaying the runtime's copy, so it always reported version 0. Both
now read the library, which owns save data, and label the two numbers
separately.

`info` called `load_profile` unguarded, raising FileNotFoundError for
a game registered but not paired on this device.

Status

Accepted

---

## Automatic sync is a per-device switch

Date: 2026-07-29

Context

`sync_enabled` on the manifest was the only way to stop a game
synchronizing, and the manifest is synchronized. Turning it off
anywhere turned it off everywhere.

That is the wrong shape for the case that prompted it: a device on a
metered or unreliable connection wanting to stop uploading, without
changing anything for the machine it shares saves with.

`DeviceProfile.enabled` already existed, already documented as
"whether SaveCloud is enabled for this game on this device", and was
read, displayed, and never checked by anything.

Decision

Make it real rather than adding a second field beside it.

`sync_enabled` on the manifest keeps its meaning: this game is managed
at all, everywhere. `enabled` on the profile means this device takes
part. Both must be on for automatic synchronization to happen.

Consequences

The switch governs automatic behaviour only - `play`, `wrap`, and a
bare `savecloud sync`. Naming a game explicitly still synchronizes it,
because the setting expresses a preference about background work
rather than permission to touch the save.

A device with no profile for a game follows the manifest alone. It has
nothing to say about a game it has never been set up for.

`savecloud autosync GAME_ID [on|off]` exposes it, and `info` and
`list` report it. Two concepts is one more than before, so both places
that show it say which is which.

Finding while implementing: `info` called `load_profile` unguarded, so
a game registered but not yet paired on this device raised
FileNotFoundError out of the service layer instead of explaining
itself. It now reports the state and names `pair`.

Status

Accepted

---

## A --json flag, not a second set of commands

Date: 2026-07-29

Context

Two graphical front ends are planned - a desktop application and a
Decky Loader plugin - and they will differ a great deal from each
other. What they must not differ in is what they call.

The risk is a plugin reimplementing sync logic in another language
because driving the CLI is awkward. Two conflict resolvers that
disagree is a worse outcome than any amount of duplicated interface
code.

Decision

A top-level `--json` option. Commands that have a structured form emit
one JSON document on stdout; everything else is unchanged.

Considered and rejected: a parallel set of machine-readable commands,
or a daemon with a socket. A GUI and a person ask the same questions -
what is registered, what would sync do, what is wrong - and two code
paths answering them would drift apart, with the human one getting the
attention.

Consequences

`--json` changes how a command reports, never what it does. Exit codes
are identical either way, so a caller can check success without
parsing anything.

Failures are documents too. A conflict reports its available
resolutions rather than prose telling a person which flag to type,
because that is the case a GUI must render as a choice rather than an
error.

Progress goes to stderr, so stdout stays parseable on its own. The
progress reporter is suppressed entirely in JSON mode regardless.

The flag is process-wide state set by the top-level callback, which
tests must not let leak between invocations. One asserts exactly that.

Interface coverage is deliberately partial: the read commands a front
end polls, plus `sync`. Interactive commands like `register` and
`pair` prompt, and a prompt has no JSON form worth inventing before a
GUI exists to say what it needs.

Status

Accepted

---

## Cloud transfers run in parallel

Date: 2026-07-29

Context

Syncing to Dropbox from a Steam Deck was slow enough to be reported as
a problem in its own right. Progress reporting had already established
it was not a hang, which left the question of why it took so long.

A save is many small files, and each one cost a full round trip issued
one after another. The transfer was latency-bound, not bandwidth-bound:
almost all of the time was spent waiting rather than moving data.

Decision

Uploads and downloads run across a pool of eight threads.

Measured against the in-memory fake with an 80ms round trip injected -
typical for a Deck on wireless - a 40-file save went from 8.1s to 2.9s.

Eight is deliberately modest. Dropbox rate-limits per account, and a
save is not worth being throttled over.

Consequences

`Progress` is now stepped from several threads, so its counter is
locked. Without that, two workers finishing together would lose a
count and the reported total would drift below the real one.

The access token is refreshed under a lock. Every worker shares one
client, so an expired token would otherwise have every thread
refreshing it simultaneously.

Destination directories are created before the workers start rather
than inside them, so two threads writing into the same new folder
cannot race creating it.

The first failure is raised once the pool has drained. Continuing
after a failed file would leave storage holding a save that never
existed on any device, and reporting success for it would be worse
than the delay this change removes.

Status

Accepted

---

## A terminated game is not a crashed game

Date: 2026-07-29

Context

`after_exit` treated any non-zero exit code as a crash, and a crash as
a reason to publish nothing.

Two things were wrong with that.

The code returned before capturing, so a crashed session was not
uploaded *and* not saved locally - it was discarded. The comment above
it claimed the save was "captured locally but not pushed", which is
what should have happened and not what the code did. A crash is when a
session is least reproducible, so discarding it is the worst available
response.

Worse on a Steam Deck: `subprocess` reports a signal death as the
negated signal number, and Gaming Mode's Exit Game sends SIGTERM. So
an ordinary session arrived as -15, was classified as a crash, and its
save was dropped. Reported from the field as "it downloads on launch
but never uploads in Gaming Mode".

Decision

Capture always, publish selectively.

Every session is captured into the library whatever the exit code. The
library is versioned and retention bounds it, so a bad capture is
recoverable and a missing one is not.

SIGTERM and SIGINT count as ordinary exits and publish normally. They
mean "stop now", which is how Steam's Stop button and Gaming Mode both
close a game. Any other non-zero code captures, marks the save
pending, and says which command publishes it once the player has
decided the save is good.

`wrap` also forwards those signals to the game rather than dying on
them. Steam signals SaveCloud, not the game; Python's default action
would have ended the wrapper immediately, so the save would never be
captured - which is the entire reason the wrapper is in the way. The
handler passes the signal on, the game flushes and exits, and
SaveCloud is still alive to capture it.

Consequences

Handlers are installed around the wait and restored afterwards, so a
launch does not leave the process's signal disposition changed.

Installing them can fail off the main thread. That is tolerated rather
than fatal: waiting unprotected is still better than refusing to
launch.

SIGKILL remains unsurvivable, by definition. If Steam escalates, the
session is lost. Nothing in a wrapper can fix that.

Status

Accepted

---

## Setting the retention window applies it

Date: 2026-07-29

Context

Trimming at version creation means retention is enforced as history
grows. It is never enforced on history that already exists.

The first report of this was someone lowering the window and then
synchronizing a game they had not played since. Sync found nothing to
do, so no version was created, so nothing was trimmed, and seven
versions stayed where the window said two. Nothing was broken - the
backlog would have cleared on the next real save - but a setting that
takes effect at an unpredictable future moment reads as one that does
not work.

Decision

`config retention` applies the window when it is set: across every
registered game, in the library and in storage, reporting what it
removed.

Backends gained a public `prune(game_id, keep)` for the storage half.
It is abstract rather than defaulting to a no-op, because a backend
that silently ignored retention would grow without bound and nothing
would say so.

Consequences

Retention now has two enforcement points rather than one - at creation
and at configuration - which is the cost of a policy that applies to
data already at rest. They share `SaveCloudLibrary.prune_versions`, so
the rule itself is still written once.

Applying the window deletes data, so the command reports per game what
it removed rather than only confirming the setting.

Unreachable storage does not fail the command. The setting is local
and the library is local; refusing to record either because a cloud
provider is offline would be the wrong trade. Storage is trimmed on
the next upload, and the command says so.

Status

Accepted
