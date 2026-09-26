#!/usr/bin/env bash
# Keep every agent's skills current, and stage Claude Desktop uploads.
#
# 1. `npx skills update -g`: Claude Code (CLI and the desktop Code tab), OpenCode, Codex
#    and the other agents installed with `npx skills add -g` pick up merged changes.
# 2. Claude Desktop chat/Cowork keeps skills in your claude.ai account, which has no
#    upload API (only Customize > Skills > Upload). For each skill listed in
#    $DESKTOP_LIST that changed since the last run, this builds <name>.zip in
#    $OUT_DIR and notifies you, so an upload is one drag-and-drop.
set -euo pipefail

DESKTOP_LIST="${AGENT_SKILLS_DESKTOP_LIST:-$HOME/.config/agent-skills/desktop-skills}"
OUT_DIR="${AGENT_SKILLS_OUT_DIR:-$HOME/Downloads/claude-desktop-skills}"
STATE_DIR="${AGENT_SKILLS_STATE_DIR:-$HOME/.local/state/agent-skills}"
UPLOAD_URL="https://claude.ai/customize/skills"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

# launchd starts with a bare PATH: add Homebrew and nvm so npx resolves.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v npx >/dev/null 2>&1 && [ -s "$HOME/.nvm/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$HOME/.nvm/nvm.sh" >/dev/null
fi
command -v npx >/dev/null 2>&1 || { log "npx not found; install Node.js"; exit 1; }

log "updating global skills"
npx -y skills@latest update -g -y

skills_root() {
  for dir in "$HOME/.agents/skills" "$HOME/.claude/skills"; do
    [ -d "$dir/$1" ] && { echo "$dir"; return 0; }
  done
  return 1
}

digest() {
  (cd "$1" && find -L . -type f -not -path '*/__pycache__/*' -not -name '.DS_Store' -print0 \
    | sort -z | xargs -0 shasum -a 256) | shasum -a 256 | cut -d' ' -f1
}

mkdir -p "$STATE_DIR" "$(dirname "$DESKTOP_LIST")"
[ -f "$DESKTOP_LIST" ] || printf '# One skill name per line: staged for Claude Desktop when it changes.\ndev-references\n' > "$DESKTOP_LIST"

changed=()
while IFS= read -r name; do
  name="${name%%#*}"; name="$(echo "$name" | tr -d '[:space:]')"
  [ -n "$name" ] || continue
  if ! root="$(skills_root "$name")"; then
    log "skip $name: not installed (npx skills add Egoushka/agent-skills -g -s $name)"
    continue
  fi
  new="$(digest "$root/$name")"
  old="$(cat "$STATE_DIR/$name.sha256" 2>/dev/null || true)"
  [ "$new" = "$old" ] && continue
  mkdir -p "$OUT_DIR"
  rm -f "$OUT_DIR/$name.zip"
  (cd "$root" && zip -qr "$OUT_DIR/$name.zip" "$name" -x '*/__pycache__/*' '*/.DS_Store')
  echo "$new" > "$STATE_DIR/$name.sha256"
  changed+=("$name")
  log "staged $OUT_DIR/$name.zip"
done < "$DESKTOP_LIST"

if [ "${#changed[@]}" -gt 0 ]; then
  msg="Upload to Claude Desktop: ${changed[*]}"
  if command -v terminal-notifier >/dev/null 2>&1; then
    terminal-notifier -title "agent-skills" -message "$msg" -open "$UPLOAD_URL" -group agent-skills
  else
    osascript -e "display notification \"$msg\" with title \"agent-skills\" subtitle \"$OUT_DIR\""
  fi
  log "$msg ($UPLOAD_URL)"
else
  log "no desktop skill changed"
fi
