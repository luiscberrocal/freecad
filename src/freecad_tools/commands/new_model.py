"""Scaffold a new model folder with a README under a category."""

from __future__ import annotations

import datetime as dt
import re
import subprocess
import unicodedata
from pathlib import Path

import click

NEW_CATEGORY_LABEL = "+ new category"


def kebab_case(value: str) -> str:
    """Convert an arbitrary model name into a kebab-case folder name."""
    # Fold accents to ASCII so "café" becomes "cafe" rather than "caf".
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    # Split camelCase / PascalCase runs before flattening the separators.
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", folded)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", spaced).strip("-").lower()
    return re.sub(r"-{2,}", "-", slug)


def list_categories(models_dir: Path) -> list[str]:
    """Return the category folder names under ``models_dir``, sorted."""
    return sorted(p.name for p in models_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def git_author(models_dir: Path) -> str:
    """Return the configured git user name, or an empty string when unavailable."""
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=models_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def yaml_str(value: str) -> str:
    """Quote a string so it is always a safe YAML scalar."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def prompt_category(models_dir: Path) -> str:
    """Ask which category to use, offering the existing folders plus a new one."""
    categories = list_categories(models_dir)
    choices = [*categories, NEW_CATEGORY_LABEL]

    click.echo("Category:")
    for index, name in enumerate(choices, start=1):
        click.echo(f"  {index}) {name}")

    picked = click.prompt(
        f"Choose [1-{len(choices)}]",
        type=click.IntRange(1, len(choices)),
    )
    if choices[picked - 1] != NEW_CATEGORY_LABEL:
        return choices[picked - 1]

    raw = click.prompt("New category name")
    category = kebab_case(raw)
    if not category:
        raise click.ClickException(f"{raw!r} does not produce a usable folder name.")
    return category


def render_readme(
    *,
    title: str,
    slug: str,
    category: str,
    author: str,
    today: str,
) -> str:
    """Build the README contents, frontmatter included."""
    return f"""---
title: {yaml_str(title)}
slug: {slug}
category: {category}
created: {today}
updated: {today}
version: 1
status: draft
description: ""
tags: []
author: {yaml_str(author)}
freecad:
  source: {slug}.FCStd
  parametric: false
  freecad_version: "1.0"
---

# {title}
"""


@click.command("new-model")
@click.option(
    "--models-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default="models",
    show_default=True,
    help="Directory holding the category folders.",
)
@click.option("--category", help="Category folder to use, skipping the prompt.")
@click.option("--name", help="Model name, skipping the prompt.")
def new_model(models_dir: Path, category: str | None, name: str | None) -> None:
    """Create a new model folder with a README.md under a category."""
    root = models_dir.resolve()
    if not root.is_dir():
        raise click.ClickException(f"{root} does not exist. Use --models-dir to point at it.")

    category = kebab_case(category) if category else prompt_category(root)
    if not category:
        raise click.ClickException("Category name is empty.")

    title = (name or click.prompt("Model name")).strip()
    slug = kebab_case(title)
    if not slug:
        raise click.ClickException(f"{title!r} does not produce a usable folder name.")

    target = root / category / slug
    if target.exists():
        raise click.ClickException(f"{target} already exists.")

    today = dt.date.today().isoformat()
    target.mkdir(parents=True)
    readme = target / "README.md"
    readme.write_text(
        render_readme(
            title=title,
            slug=slug,
            category=category,
            author=git_author(root),
            today=today,
        )
    )
    click.echo(f"Created {readme}")
