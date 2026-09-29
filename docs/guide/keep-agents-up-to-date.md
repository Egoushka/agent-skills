---
title: "Keep agents up to date"
description: "How a change travels from upstream to your agents, and the daily macOS job that updates every agent and stages Claude Desktop uploads."
order: 2
section: "Guides"
---

This page summarises [docs/sync.md](../sync.md) and the two scripts in [`tools/sync/`](../../tools/sync/).

## How an update travels

An update takes three hops, and only the first runs in this repository ([docs/sync.md](../sync.md)):

1. **Upstream to this repository.** Every Monday at 05:23 UTC, [upstream-sync.yml](../../.github/workflows/upstream-sync.yml) moves the vendored skills' pins to upstream HEAD and, if anything changed, opens or updates one pull request. Nothing lands until someone merges it ([Vendor an upstream skill](vendor-a-skill.md#review-the-weekly-update)).
2. **This repository to each machine.** `npx skills add` made local copies. They change only when `npx skills update` runs on that machine.
3. **Machine to model.** At session start the agent reads every installed skill's name and description, and loads a body only when a task matches.

## Where each agent keeps its skills

| Target | Where its skills live | How they stay current |
|---|---|---|
| Claude Code, OpenCode, Codex | `~/.agents/skills`, symlinked into each agent | `npx skills update -g`, run by the daily job |
| Claude Desktop chat, Cowork | your claude.ai account | you upload the zips the daily job stages |
| Containers, such as orchestrator workers | the container's home | a fresh install at start |

Claude Code here means the CLI and the Code tab of the desktop app.

## Install the daily job on macOS

From a clone of the repository:

```bash
./tools/sync/install-macos.sh               # daily at 09:07 and at login
./tools/sync/install-macos.sh --uninstall
tail -f ~/Library/Logs/agent-skills-sync.log
```

[install-macos.sh](../../tools/sync/install-macos.sh) copies `sync-skills.sh` to `~/.local/bin/agent-skills-sync` and loads a LaunchAgent, `com.egoushka.agent-skills-sync`, that runs it at 09:07 every day and at login. To pick another hour, set `AGENT_SKILLS_SYNC_HOUR` when you run the installer; the minute stays 7.

> [!NOTE]
> The job runs the copy in `~/.local/bin`, not the file in your clone. After `sync-skills.sh` changes, run the installer again.

## What each run does

[sync-skills.sh](../../tools/sync/sync-skills.sh) does five things:

1. It adds Homebrew's directories to `PATH`, and loads nvm if `npx` is still missing, because launchd starts with a bare `PATH`. Without `npx` it logs "npx not found; install Node.js" and stops.
2. It runs `npx -y skills@latest update -g -y`, which updates the user-wide skills of every agent.
3. It reads skill names, one per line, from `~/.config/agent-skills/desktop-skills`. The first run creates that file with `dev-references` in it.
4. For each name, it finds the installed copy in `~/.agents/skills` or `~/.claude/skills` and hashes its files. When the hash differs from the last run's, it writes `~/Downloads/claude-desktop-skills/<name>.zip`.
5. If it staged any zip, it notifies you. With `terminal-notifier` installed (`brew install terminal-notifier`), clicking the notification opens the upload page, `https://claude.ai/customize/skills`.

The script reads three variables. The LaunchAgent sets none of them, so the job uses the defaults; the variables apply when you run the script yourself.

| Variable | Default |
|---|---|
| `AGENT_SKILLS_DESKTOP_LIST` | `~/.config/agent-skills/desktop-skills` |
| `AGENT_SKILLS_OUT_DIR` | `~/Downloads/claude-desktop-skills` |
| `AGENT_SKILLS_STATE_DIR` | `~/.local/state/agent-skills`, one hash file per skill |

Nothing in `tools/sync/` installs a job on Linux or Windows. There, schedule `npx skills update -g` yourself.

## Claude Desktop and Cowork

Account skills have one way in: the upload dialog under Customize › Skills. There is no API or CLI for it, and the request for one, [anthropics/claude-code#93163](https://github.com/anthropics/claude-code/issues/93163), is open. Cowork cannot subscribe to a custom plugin marketplace either ([#66184](https://github.com/anthropics/claude-code/issues/66184)). The job's zip-and-notify step stands in until one of them lands ([docs/sync.md](../sync.md#why-claude-desktop-cant-be-fully-automatic)).

Two side effects:

- **Account skills also sync into Claude Code**, under "claude.ai sync". A skill you upload and also install with `npx skills` can show up twice, so upload only the skills you want in chat or Cowork.
- **`dev-references` in Claude Desktop needs the refs server.** claude.ai custom connectors call from Anthropic's cloud, so they cannot reach a server on a private network. docs/sync.md bridges it through `claude_desktop_config.json` with `mcp-remote`, which runs on your machine.

## Containers and workers

Workers are disposable, so they install at start instead of updating ([docs/sync.md](../sync.md#orchestrator-workers)):

```bash
DISABLE_TELEMETRY=1 npx -y skills@latest add Egoushka/agent-skills -g -a opencode -s '*' -y
```

For reproducible runs, replace `Egoushka/agent-skills` with a tree URL at a commit, as in the [Quickstart](quickstart.md#pinned-to-a-commit).
