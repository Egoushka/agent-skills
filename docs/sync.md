# Keeping agents in sync

Updates travel in three hops. Only the first is automated in the repo:

1. **Upstream → this repo.** The weekly `upstream-sync` job opens a PR; nothing lands until it is merged.
2. **Repo → each machine.** `npx skills add` made local copies. They change only on `npx skills update`, so each machine runs that on a schedule.
3. **Machine → model.** At session start the agent reads every installed skill's name and description, and loads a body only when a task matches.

| Target | Where its skills live | How it stays current |
|---|---|---|
| Claude Code (CLI and the desktop app's Code tab), OpenCode, Codex | `~/.agents/skills`, symlinked into each agent | `npx skills update -g` in the daily job |
| Claude Desktop chat and Cowork | Your claude.ai account (Customize › Skills) | Semi-automatic: the job zips changed skills and notifies you; you upload them |
| Orchestrator workers (containers) | The container's home | Install at container start |

## macOS: daily job

```bash
./tools/sync/install-macos.sh               # daily at 09:07 and at login
./tools/sync/install-macos.sh --uninstall
tail -f ~/Library/Logs/agent-skills-sync.log
```

`sync-skills.sh` runs `npx skills update -g -y`. It then checks each skill named in `~/.config/agent-skills/desktop-skills` (default: `dev-references`). When one has changed since the last run, it writes `~/Downloads/claude-desktop-skills/<name>.zip` and posts a notification. With `terminal-notifier` installed (`brew install terminal-notifier`), clicking the notification opens the upload page.

### Why Claude Desktop can't be fully automatic

Account skills can be added only through the upload dialog: there is no API or CLI, and the request for one ([anthropics/claude-code#93163](https://github.com/anthropics/claude-code/issues/93163)) is open. Cowork can't subscribe to a custom plugin marketplace either ([#66184](https://github.com/anthropics/claude-code/issues/66184)). When either lands, the job can replace the zip-and-notify step.

Two side effects to know:

- **Account skills also sync into Claude Code**, where they appear under "claude.ai sync". A skill that is both uploaded and installed with `npx skills` can show up twice. Upload only the skills you want in chat or Cowork.
- **`dev-references` in Claude Desktop needs the refs server.** claude.ai custom connectors call from Anthropic's cloud, so they cannot reach a tailnet-only endpoint. Bridge it locally through `claude_desktop_config.json`, which runs on your Mac inside the tailnet:

  ```json
  {
    "mcpServers": {
      "refs": {
        "command": "npx",
        "args": ["-y", "mcp-remote", "https://refs.example.ts.net/mcp", "--header", "Authorization:Bearer ${REFS_TOKEN}"],
        "env": { "REFS_TOKEN": "<token>" }
      }
    }
  }
  ```

## Orchestrator workers

Workers are disposable, so they install fresh at start instead of updating:

```bash
DISABLE_TELEMETRY=1 npx -y skills@latest add Egoushka/agent-skills -g -a opencode -s '*' -y
```

Pin a commit for reproducible runs by installing from a tree URL (`https://github.com/Egoushka/agent-skills/tree/<sha>/skills/<name>`) instead of the repo shorthand.
