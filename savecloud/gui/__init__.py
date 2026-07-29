"""
Graphical front end.

Imports SaveCloud's services directly rather than driving the CLI: it
is the same Python process, so a subprocess and a JSON round trip would
buy nothing. The `--json` interface exists for front ends that cannot
do this - the Decky Loader plugin among them.

Nothing here contains business logic. Widgets call `GuiFacade`, which
calls services, exactly as the commands do.
"""
