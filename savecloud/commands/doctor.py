"""
Check an installation for problems.
"""

from __future__ import annotations

import typer

from savecloud.models.diagnostic import Finding, Severity
from savecloud.services.diagnostics import DiagnosticsService

MARKERS = {
    Severity.OK: ("✓", typer.colors.GREEN),
    Severity.WARNING: ("!", typer.colors.YELLOW),
    Severity.ERROR: ("✗", typer.colors.RED),
}


def render(finding: Finding) -> None:
    """
    Print one finding.
    """

    marker, colour = MARKERS[finding.severity]

    typer.secho(
        f"{marker} {finding.title}",
        fg=colour,
        bold=finding.severity is not Severity.OK,
    )

    if finding.detail:
        for line in finding.detail.split("\n"):
            typer.echo(f"    {line}")

    if finding.remedy and finding.severity is not Severity.OK:
        typer.echo()

        for line in finding.remedy.split("\n"):
            typer.echo(f"    → {line}")

    typer.echo()


def doctor(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show checks that passed, not only problems.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit non-zero on warnings as well as errors.",
    ),
) -> None:
    """
    Check this installation for problems.
    """

    findings = DiagnosticsService.run()

    errors = [f for f in findings if f.severity is Severity.ERROR]
    warnings = [f for f in findings if f.severity is Severity.WARNING]

    typer.echo()
    typer.echo("SaveCloud Doctor")
    typer.echo("----------------")
    typer.echo()

    shown = findings if verbose else [f for f in findings if f.is_problem]

    if not shown:
        typer.secho(
            "✓ No problems found.",
            fg=typer.colors.GREEN,
        )

        typer.echo()
        typer.echo("Run with --verbose to see everything that was checked.")

        return

    for finding in shown:
        render(finding)

    #
    # Summary
    #

    typer.echo("----------------")

    if errors:
        typer.secho(
            f"{len(errors)} error(s), {len(warnings)} warning(s).",
            fg=typer.colors.RED,
        )

    elif warnings:
        typer.secho(
            f"{len(warnings)} warning(s). Nothing is broken.",
            fg=typer.colors.YELLOW,
        )

    else:
        typer.secho(
            "No problems found.",
            fg=typer.colors.GREEN,
        )

    if errors or (strict and warnings):
        raise typer.Exit(code=1)
