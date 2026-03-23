#!/bin/bash
# AI Research Digest Agent - Setup Script
# ========================================
# Runs automatically when you open your laptop each morning
# Uses Claude Code CLI (your existing subscription) - no extra API costs!
# Only requires: agent.py + setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

echo "🔬 AI Research Digest Agent Setup"
echo "=================================="

# Check for Claude Code CLI
echo ""
echo "🔍 Checking for Claude Code CLI..."
if ! command -v claude &> /dev/null; then
    echo "❌ Claude Code not found!"
    echo ""
    echo "   Install it with: npm install -g @anthropic-ai/claude-code"
    echo "   Then run this setup again."
    exit 1
fi
echo "✅ Claude Code found: $(claude --version 2>/dev/null || echo 'installed')"

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "📱 Detected: macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo "🐧 Detected: Linux"
else
    echo "⚠️  Unknown OS: $OSTYPE"
    echo "   Manual setup may be required."
fi

# Step 1: Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Step 2: Install dependencies
echo ""
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r "$SCRIPT_DIR/Requirements.txt"

# Step 3: Create logs directory
mkdir -p "$SCRIPT_DIR/logs"

# Step 4: Create runner script
echo ""
echo "📝 Creating runner script..."
cat > "$SCRIPT_DIR/run_digest.sh" << 'RUNNER'
#!/bin/bash
# Runner script - triggered on login/wake
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Small delay to ensure network is up
sleep 10

# Load environment variables
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Activate virtual environment and run
source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/agent.py" "$@"
RUNNER
chmod +x "$SCRIPT_DIR/run_digest.sh"

# Step 5: Create .env file if missing
echo ""
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "📝 Creating .env template..."
    cat > "$SCRIPT_DIR/.env" << 'ENVFILE'
# AI Research Digest Agent Configuration
# No API key needed - uses Claude Code CLI!

# Gmail Configuration (for sending emails)
# Note: Use an App Password, not your regular Gmail password
# Create one at: https://myaccount.google.com/apppasswords
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password

# Recipient email (defaults to GMAIL_ADDRESS if not set)
RECIPIENT_EMAIL=your_email@gmail.com
ENVFILE
    echo "   Created .env - please edit with your Gmail credentials"
fi

# Step 6: Install login trigger based on OS
echo ""
echo "🚀 Setting up login trigger..."

if [[ "$OS" == "macos" ]]; then
    # macOS: Use LaunchAgent (embedded plist)
    LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
    PLIST_NAME="com.ai-research-digest.plist"
    PLIST_DEST="$LAUNCH_AGENTS_DIR/$PLIST_NAME"
    
    mkdir -p "$LAUNCH_AGENTS_DIR"
    
    cat > "$PLIST_DEST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ai-research-digest</string>
    <key>ProgramArguments</key>
    <array>
        <string>$SCRIPT_DIR/run_digest.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/logs/launchd_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/logs/launchd_stderr.log</string>
</dict>
</plist>
PLIST
    
    # Load the launch agent
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    launchctl load "$PLIST_DEST"
    
    echo "✅ macOS LaunchAgent installed!"
    echo "   Location: $PLIST_DEST"
    
elif [[ "$OS" == "linux" ]]; then
    # Linux: Use XDG autostart (embedded desktop file)
    AUTOSTART_DIR="$HOME/.config/autostart"
    DESKTOP_NAME="ai-research-digest.desktop"
    DESKTOP_DEST="$AUTOSTART_DIR/$DESKTOP_NAME"
    
    mkdir -p "$AUTOSTART_DIR"
    
    cat > "$DESKTOP_DEST" << DESKTOP
[Desktop Entry]
Type=Application
Name=Atom — AI Research Digest
Comment=Daily AI research digest by Atom
Exec=$SCRIPT_DIR/run_digest.sh
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=30
StartupNotify=false
DESKTOP
    chmod +x "$DESKTOP_DEST"
    
    echo "✅ Linux autostart installed!"
    echo "   Location: $DESKTOP_DEST"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "=================================="
echo "📋 Next Steps:"
echo "=================================="
echo ""
echo "1. Configure Gmail credentials:"
echo "   nano $SCRIPT_DIR/.env"
echo ""
echo "   Required:"
echo "   - GMAIL_ADDRESS (your email)"
echo "   - GMAIL_APP_PASSWORD (16-char app password)"
echo ""
echo "   No API key needed - uses your Claude Code subscription!"
echo ""
echo "2. Test the agent:"
echo "   $SCRIPT_DIR/run_digest.sh --test"
echo ""
echo "3. Done! Digest runs automatically on laptop open."
echo ""
echo "=================================="
echo "📧 Gmail App Password:"
echo "=================================="
echo "   https://myaccount.google.com/apppasswords"
echo ""
echo "=================================="
echo "🔧 Commands:"
echo "=================================="
echo "   ./run_digest.sh --test   # Test (no email)"
echo "   ./run_digest.sh --force  # Force run"
echo "   cat logs/digest.log      # Check logs"
echo ""
if [[ "$OS" == "macos" ]]; then
echo "   # Disable: launchctl unload ~/Library/LaunchAgents/$PLIST_NAME"
echo "   # Enable:  launchctl load ~/Library/LaunchAgents/$PLIST_NAME"
elif [[ "$OS" == "linux" ]]; then
echo "   # Disable: rm ~/.config/autostart/$DESKTOP_NAME"
fi
echo ""