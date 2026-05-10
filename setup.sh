#!/bin/bash
# Friday Sermon Email — interactive setup
# Creates a Python venv, installs deps, copies .env, and installs the
# launchd job that fires `--auto` hourly on Fri/Sat.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.mj.haramain-fridays.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "========================================"
echo "Haramain Fridays — Setup"
echo "========================================"
echo ""

# 1. venv + deps
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python venv at .venv..."
    python3 -m venv "$VENV_DIR"
fi
echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"
echo "  ✓ venv ready"
echo ""

# 2. .env
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo "Created .env from template."
    echo ""
    echo "⚠️  Edit .env with your credentials:"
    echo "   1. GEMINI_API_KEY  — https://aistudio.google.com/apikey"
    echo "   2. SMTP_EMAIL      — your sending address"
    echo "   3. SMTP_PASSWORD   — Gmail App Password (https://myaccount.google.com/apppasswords)"
    echo ""
    echo "Then drop your Firebase service account JSON next to this script:"
    echo "   harmainfridays-firebase-adminsdk-fbsvc-*.json"
    echo ""
    read -r -p "Press Enter once .env and the Firebase JSON are in place..." _
fi

# 3. Optional dry run
echo ""
echo "Run a single --auto tick now to verify everything's wired up? (y/n)"
read -r test_choice
if [[ "$test_choice" == "y" || "$test_choice" == "Y" ]]; then
    "$VENV_DIR/bin/python3" "$SCRIPT_DIR/friday_sermon_email.py" --auto
    echo ""
fi

# 4. launchd job
echo ""
echo "Install the hourly Fri/Sat launchd job? (y/n)"
read -r install_choice
if [[ "$install_choice" == "y" || "$install_choice" == "Y" ]]; then
    mkdir -p "$LAUNCH_AGENTS_DIR"

    # Unload current job so we can replace cleanly
    if launchctl list 2>/dev/null | grep -q "com.mj.haramain-fridays"; then
        launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
    fi
    # Also clean up obsolete labels from previous iterations of this project
    for old in com.mj.friday-sermon-email com.mj.friday-draft com.mj.friday-send; do
        if launchctl list 2>/dev/null | grep -q "$old"; then
            launchctl unload "$LAUNCH_AGENTS_DIR/${old}.plist" 2>/dev/null || true
            rm -f "$LAUNCH_AGENTS_DIR/${old}.plist"
            echo "  ✓ Removed obsolete $old"
        fi
    done

    cp "$SCRIPT_DIR/$PLIST_NAME" "$LAUNCH_AGENTS_DIR/"
    launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME"

    echo ""
    echo "✓ Scheduler installed."
    echo ""
    echo "Useful commands:"
    echo "  - Check status: launchctl list | grep haramain"
    echo "  - View log:     tail -f ~/Library/Logs/haramain-fridays.log"
    echo "  - Force tick:   $VENV_DIR/bin/python3 $SCRIPT_DIR/friday_sermon_email.py --auto"
    echo "  - Uninstall:    launchctl unload ~/Library/LaunchAgents/$PLIST_NAME"
else
    echo ""
    echo "Skipping scheduler install."
    echo ""
    echo "To install later:"
    echo "  cp $SCRIPT_DIR/$PLIST_NAME ~/Library/LaunchAgents/"
    echo "  launchctl load ~/Library/LaunchAgents/$PLIST_NAME"
fi

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
