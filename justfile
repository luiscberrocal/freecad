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

# Google Drive folder that receives the PDFs (rclone remote "gdrive").
drive_folder := "1WMZzek2Hf-heIRtXxG153-wXcQ9t08do"

# Upload new and changed PDFs to Google Drive, keeping the repo's folder layout. Never deletes anything there.
upload-pdfs *ARGS:
    rclone copy {{justfile_directory()}} "gdrive,root_folder_id={{drive_folder}}:" \
        --filter "- .*/**" --filter "+ *.pdf" --filter "- *" \
        --progress {{ARGS}}

# List the PDFs that upload-pdfs would upload.
upload-pdfs-dry:
    @just upload-pdfs --dry-run
