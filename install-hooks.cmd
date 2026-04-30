@echo off
REM Activate the versioned Git hooks in .githooks for this clone.
REM Run this once after cloning the repository.
git config core.hooksPath .githooks
if errorlevel 1 (
    echo Failed to configure core.hooksPath.
    exit /b 1
)
echo Git hooks activated: core.hooksPath -^> .githooks
