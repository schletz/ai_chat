#!/bin/sh
# Activate the versioned Git hooks in .githooks for this clone.
# Run this once after cloning the repository.
git config core.hooksPath .githooks || {
    echo "Failed to configure core.hooksPath." >&2
    exit 1
}
echo "Git hooks activated: core.hooksPath -> .githooks"
