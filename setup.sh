#!/bin/bash
# Friday Sermon Email Setup Script
# This script helps you configure and install the Friday sermon email automation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.mj.friday-sermon-email.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "========================================"
echo "Friday Sermon Email - Setup Script"
echo "========================================"
echo ""

# Check if .env file exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "Creating .env file from template..."
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env with your credentials:"
    echo "   1. GEMINI_API_KEY - Get from https://aistudio.google.com/apikey"
    echo "   2. SMTP_EMAIL - Your email address"
    echo "   3. SMTP_PASSWORD - App password (for Gmail: https://myaccount.google.com/apppasswords)"
    echo ""
    echo "Run: nano $SCRIPT_DIR/.env"
    echo ""
    read -p "Press Enter after you've configured .env, or Ctrl+C to exit..."
fi

# Test the script
echo ""
echo "Would you like to run a test to verify the setup? (y/n)"
read -r test_choice
if [[ "$test_choice" == "y" || "$test_choice" == "Y" ]]; then
    echo ""
    echo "Running test..."
    python3 "$SCRIPT_DIR/friday_sermon_email.py"
    echo ""
fi

# Install launchd job
echo ""
echo "Would you like to install the weekly scheduler? (y/n)"
echo "This will run the script every Friday at 6:00 AM PST (5:00 PM Makkah time)"
read -r install_choice

if [[ "$install_choice" == "y" || "$install_choice" == "Y" ]]; then
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p "$LAUNCH_AGENTS_DIR"
    
    # Unload existing job if present
    if launchctl list 2>/dev/null | grep -q "com.mj.friday-sermon-email"; then
        echo "Unloading existing job..."
        launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
    fi
    
    # Copy plist file
    echo "Installing launch agent..."
    cp "$SCRIPT_DIR/$PLIST_NAME" "$LAUNCH_AGENTS_DIR/"
    
    # Load the job
    echo "Loading launch agent..."
    launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME"
    
    echo ""
    echo "✓ Scheduler installed successfully!"
    echo ""
    echo "The script will run every Friday at 6:00 AM PST (5:00 PM Makkah time)"
    echo ""
    echo "Useful commands:"
    echo "  - Check status: launchctl list | grep friday-sermon"
    echo "  - View logs: tail -f ~/Library/Logs/friday-sermon-email.log"
    echo "  - Uninstall: launchctl unload ~/Library/LaunchAgents/$PLIST_NAME"
else
    echo ""
    echo "Skipping scheduler installation."
    echo ""
    echo "To install later, run:"
    echo "  cp $SCRIPT_DIR/$PLIST_NAME ~/Library/LaunchAgents/"
    echo "  launchctl load ~/Library/LaunchAgents/$PLIST_NAME"
fi

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
