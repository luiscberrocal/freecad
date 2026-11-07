# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A personal library of FreeCAD models, mostly for 3D printing, plus a small CLI for housekeeping. Most of the repo is binary assets (`.FCStd` sources, `.3mf` print exports). There are two separate Python environments, and they do not share dependencies:

- **`src/freecad_tools/`**: a click CLI, run through `uv` (Python 3.12+). It does not import FreeCAD.
- **Model build scripts** such as `models/bim/three-bedroom-house/build_house.py`: run by FreeCAD's bundled interpreter, not by `uv` or `.venv`. `FreeCAD`, `Arch`, `Draft`, `Part`, `ifcopenshell` and `matplotlib` all come from the FreeCAD app (currently 1.1.1).

## Commands

`just` recipes work from anywhere in the repo:

```sh
just new                                # scaffold a model folder (prompts for category and name)
just new --category other --name "Foo"  # same, without prompts
just clean-dry                          # list *.FCBak files that would be deleted
just clean                              # delete them (asks first; `just clean --yes` skips the prompt)
```

Rebuild a scripted model from the repo root with FreeCAD's interpreter. Keep the `< /dev/null`:

```sh
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
    models/bim/three-bedroom-house/build_house.py < /dev/null
```

A successful run prints `OBJECTS <n> ERRORS []` and then `DONE`. A non-empty `ERRORS` list names objects that failed to recompute. The script does not stop on errors: it still overwrites every output and exits normally, so read that line rather than relying on the exit code.

There are no tests and no lint or format configuration in this repo.

## Repository layout

- `models/<category>/<slug>/`: one folder per model. Create these with `just new`, which writes the kebab-case slug and the README. Categories are simply the folders under `models/`, and the misspelled `mulitboard` is the real folder name.
- `external/`: third-party material (a keychain project and its font pack), not the user's own models.
- Each model `README.md` starts with YAML frontmatter (title, slug, category, version, status, `freecad.source`, `freecad.parametric`, `freecad.freecad_version`). The template lives in `render_readme` in `src/freecad_tools/commands/new_model.py`. It defaults to `freecad_version: "1.0"` and `parametric: false`, so update those for a scripted model. Some older models have no README, an empty one, or one without frontmatter.
- CLI commands live one per module in `src/freecad_tools/commands/` and are registered in `cli.py`.

## Scripted BIM models

`build_house.py` is the source of truth for the three-bedroom house. The `.FCStd`, `.ifc`, plan `.pdf` and schedule `.csv` next to it are all generated and overwritten on each run, so hand edits to the `.FCStd` are lost. Commit the regenerated files together with the script change. Running the script rewrites them, so check `git status` first if they hold uncommitted work.

The script is driven by constants and dicts at the top (`WALLS`, `ROOMS`, `WINDOWS`, `DOORS`, `MATERIALS`, plus the shower and toilet sizes used by `fixture_specs`). `build()` turns them into Arch objects and the writers consume the result. Units are millimetres, X is east, Y is north, and Z = 0 is the finished floor.

Things that are easy to break:

- **Entry point**: `main()` is called at module level on purpose. Under `freecadcmd`, `__name__` is the script's module name, not `"__main__"`, so an `if __name__ == "__main__"` guard would never run. Importing the file also runs the whole build.
- **Walls must be axis-aligned**: `is_along_x`, `opening_placement`, `draw_window` and `draw_door` all assume this.
- **Opening positions are absolute**: the `centre` value in `WINDOWS` and `DOORS` is a global X or Y coordinate, not an offset from the wall's start.
- **New rooms** need an entry in `PLAN_ROOM_NAMES` as well as `ROOMS`, or `write_plan` raises `KeyError`. A room that gives up floor to a closet also needs an entry in `ROOM_CUTOUTS`, or the two spaces overlap.
- **Sliding doors**: a `DOORS` hinge end of 0 means a sliding door, which uses the window preset with solid panels. Its swing side is the closet side.
- **Language**: the plan PDF is in Spanish (room names and title block). Model labels, the IFC and the schedule are in English.
- **The plan is not fully model-driven**: wall cuts and room areas come from the real solids. The roof outline and dimension lines are drawn from the constants, so they follow a changed value, but new walls get no dimensions unless added to `write_plan`. The sheet origin, north arrow and title block position are literal numbers there, so a larger footprint can run into them.
- **Opening names carry meaning**: the first word of a `WINDOWS` or `DOORS` key (`W02`) is a type tag printed on the plan, shared by every opening of the same kind, size and sill (`W02 Bedroom 2`, `W02 Dining`). The table on the plan lists one row per tag with a count. `opening_types` raises if a tag covers two different sizes or one size has two tags, so pick the existing tag when adding a matching opening. Full names must stay unique because `write_ifc` and `schedule_rows` look openings up by name.
- **`write_ifc` patches FreeCAD's exporter output**: it adds the missing `IfcRelFillsElement` links, matching each door or window to its opening by name, converts `OverallWidth` and `OverallHeight` from millimetres to metres, and sets the operation type of sliding doors. Keep these repairs when changing the export.
