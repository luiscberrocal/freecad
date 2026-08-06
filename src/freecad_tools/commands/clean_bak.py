"""Delete FreeCAD ``*.FCBak`` backup files from a project tree."""

from __future__ import annotations

from pathlib import Path

import click

BACKUP_PATTERN = "*.FCBak"


def find_backups(root: Path) -> list[Path]:
    """Return every ``*.FCBak`` file under ``root``, sorted by path."""
    return sorted(p for p in root.rglob(BACKUP_PATTERN) if p.is_file())


def human_size(num_bytes: int) -> str:
    """Format a byte count using the largest unit that keeps it under 1024."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


@click.command("clean-bak")
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="List the files that would be deleted without removing anything.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Delete without asking for confirmation.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Print each file as it is deleted.",
)
def clean_bak(path: Path, dry_run: bool, yes: bool, verbose: bool) -> None:
    """Delete every *.FCBak backup file found under PATH (default: current directory)."""
    root = path.resolve()
    backups = find_backups(root)

    if not backups:
        click.echo(f"No {BACKUP_PATTERN} files found under {root}.")
        return

    total_bytes = sum(p.stat().st_size for p in backups)
    click.echo(f"Found {len(backups)} {BACKUP_PATTERN} files ({human_size(total_bytes)}):")
    for backup in backups:
        click.echo(f"  {backup.relative_to(root)}")

    if dry_run:
        click.echo("Dry run: nothing was deleted.")
        return

    if not yes and not click.confirm(f"Delete {len(backups)} files?"):
        click.echo("Aborted: nothing was deleted.")
        return

    deleted = 0
    freed = 0
    for backup in backups:
        size = backup.stat().st_size
        try:
            backup.unlink()
        except OSError as exc:
            click.echo(f"Could not delete {backup}: {exc}", err=True)
            continue
        deleted += 1
        freed += size
        if verbose:
            click.echo(f"Deleted {backup.relative_to(root)}")

    click.echo(f"Deleted {deleted} files ({human_size(freed)}).")
