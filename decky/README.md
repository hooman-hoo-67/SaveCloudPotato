# SaveCloud for Decky Loader

SaveCloud in Gaming Mode, on a Steam Deck.

The desktop interface is where games are set up: choosing an adapter,
locating a save folder, pairing a device, entering cloud credentials.
None of that belongs on a controller, so none of it is here.

What is here is the part that has to work where the Deck is actually
used - seeing whether each game's save is current, synchronizing it, and
choosing a side when two devices have both moved on.

## What it can do

- Show every registered game with its state, checked when the panel is
  opened rather than once at boot.
- Synchronize one game, or all of them.
- Resolve a conflict, with both saves described - which device wrote
  each one, how long ago, and which version it is.
- Show recent log lines, because a failure during a session otherwise
  leaves no trace reachable without rebooting to Desktop Mode.

## What it needs

SaveCloud itself, installed for the desktop user. Install it in Desktop
Mode and run:

```
savecloud install
```

That puts the command at `~/.local/bin/savecloud`, which is the first
place the plugin looks. An AppImage left in `~/Applications`,
`~/Downloads` or the home directory is found too.

Without it the panel says so and does nothing else - being uninstalled
is a normal state, not an error.

## How it works

The backend does not import SaveCloud. It runs the `savecloud` command
and reads its `--json` output.

That is not indirection for its own sake. Decky runs plugin backends
**as root**, under Decky's own interpreter - neither of which is where
SaveCloud is installed. A command run as root against the user's `HOME`
would write root-owned files into `~/.local/share/savecloud` and lock
someone out of their own save library, from inside a plugin meant to
protect it. So every invocation drops to the desktop user first.

Nothing in the backend raises. Gaming Mode has nowhere to show a
traceback, so timeouts, crashes, silence and non-JSON prose all come
back as documents the panel can render.

The environment is built rather than inherited, since root's would send
the command looking in the wrong places. `SSL_CERT_FILE`, `SSL_CERT_DIR`
and the proxy variables are carried across anyway: certificate trust is
configured through the environment and nowhere else, and dropping it
would mean a Deck that syncs fine from a terminal failing from the
panel with a certificate error and no obvious cause. That matters on any
network that inspects TLS, which university and workplace networks
commonly do.

Those have to be set where **Decky** sees them - a shell profile is read
by your terminal, not by a system service. Installing the intercepting
authority into the system trust store instead needs no variables at all,
and is the better fix where it survives updates.

The backend is covered by `tests/test_decky.py` in the repository root.
The React side can be type-checked and built anywhere, but only a real
Deck can tell you it looks right.

## Building

```
npm install
npm run build
```

That produces `dist/index.js`. `npm run typecheck` checks the frontend
without building it.

## Installing by hand

Decky loads plugins from `~/homebrew/plugins`. A plugin directory needs
the manifest, the backend and the built bundle:

```
SaveCloud/
  plugin.json
  package.json
  main.py
  dist/index.js
```

Copy those onto the Deck as `~/homebrew/plugins/SaveCloud`, then restart
Decky:

```
sudo systemctl restart plugin_loader
```
