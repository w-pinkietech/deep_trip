#!/bin/bash
set -e

# Base directory of the repo
REPO_ROOT=$(cd "$(dirname "$0")"; pwd)
TEN_FRAMEWORK_DIR="$REPO_ROOT/ten-framework"
EXTENSION_DIR="$REPO_ROOT/deep_trip"
TARGET_DIR="$TEN_FRAMEWORK_DIR/ai_agents/agents/ten_packages/extension"
SYMLINK_PATH="$TARGET_DIR/deep_trip"

echo "Setting up Deep Trip extension in TEN Framework..."

if [ ! -d "$TEN_FRAMEWORK_DIR" ]; then
    echo "Error: ten-framework directory not found at $TEN_FRAMEWORK_DIR"
    exit 1
fi

if [ ! -d "$EXTENSION_DIR" ]; then
    echo "Error: deep_trip extension directory not found at $EXTENSION_DIR"
    exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "Creating target directory: $TARGET_DIR"
    mkdir -p "$TARGET_DIR"
fi

if [ -L "$SYMLINK_PATH" ]; then
    echo "Symlink already exists at $SYMLINK_PATH"
    # Verify where it points
    CURRENT_TARGET=$(readlink "$SYMLINK_PATH")
    echo "Points to: $CURRENT_TARGET"
elif [ -e "$SYMLINK_PATH" ]; then
    echo "Error: File or directory exists at $SYMLINK_PATH but is not a symlink."
    exit 1
else
    echo "Creating symlink..."
    # Calculate relative path
    # deep_trip is at root
    # ten-framework/ai_agents/agents/ten_packages/extension/deep_trip
    # relative path: ../../../../../deep_trip
    ln -s "../../../../../deep_trip" "$SYMLINK_PATH"
    echo "Symlink created at $SYMLINK_PATH"
fi

echo "Deep Trip extension setup complete."
