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
