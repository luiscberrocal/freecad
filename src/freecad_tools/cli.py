"""Entry point for the ``freecad-tools`` command line interface."""

from __future__ import annotations

import click

from freecad_tools import __version__
from freecad_tools.commands.clean_bak import clean_bak
from freecad_tools.commands.new_model import new_model


@click.group()
@click.version_option(__version__, prog_name="freecad-tools")
def cli() -> None:
    """Utilities for working with FreeCAD project directories."""


cli.add_command(clean_bak)
cli.add_command(new_model)


if __name__ == "__main__":
    cli()
