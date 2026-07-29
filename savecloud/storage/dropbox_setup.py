"""
Interactive Dropbox authorization.

Kept beside the backend rather than in the command layer. The `config
provider` command calls `backend.setup()` without knowing which
provider it is talking to, exactly as `doctor` calls
`provider_warnings()` - so adding a provider never means editing a
command.
"""

from __future__ import annotations

import urllib.parse

import typer

from savecloud.services.credentials import CredentialService
from savecloud.utils import http

PROVIDER = "dropbox"

TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
AUTHORIZE_URL = "https://www.dropbox.com/oauth2/authorize"

APP_CONSOLE = "https://www.dropbox.com/developers/apps"


def authorize_url(app_key: str) -> str:
    """
    Build the URL that grants SaveCloud access.

    `token_access_type=offline` is what makes Dropbox return a refresh
    token. Without it the authorization yields a token that expires in
    a few hours and synchronization stops working the same day.
    """

    query = urllib.parse.urlencode(
        {
            "client_id": app_key,
            "response_type": "code",
            "token_access_type": "offline",
        }
    )

    return f"{AUTHORIZE_URL}?{query}"


def exchange_code(
    app_key: str,
    app_secret: str,
    code: str,
) -> dict:
    """
    Exchange an authorization code for a refresh token.
    """

    return http.post_form(
        TOKEN_URL,
        {
            "code": code,
            "grant_type": "authorization_code",
            "client_id": app_key,
            "client_secret": app_secret,
        },
    )


def run_setup() -> None:
    """
    Walk the user through authorizing SaveCloud with Dropbox.
    """

    from savecloud.utils.prompt import prompt_required

    typer.echo()
    typer.echo("Dropbox setup")
    typer.echo("-------------")
    typer.echo()
    typer.echo("SaveCloud needs its own Dropbox app. This is free, takes")
    typer.echo("a couple of minutes, and only has to be done once per")
    typer.echo("Dropbox account.")
    typer.echo()
    typer.echo(f"  1. Open {APP_CONSOLE}")
    typer.echo("  2. Create app → Scoped access → App folder")
    typer.echo("     (App folder keeps SaveCloud out of the rest of your")
    typer.echo("      Dropbox; it can only see its own folder.)")
    typer.echo("  3. Name it anything, e.g. savecloud-<your-name>")
    typer.echo("  4. On the Permissions tab, tick:")
    typer.echo("       files.metadata.read")
    typer.echo("       files.metadata.write")
    typer.echo("       files.content.read")
    typer.echo("       files.content.write")
    typer.echo("     then Submit. Do this BEFORE authorizing, or the")
    typer.echo("     token will lack the permissions and uploads fail.")
    typer.echo("  5. On the Settings tab, copy the App key and App secret.")
    typer.echo()

    app_key = prompt_required("App key")
    app_secret = prompt_required("App secret")

    typer.echo()
    typer.echo("Now open this URL and click Allow:")
    typer.echo()
    typer.echo(f"    {authorize_url(app_key)}")
    typer.echo()
    typer.echo("Dropbox will show you an authorization code.")
    typer.echo()

    code = prompt_required("Authorization code")

    try:
        response = exchange_code(app_key, app_secret, code.strip())

    except http.HttpError as error:

        typer.secho(
            "✗ Dropbox rejected the authorization.",
            fg=typer.colors.RED,
        )

        typer.echo()

        if "invalid_grant" in error.body:
            typer.echo(
                "That code was already used or has expired. Codes are "
                "single-use and short-lived - open the URL again for a "
                "fresh one."
            )

        elif error.is_auth_failure:
            typer.echo("The app key or app secret does not match.")

        else:
            typer.echo(str(error))

        raise typer.Exit(code=1)

    refresh_token = response.get("refresh_token")

    if not refresh_token:
        typer.secho(
            "✗ Dropbox returned no refresh token.",
            fg=typer.colors.RED,
        )

        typer.echo()
        typer.echo(
            "This happens when the authorization URL omits "
            "token_access_type=offline. Re-run setup and use the URL "
            "exactly as printed."
        )

        raise typer.Exit(code=1)

    CredentialService.save(
        PROVIDER,
        {
            "app_key": app_key,
            "app_secret": app_secret,
            "refresh_token": refresh_token,
        },
    )

    typer.echo()
    typer.secho(
        "✓ Dropbox authorized.",
        fg=typer.colors.GREEN,
    )

    typer.echo(f"  Credentials saved to {CredentialService.path(PROVIDER)}")
    typer.echo("  This file is never synchronized between devices.")

    #
    # Confirm the credentials actually work, rather than reporting
    # success and failing at the first sync.
    #

    from savecloud.storage.dropbox import DropboxStorageBackend

    DropboxStorageBackend.reset()

    try:
        email = DropboxStorageBackend.client().account_email()

    except Exception:
        email = None

    if email:
        typer.echo(f"  Connected as {email}")

    typer.echo()
    typer.echo("Activate it with:")
    typer.echo()
    typer.echo("    savecloud config backend dropbox")
    typer.echo()
    typer.echo("Each device needs its own setup, since credentials stay local.")
