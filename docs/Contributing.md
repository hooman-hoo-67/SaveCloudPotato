# Contributing

The guiding principle: every new feature should look like it was part
of the original design. If a change requires touching unrelated
components, that usually means it does not fit the architecture yet.

---

## Setup

```bash
pip install -e . pytest
pytest
```

Tests create a SaveCloud installation in a temporary directory. They
never touch your real one.

---

## Dependency Rules

Dependencies flow downward.

```
Commands  →  Services  →  Models  →  Frameworks  →  Filesystem
```

| Component | May depend on |
|-----------|---------------|
| Commands | Services, models, utilities |
| Services | Models, registries, frameworks, utilities |
| Models | Standard library |
| Adapters, launchers, storage backends | Models, config, utilities |
| Utilities | Standard library |

Two rules are worth stating explicitly because they are easy to break:

**Commands never import other commands.** Anything two commands need
goes in `savecloud/utils/`. `utils/output.py` exists because `sync` and
`play` both report conflicts.

**Frameworks never import each other.** An adapter knows nothing about
launchers; a storage backend knows nothing about emulators. They meet
only in the service layer.

---

## Adding a Storage Backend

1. Subclass `BaseStorageBackend`, or `FilesystemStorageBackend` if the
   provider presents itself as a directory.
2. Register it in `StorageRegistry`.
3. Done. `SyncService` needs no changes.

A directory-shaped provider usually needs only two methods:

```python
class MyBackend(FilesystemStorageBackend):

    @staticmethod
    def display_name() -> str:
        return "My Provider"

    @classmethod
    def storage_root(cls) -> Path:
        return ConfigurationService.load().storage_root
```

`available()` matters more than it looks. A backend that is configured
but unreachable must return `False`, not raise — SaveCloud is expected
to keep working offline. If the backend cannot be used, say why in
`unavailable_reason()`; that string is shown to the user.

Do not create a missing root if its absence means the provider is not
actually set up. The Syncthing backend refuses rather than creating a
directory that would silently never replicate.

Override `provider_warnings()` if your provider can end up in a state
only it can detect - a replication conflict, an expired token, a quota.
`savecloud doctor` surfaces whatever it returns without knowing what
the provider is.

---

## Adding an Adapter

1. Subclass `BaseAdapter`.
2. Implement `locate_save()` and `validate_save()`.
3. Register it in `AdapterRegistry`.

Adapters locate and validate saves. They never launch games,
synchronize, or touch the library.

---

## Adding a Launcher

1. Subclass `BaseLauncher`.
2. Implement `validate()` and `launch()`.
3. Register it in `LauncherRegistry`.

Launchers start processes. They never locate saves or synchronize.

---

## Adding a Command

```
Validate input  →  Call a service  →  Display the result
```

Commands parse arguments, prompt, call services, and print. They do not
read JSON, synchronize, launch, or locate saves.

Register single-action commands in `cli.py` with `app.command()`. Only
use `add_typer()` for a group with real subcommands — mounting a
single-action command as a sub-Typer turns it into a Click group, and
options after its positional argument stop parsing.

---

## Adding a Service

Ask first whether it owns a distinct business domain. If not, extend an
existing service. A service that wraps one or two helper functions
should be a utility instead.

---

## Testing

Test behaviour, not implementation:

- Does registration create the expected files?
- Does an import create a version?
- Does a restore preserve history?
- Does the configured backend resolve?

Fixtures live in `tests/conftest.py`. `register_game()` sets up a game
with a device profile; `write_save()` and `read_save()` handle save
contents.

Two things are worth testing directly whenever you touch them:

**Conflict handling.** Verify that nothing is overwritten, not merely
that an error was raised.

**Storage failure.** Verify the library still holds the save. A save
must survive a backend being unreachable.

`tests/test_multi_device.py` runs two installations against one storage
root. New synchronization behaviour belongs there.

Before opening a pull request:

```bash
pytest
python -m pyflakes savecloud/ tests/
```

---

## Documentation

Update the docs in the same change as the code.

- Architecture change → `docs/Architecture.md`
- Behaviour change → `docs/API.md`
- Model change → a new `docs/DATA_Model_vX.Y.md`
- Any decision worth questioning later → `docs/DECISIONS.md`

`DECISIONS.md` records *why*. A decision that only says what changed
will not help whoever revisits it.

---

## Style

- Descriptive names over abbreviations.
- One task per function.
- Raise meaningful exceptions; never swallow errors silently.
- Comments explain *why*, not *what*.
- Match the surrounding code. Consistency beats preference.

---

## Common Mistakes

| Mistake | Instead |
|---------|---------|
| Business logic in a command | Move it to a service |
| Platform knowledge in a service | Move it to an adapter, launcher, or backend |
| Duplicated configuration | `InstallationConfig` |
| Synchronizing a working save folder | Everything passes through the library |
| A lower layer importing a higher one | Invert the dependency |
| Timestamps to decide which save is newer | Checksums |
