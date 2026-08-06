# List the available tasks.
default:
    @just --list

# Scaffold a new model folder with a README (prompts for category and name).
new *ARGS:
    uv run freecad-tools new-model --models-dir {{justfile_directory()}}/models {{ARGS}}

# Delete every *.FCBak backup file in the repo (asks for confirmation).
clean *ARGS:
    uv run freecad-tools clean-bak {{justfile_directory()}} {{ARGS}}

# List the *.FCBak files that clean-bak would delete.
clean-dry:
    @just clean --dry-run
