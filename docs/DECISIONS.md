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

Status

Accepted
