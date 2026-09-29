---
title: "Quickstart"
description: "Install one skill user-wide with npx skills, read what it costs in context, and keep it current in Claude Code, OpenCode or Codex."
order: 1
section: "Get started"
---

You install skills from this repository with the [`skills`](https://github.com/vercel-labs/skills) CLI. It keeps one copy of each skill per machine and symlinks it into each agent's folder, so one update reaches every agent ([README](../../README.md#install)).

## Before you start

- Node.js, for `npx`.
- An agent that reads `SKILL.md`. The README names Claude Code, OpenCode and Codex.

> [!IMPORTANT]
> A skill hands instructions, and sometimes scripts, to an agent that runs with your permissions. The README's [security model](../../README.md#security-model) says what this repository checks before a skill reaches you. Three skills pre-approve broad command execution in `allowed-tools`: `agentic-actions-auditor`, `playwright-cli` and `supply-chain-risk-auditor`. `python3 tools/validate.py` lists them under W110.

## Install one skill

```bash title="One skill, user-wide"
npx skills add Egoushka/agent-skills -g -s systematic-debugging
```

`-g` installs user-wide and `-s` names the skill; the catalog site spells it `--skill` ([catalog.py](../../tools/catalog.py)). `systematic-debugging` needs no setup, which makes it a good first skill. A user-wide install lives in `~/.agents/skills`, symlinked into each agent ([docs/sync.md](../sync.md)).

Start a new session. At session start the agent reads the name and description of every installed skill, and it loads a skill's body only when a task matches the description ([docs/sync.md](../sync.md)). A failing test or an unexpected error is the kind of task the description of `systematic-debugging` names.

## Other ways to install

### Choose at a prompt

```bash
npx skills add Egoushka/agent-skills
```

The CLI asks which skills to install and into which agents.

### Every skill, for named agents

```bash
npx skills add Egoushka/agent-skills -g -a claude-code -a opencode -s '*' -y
```

`-a` names an agent and repeats. `-s '*'` takes every skill, and `-y` runs without prompts, the way the [daily job](keep-agents-up-to-date.md) and container installs use it.

> [!NOTE]
> The repository's examples name only the `claude-code` and `opencode` agents. For Codex or another agent, pick it in the interactive form, or look up its name in the `skills` CLI's documentation.

Every installed skill costs its description in every session, and all 36 together come to about 3.7k tokens, so install the skills you use.

### Pinned to a commit

[docs/sync.md](../sync.md#orchestrator-workers) pins a commit by installing from a tree URL instead of the repository shorthand:

```bash title="One skill at a commit of this repository"
npx skills add https://github.com/Egoushka/agent-skills/tree/<sha>/skills/<name> -g
```

A vendored skill is already pinned to an upstream commit in `vendor.json`. The tree URL also fixes which commit of this repository you take.

### Plugins from publishers

Four plugins install from their publishers with Claude Code's plugin commands. These lines come from [publishers.json](../../publishers.json):

```bash title="Claude Code"
claude plugin marketplace add dotnet/skills && claude plugin install dotnet@dotnet-agent-skills
claude plugin marketplace add trailofbits/skills && claude plugin install differential-review@trailofbits
claude plugin marketplace add trailofbits/skills && claude plugin install sharp-edges@trailofbits
claude plugin marketplace add trailofbits/skills && claude plugin install insecure-defaults@trailofbits
```

The repository gives no command for these plugins in OpenCode or Codex.

## Read what it costs

The [README catalog](../../README.md#catalog) gives every skill two numbers:

| Column | What it counts | `systematic-debugging` |
|---|---|---|
| Always loaded | the name and description, in every session | ≈29 |
| On activation | the `SKILL.md` body, when the skill fires | ≈2.3k |

Both are estimates: characters divided by 4. [Context cost](context-cost.md) explains them and what they leave out.

## Keep it current

```bash
npx skills update      # what changed since you installed (README)
npx skills update -g   # skills installed with -g (docs/sync.md)
```

Upstream changes reach this repository as a weekly pull request, and your machine only when it runs `update`. On macOS, `./tools/sync/install-macos.sh` from a clone installs a daily job that runs the update for you. Claude Desktop chat and Cowork keep skills in your claude.ai account and take them only as uploads. [Keep agents up to date](keep-agents-up-to-date.md) covers both.

## Set up dev-references

`dev-references` uses the first backend it finds ([SKILL.md](../../skills/dev-references/SKILL.md)):

1. **The refs MCP server**, one shared index, through the tools `refs:search_refs`, `refs:read_ref` and `refs:list_ref_sources`.
2. **The local CLI**, `python3 scripts/refs.py`, which needs `python3` and `git`. With no index yet, the skill asks you before it runs `python3 scripts/refs.py update`, a one-time download of about 90 MB.
3. **DeepWiki MCP**, for public repositories outside the corpora.

[refs/README.md](../../refs/README.md#run-it) runs the server with Docker Compose and connects Claude Code and OpenCode to it. For Claude Code the command has this shape:

```bash
claude mcp add --transport http refs https://<refs-host>/mcp --scope user \
  --header "Authorization: Bearer $REFS_TOKEN"
```

> [!WARNING]
> Keep the endpoint private. One of the corpora, developer-roadmap, allows personal use only, so the server belongs on a private network or behind a proxy, with `REFS_TOKEN` set ([ADR 0003](../adr/0003-reference-corpora-as-a-search-service.md)).
