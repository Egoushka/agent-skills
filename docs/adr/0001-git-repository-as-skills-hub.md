# 0001: A Git repository is the skills hub

- Status: accepted
- Date: 2026-09-27

## Context

The skills should be usable from Claude Code, OpenCode, Codex and a planned orchestrator that drives OpenCode sessions, while staying reviewable and public. Options considered, as of September 2026:

| Option | What it is | Assessment |
|---|---|---|
| LiteLLM Skills Gateway | Registers Git-backed skills and serves a `marketplace.json` that Claude Code adds as a plugin marketplace | Works, but it is a catalog layered on the same Git sources and oriented to Claude Code's marketplace. It is built for teams and adds nothing for a single maintainer |
| agentgateway | MCP/A2A gateway | No skills support; [issue #3579](https://github.com/agentgateway/agentgateway/issues/3579) is an open request |
| Skills over MCP (SEP-2640) | Servers expose `skills/list` and `skills/get`; clients fetch skills at runtime | Reported final in September 2026, but client support is uneven; early servers exist |
| Git repository + [`npx skills`](https://github.com/vercel-labs/skills) | One repository of `skills/<name>/SKILL.md`; the CLI installs into 70+ agents via symlinks | Zero infrastructure, works offline, review happens in pull requests |

## Decision

A public Git repository with the flat `skills/<name>/` layout, installed with `npx skills`. CI enforces the spec; a generated catalog (README and Pages) makes cost and provenance visible.

## Consequences

- Installed skills are local copies. An update reaches a machine only when `npx skills update` runs there, and there is no central revocation.
- No per-user access control, so private skills need a separate private repository (see [authoring rule 9](../authoring.md#9-keep-private-skills-private)).
- The layout is exactly what a skills-over-MCP server would serve. When clients support SEP-2640, a server can publish this directory without restructuring it, and the orchestrator can fetch skills at runtime instead of relying on installs.
