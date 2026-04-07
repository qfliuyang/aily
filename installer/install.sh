#!/bin/bash
#
# Aily macOS Installer
# Installs Aily app and sets up launch agent
#

set -e

APP_NAME="Aily"
APP_BUNDLE="Aily.app"
LAUNCH_AGENT_PLIST="com.aily.app.plist"
INSTALL_DIR="/Applications"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
AILY_DATA_DIR="$HOME/.aily"

echo "=========================================="
echo "Aily Installer"
echo "=========================================="
echo ""

# Check if running from DMG or local directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -d "$SCRIPT_DIR/$APP_BUNDLE" ]]; then
    SOURCE_DIR="$SCRIPT_DIR"
elif [[ -d "$SCRIPT_DIR/../$APP_BUNDLE" ]]; then
    SOURCE_DIR="$(dirname "$SCRIPT_DIR")"
else
    echo "Error: Cannot find $APP_BUNDLE"
    exit 1
fi

echo "Source: $SOURCE_DIR"
echo "Install target: $INSTALL_DIR"
echo ""

# Create data directory
mkdir -p "$AILY_DATA_DIR"

# Copy app bundle
echo "Installing Aily.app..."
if [[ -d "$INSTALL_DIR/$APP_BUNDLE" ]]; then
    echo "Removing previous installation..."
    rm -rf "$INSTALL_DIR/$APP_BUNDLE"
fi

cp -R "$SOURCE_DIR/$APP_BUNDLE" "$INSTALL_DIR/"
echo "✓ Aily.app installed to $INSTALL_DIR"
echo ""

# Install launch agent
echo "Setting up launch agent..."
mkdir -p "$LAUNCH_AGENTS_DIR"

# Update plist with actual user home directory
sed "s|/Users/luzi|$HOME|g" "$SOURCE_DIR/$LAUNCH_AGENT_PLIST" > "$LAUNCH_AGENTS_DIR/$LAUNCH_AGENT_PLIST"

# Load launch agent
launchctl unload "$LAUNCH_AGENTS_DIR/$LAUNCH_AGENT_PLIST" 2>/dev/null || true
launchctl load "$LAUNCH_AGENTS_DIR/$LAUNCH_AGENT_PLIST"
echo "✓ Launch agent installed and started"
echo ""

# Create .env template if doesn't exist
ENV_FILE="$INSTALL_DIR/$APP_BUNDLE/Contents/Resources/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "Creating configuration template..."
    cat > "$ENV_FILE" << 'EOF'
# Aily Configuration
# Fill in your API keys or use: security add-generic-password -s aily -a feishu_app_id -w YOUR_KEY

# Feishu Bot
feishu_app_id=
feishu_app_secret=
feishu_verification_token=
feishu_encrypt_key=

# Obsidian
obsidian_rest_api_key=
obsidian_vault_path=
obsidian_rest_api_port=27123

# OpenAI / LLM
llm_api_key=
llm_base_url=https://api.openai.com/v1
llm_model=gpt-4o-mini

# Features
aily_digest_enabled=true
aily_digest_hour=9
aily_digest_minute=0
feishu_voice_enabled=false
EOF
    echo "✓ Configuration template created at $ENV_FILE"
    echo ""
fi

echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Aily has been installed to: $INSTALL_DIR/$APP_BUNDLE"
echo ""
echo "Next steps:"
echo "1. Edit configuration: $ENV_FILE"
echo "2. Or use Keychain to store credentials:"
echo "   security add-generic-password -s aily -a feishu_app_id -w YOUR_APP_ID"
echo ""
echo "Aily will start automatically on login."
echo "To start now: open '$INSTALL_DIR/$APP_BUNDLE'"
echo ""
echo "Logs: $AILY_DATA_DIR/aily.log"
echo ""

# Open the app if requested
if [[ "$1" == "--launch" ]]; then
    echo "Starting Aily..."
    open "$INSTALL_DIR/$APP_BUNDLE"
fi
