#!/bin/bash
#
# Build Aily macOS DMG Installer
# Creates a signed DMG with the app bundle and installer scripts
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build"
DMG_NAME="Aily-0.5.0-macOS.dmg"
VOLUME_NAME="Aily Installer"

echo "=========================================="
echo "Aily DMG Builder"
echo "=========================================="
echo ""

# Check dependencies
echo "Checking dependencies..."
if ! command -v create-dmg &> /dev/null; then
    echo "Warning: create-dmg not found. Installing..."
    brew install create-dmg || {
        echo "Please install create-dmg: brew install create-dmg"
        exit 1
    }
fi
echo "✓ Dependencies OK"
echo ""

# Create build directory
mkdir -p "$BUILD_DIR"
rm -rf "$BUILD_DIR/dmg-contents"
mkdir -p "$BUILD_DIR/dmg-contents"

# Build Python environment if needed
echo "Setting up Python environment..."
cd "$PROJECT_ROOT"

if [[ ! -d ".venv" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Install/update dependencies
.venv/bin/pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Copy files to build directory
echo "Preparing app bundle..."
cp -R "$SCRIPT_DIR/Aily.app" "$BUILD_DIR/dmg-contents/"

# Copy source code into app bundle Resources
mkdir -p "$BUILD_DIR/dmg-contents/Aily.app/Contents/Resources/aily"
cp -R "$PROJECT_ROOT/aily" "$BUILD_DIR/dmg-contents/Aily.app/Contents/Resources/"
cp "$PROJECT_ROOT/requirements.txt" "$BUILD_DIR/dmg-contents/Aily.app/Contents/Resources/"

# Copy Python virtual environment
mkdir -p "$BUILD_DIR/dmg-contents/Aily.app/Contents/Resources/.venv"
cp -R .venv/lib .venv/bin "$BUILD_DIR/dmg-contents/Aily.app/Contents/Resources/.venv/"

echo "✓ App bundle prepared"
echo ""

# Copy installer scripts
cp "$SCRIPT_DIR/install.sh" "$BUILD_DIR/dmg-contents/"
cp "$SCRIPT_DIR/uninstall.sh" "$BUILD_DIR/dmg-contents/"
cp "$SCRIPT_DIR/com.ily.app.plist" "$BUILD_DIR/dmg-contents/"

# Create README
cat > "$BUILD_DIR/dmg-contents/README.txt" << 'EOF'
Aily - Personal Knowledge Assistant
=====================================

Aily captures your knowledge from Feishu, Monica, and Claude Code into Obsidian.

Installation:
1. Drag Aily.app to Applications
2. Or run ./install.sh for full setup with launch agent

Configuration:
- Edit /Applications/Aily.app/Contents/Resources/.env
- Or use macOS Keychain: security add-generic-password -s aily -a feishu_app_id -w YOUR_KEY

Uninstallation:
- Run ./uninstall.sh

More info: https://github.com/yourusername/aily
EOF

echo "Creating DMG..."
cd "$BUILD_DIR"

# Remove old DMG
rm -f "$DMG_NAME"

# Build DMG
create-dmg \
    --volname "$VOLUME_NAME" \
    --volicon "$SCRIPT_DIR/Aily.app/Contents/Resources/Aily.icns" 2>/dev/null || true \
    --window-pos 200 120 \
    --window-size 800 400 \
    --icon-size 100 \
    --app-drop-link 600 185 \
    --icon "Aily.app" 200 185 \
    --icon "README.txt" 400 185 \
    "$DMG_NAME" \
    "dmg-contents/"

echo ""
echo "=========================================="
echo "DMG Build Complete!"
echo "=========================================="
echo ""
echo "Output: $BUILD_DIR/$DMG_NAME"
echo ""
echo "To sign the DMG:"
echo "  codesign --sign 'Developer ID Application' '$BUILD_DIR/$DMG_NAME'"
echo ""
echo "To notarize (required for macOS 10.15+):"
echo "  xcrun altool --notarize-app --primary-bundle-id 'com.aily.app' \"
echo "    --username 'your@email.com' --password '@keychain:AC_PASSWORD' \"
echo "    --file '$BUILD_DIR/$DMG_NAME'"
echo ""
