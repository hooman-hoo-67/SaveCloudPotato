"""
SaveCloud's Decky Loader backend.

Decky plugins run as root, under Decky's own Python. Neither of those
is where SaveCloud lives, so this does not import it - it runs the
`savecloud` command and reads its `--json` output, which is what that
interface was added for.

Running as root matters more than it looks. SaveCloud writes to
`~/.local/share/savecloud`, and a command run as root with the user's
HOME would create files the user can no longer write - locking someone
out of their own save library from inside a plugin that was supposed to
help. Every invocation therefore drops to the desktop user first.
"""

from __future__ import annotations

import asyncio
import json
import os
import pwd
from pathlib import Path

import decky

#
# How long to let a command run. A sync on a slow connection is the
# long one; anything past this is stuck rather than working, and Gaming
# Mode has no way to show a spinner forever.
#

TIMEOUT_SECONDS = 300

#
# Where a user installation puts the command. `savecloud install`
# creates the first; the rest are where someone might have unpacked an
# AppImage by hand.
#

CANDIDATES = (
    ".local/bin/savecloud",
    "Applications/SaveCloud-x86_64.AppImage",
    "Downloads/SaveCloud-x86_64.AppImage",
    "SaveCloud-x86_64.AppImage",
)

#
# Environment the command needs to reach the network, carried across
# from whatever Decky was started with. Certificate trust and proxies
# are configured here and nowhere else, so a fixed environment that
# omitted them would leave the plugin unable to reach a cloud provider
# on a network where the command line works.
#
# urllib reads the lower-case proxy names too, and something has
# usually set only one spelling.
#

PASSED_THROUGH = (
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
)


def _user() -> pwd.struct_passwd:
    """
    The desktop user, not root.

    Decky reports whose session it is running inside; falling back to
    `deck` is right on SteamOS and wrong nowhere that matters, since a
    machine without that account will have told Decky its real one.
    """

    name = getattr(decky, "USER", None) or "deck"

    try:
        return pwd.getpwnam(name)

    except KeyError:
        return pwd.getpwuid(os.getuid())


def _home() -> Path:
    """
    The desktop user's home directory.
    """

    reported = getattr(decky, "HOME", None)

    return Path(reported) if reported else Path(_user().pw_dir)


def locate() -> Path | None:
    """
    Find the `savecloud` command.

    Returns None when SaveCloud is not installed for this user, which
    is a thing the interface has to be able to say rather than crash
    over.
    """

    home = _home()

    for relative in CANDIDATES:

        candidate = home / relative

        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    return None


class Plugin:
    """
    What Gaming Mode is allowed to ask SaveCloud.
    """

    async def _main(self) -> None:

        decky.logger.info("SaveCloud plugin started")

    async def _unload(self) -> None:

        decky.logger.info("SaveCloud plugin stopped")

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    async def installed(self) -> dict:
        """
        Whether SaveCloud can be found, and which build it is.
        """

        command = locate()

        if command is None:
            return {
                "ok": False,
                "error": (
                    "SaveCloud is not installed for this user. Install it "
                    "in Desktop Mode, then run `savecloud install`."
                ),
            }

        version = await self._run("--version", raw=True)

        printed = (version.get("output") or "").splitlines()

        return {
            "ok": True,
            "path": str(command),
            "version": printed[0] if printed else "",
        }

    async def games(self) -> dict:
        """
        Every registered game and its state.
        """

        return await self._run("--json", "list")

    async def detail(self, game_id: str) -> dict:
        """
        One game in full.
        """

        return await self._run("--json", "info", game_id)

    async def check(self, game_id: str) -> dict:
        """
        What synchronizing would do, without doing it.
        """

        return await self._run("--json", "sync", game_id, "--check")

    async def check_all(self) -> dict:
        """
        What synchronizing would do for every game.

        One command rather than one per game: the interface opens with
        every game's state visible, and a round trip each would make
        that noticeably slow on a library of any size.
        """

        return await self._run("--json", "sync", "--check")

    async def logs(self, lines: int = 40) -> dict:
        """
        Recent log entries, for when something went wrong in a session.
        """

        return await self._run("--json", "logs", "--lines", str(lines))

    # ------------------------------------------------------------------
    # Acting
    # ------------------------------------------------------------------

    async def sync(self, game_id: str) -> dict:
        """
        Synchronize one game.
        """

        return await self._run("--json", "sync", game_id)

    async def sync_all(self) -> dict:
        """
        Synchronize every game this device takes part in.
        """

        return await self._run("--json", "sync")

    async def resolve(self, game_id: str, keep: str) -> dict:
        """
        Resolve a conflict.

        Parameters
        ----------
        game_id
            Game to resolve.
        keep
            "local" or "remote".
        """

        if keep not in ("local", "remote"):
            return {"ok": False, "error": f'Cannot keep "{keep}".'}

        return await self._run(
            "--json",
            "sync",
            game_id,
            f"--keep-{keep}",
        )

    # ------------------------------------------------------------------
    # Running the command
    # ------------------------------------------------------------------

    async def _run(self, *arguments: str, raw: bool = False) -> dict:
        """
        Run `savecloud` as the desktop user and read its answer.

        Never raises. Gaming Mode has nowhere to show a traceback, so
        every failure comes back as a document the interface can
        render.
        """

        #
        # Every call, before anything can go wrong with it. Diagnosing
        # a blank panel once meant guessing whether calls were arriving
        # at all: the backend logged that it started and then nothing,
        # which looks identical whether it is idle or unreachable.
        #

        decky.logger.info("running: %s", " ".join(arguments))

        command = locate()

        if command is None:
            decky.logger.warning("savecloud was not found for this user")

            return {
                "ok": False,
                "error": "SaveCloud is not installed for this user.",
            }

        account = _user()

        home = _home()

        environment = {
            "HOME": str(home),
            "PATH": f"{home}/.local/bin:/usr/bin:/bin",
            "USER": account.pw_name,
            "LOGNAME": account.pw_name,
            #
            # Qt would otherwise try to reach a display that does not
            # exist for this process, and the CLI does not need one.
            #
            "QT_QPA_PLATFORM": "offscreen",
        }

        #
        # A built environment is deliberate - inheriting root's would
        # send the command looking in the wrong places. But the network
        # is configured through the environment and nowhere else, so
        # dropping these makes a plugin that cannot reach a cloud
        # provider on a network the terminal handles fine.
        #
        # It matters on any network that inspects TLS, where the
        # intercepting authority is trusted through SSL_CERT_FILE
        # rather than being in the default store. University and
        # workplace networks commonly do this.
        #

        for name in PASSED_THROUGH:

            value = os.environ.get(name)

            if value:
                environment[name] = value

        def become_user() -> None:
            """
            Drop to the desktop user before exec.

            Without this the command runs as root and leaves
            root-owned files in the user's library, which is a way of
            breaking an installation rather than reading it.
            """

            os.setgid(account.pw_gid)

            os.setuid(account.pw_uid)

        try:
            process = await asyncio.create_subprocess_exec(
                str(command),
                *arguments,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=environment,
                cwd=str(home),
                preexec_fn=become_user if os.getuid() == 0 else None,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=TIMEOUT_SECONDS,
            )

        except asyncio.TimeoutError:
            return {
                "ok": False,
                "error": (
                    f"SaveCloud did not finish within "
                    f"{TIMEOUT_SECONDS} seconds."
                ),
            }

        except Exception as error:
            decky.logger.exception("savecloud could not be run")

            return {"ok": False, "error": str(error)}

        output = stdout.decode("utf-8", "replace").strip()

        if raw:
            return {"ok": process.returncode == 0, "output": output}

        if not output:
            return {
                "ok": False,
                "error": (
                    stderr.decode("utf-8", "replace").strip()
                    or f"SaveCloud exited with {process.returncode}."
                ),
            }

        try:
            document = json.loads(output)

        except json.JSONDecodeError:
            #
            # A command that printed prose rather than a document. Its
            # own words are more useful than a parse error.
            #

            return {"ok": False, "error": output.splitlines()[-1]}

        #
        # The exit code is the authority on success; the document
        # carries the explanation.
        #

        document.setdefault("ok", process.returncode == 0)

        return document
