#!/usr/bin/env bash
# Install (or remove with --uninstall) a daily launchd job that runs sync-skills.sh.
set -euo pipefail

LABEL="com.egoushka.agent-skills-sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
BIN="$HOME/.local/bin/agent-skills-sync"
LOG="$HOME/Library/Logs/agent-skills-sync.log"
HOUR="${AGENT_SKILLS_SYNC_HOUR:-9}"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
  rm -f "$PLIST" "$BIN"
  echo "removed $LABEL"
  exit 0
fi

mkdir -p "$(dirname "$BIN")" "$(dirname "$PLIST")" "$(dirname "$LOG")"
install -m 0755 "$(cd "$(dirname "$0")" && pwd)/sync-skills.sh" "$BIN"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$BIN</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>7</integer></dict>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed $LABEL: daily at $HOUR:07 and at login; log: $LOG"
echo "desktop skill list: ~/.config/agent-skills/desktop-skills"
