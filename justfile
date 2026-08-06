# List the available tasks.
default:
    @just --list

# Delete every *.FCBak backup file in the repo (asks for confirmation).
clean *ARGS:
    uv run freecad-tools clean-bak {{justfile_directory()}} {{ARGS}}

# List the *.FCBak files that clean-bak would delete.
clean-dry:
    @just clean --dry-run
