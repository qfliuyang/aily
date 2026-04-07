#!/bin/bash
#
# Aily Uninstaller
# Removes Aily app and launch agent
#

set -e

APP_NAME="Aily"
APP_BUNDLE="Aily.app"
LAUNCH_AGENT_PLIST="com.aily.app.plist"
INSTALL_DIR="/Applications"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
AILY_DATA_DIR="$HOME/.aily"

echo "=========================================="
echo "Aily Uninstaller"
echo "=========================================="
echo ""

# Confirm
read -p "Are you sure you want to uninstall Aily? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

# Stop and unload launch agent
echo "Stopping Aily service..."
if [[ -f "$LAUNCH_AGENTS_DIR/$LAUNCH_AGENT_PLIST" ]]; then
    launchctl unload "$LAUNCH_AGENTS_DIR/$LAUNCH_AGENT_PLIST" 2>/dev/null || true
    rm "$LAUNCH_AGENTS_DIR/$LAUNCH_AGENT_PLIST"
    echo "✓ Launch agent removed"
fi

# Kill running processes
pkill -f "aily.main" 2>/dev/null || true

# Remove app bundle
echo "Removing Aily.app..."
if [[ -d "$INSTALL_DIR/$APP_BUNDLE" ]]; then
    rm -rf "$INSTALL_DIR/$APP_BUNDLE"
    echo "✓ Aily.app removed"
fi

# Ask about data directory
read -p "Remove Aily data directory ($AILY_DATA_DIR)? This includes your queue and graph databases. (y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$AILY_DATA_DIR"
    echo "✓ Data directory removed"
fi

echo ""
echo "=========================================="
echo "Aily has been uninstalled."
echo "=========================================="
