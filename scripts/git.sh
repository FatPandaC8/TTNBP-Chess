#!/bin/bash

# Get branch - or can use $(git symbolic-ref --short HEAD)
current_branch=$(git branch --show-current)

# No command line -> raise error, no auto commit
if [ $# -eq 0 ]; then
    echo "[ERROR]: No commit message or files provided. Please specify files and commit 
message."
    exit 1
fi

# Get commit message as last args
commit_msg="${@: -1}"

# Get all files
files=("${@:1:$#-1}")

# Array contains all files to add
files_add=()
for f in "${files[@]}"; do
    if [ -e "$f" ]; then
        files_add+=("$f")
    else
        echo "[INFO]: File or directory '$f' not exist, skip to add."
    fi
done

# If no files -> git add .
if [ ${#files_add[@]} -eq 0 ]; then
    echo "[INFO]: No valid files specified, running 'git add .'"
    git add .
else
    git add "${files_add[@]}"
fi

# Array of files staged
staged_files=$(git diff --cached --name-only)

if [ -z "$staged_files" ]; then
    echo "[ERROR]: No files staged for commit. Aborting."
    exit 1
fi

# Info
echo "[INFO]: You are in BRANCH: $current_branch"
echo "[INFO]: Files staged for commit:"
echo "$staged_files"
echo "[INFO]: COMMIT message: $commit_msg"

# Commit and save HEAD status before
prev_head=$(git rev-parse HEAD)

if git commit -m "$commit_msg"; then
    echo "[INFO]: Commit successful."
else
    echo "[ERROR]: Commit failed. Possibly no changes to commit."
    exit 1
fi

# User options
read -rp "[INFO]: Do you want to push to origin/$current_branch? (y/n): " answer
case "$answer" in
    y|Y|yes|YES)
        echo "[INFO]: Pushing to origin/$current_branch..."
        if git push origin "$current_branch"; then
            echo "[INFO]: Push successful."
            exit 0
        else
            echo "[ERROR]: Push failed."
            exit 1
        fi
        ;;
    *)
        echo "[INFO]: Push cancelled by user. Rolling back commit and staged files..."

        # Reset commit
        git reset --soft "$prev_head"

        # Unstage file_add
        git reset

        echo "[INFO]: Rollback completed. No changes committed or staged."
        exit 0
        ;;
esac
