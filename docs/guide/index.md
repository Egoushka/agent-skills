---
title: "Overview"
description: "What agent-skills holds, how its skills, pins and context numbers fit together, what it leaves out, and where it stands."
order: 0
section: "Get started"
---

agent-skills is a Git repository of [Agent Skills](https://agentskills.io) for Claude Code, OpenCode, Codex and the other agents that read `SKILL.md`. You install them with the [`skills`](https://github.com/vercel-labs/skills) CLI. Skills written elsewhere come in vendored: `tools/vendor.py` copies them byte for byte from their upstream repository at a pinned commit. Every skill shows what it costs in context, once in every session and again when it fires.

## What is in it

`skills/` holds 36 skills, each a directory with a `SKILL.md`:

- **1 own skill**, [`dev-references`](../../skills/dev-references/SKILL.md). It searches curated developer reference corpora and answers with cited links or sections.
- **35 vendored skills** from 9 upstream repositories. [vendor.json](../../vendor.json) lists each one with its repository, its path there, the pinned commit and the license.

Four more plugins install from their publishers instead: `dotnet`, `differential-review`, `sharp-edges` and `insecure-defaults`, listed in [publishers.json](../../publishers.json). They carry a language server, sub-agents or a command, which copying their skills alone would drop ([ADR 0002](../adr/0002-vendor-and-pin-community-skills.md)).

The [README catalog](../../README.md#catalog) and the [catalog site](https://egoushka.github.io/agent-skills/) show every skill with its origin, license and token counts. All 36 descriptions together come to about 3.7k tokens in every session. `catalog.py` generates the README block from the skills, and CI fails when the block is stale, so it holds the current list. [Reference](reference.md#the-skill-list) groups the skills by origin.

## How it works

The [README](../../README.md#how-it-fits-together) splits the system into three layers, each kept where its kind of content belongs:

- **Skills are instructions.** They are small, so `npx skills` copies them onto every machine and symlinks them into each agent. `vendor.json` is the lock file for the vendored ones.
- **Reference corpora are data.** About 90 MB of catalogs and curricula that change daily, some licensed for personal use only, so they stay on one server. [`refs/`](../../refs/README.md) serves them over MCP and `dev-references` queries them. The same engine runs as a local CLI ([ADR 0003](../adr/0003-reference-corpora-as-a-search-service.md)).
- **DeepWiki is breadth.** `dev-references` falls back to DeepWiki MCP for public repositories outside the corpora.

Three scripts under `tools/` keep the skills honest:

- [validate.py](../../tools/validate.py) lints every skill against the Agent Skills spec and the [authoring rules](../authoring.md).
- [vendor.py](../../tools/vendor.py) copies vendored skills at their pins, checks the copies byte for byte, and moves the pins when upstream changes.
- [catalog.py](../../tools/catalog.py) builds the README catalog and the site from the skills, `vendor.json`, the linter's findings and git history.

[ci.yml](../../.github/workflows/ci.yml) runs the linter, the pin check, the catalog check, the unit tests and actionlint on every push to `main` and every pull request. [upstream-sync.yml](../../.github/workflows/upstream-sync.yml) opens one pull request a week with the upstream changes and a review report.

## What it does not do

- **No skills server.** The skills are files in a public repository. An installed copy changes only when `npx skills update` runs on that machine, and the repository cannot revoke it ([ADR 0001](../adr/0001-git-repository-as-skills-hub.md)).
- **No access control.** Everything under `skills/` is public. Private skills belong in a separate private repository ([authoring rule 9](../authoring.md#9-keep-private-skills-private)).
- **No local edits to vendored skills.** Fixes go upstream. The one exception is a recorded patch that cuts a reference to an upstream skill the hub leaves out; `executing-plans` and `test-driven-development` carry one each ([ADR 0002](../adr/0002-vendor-and-pin-community-skills.md)).
- **No copies of the corpora.** The repository publishes only the list of what to index, [sources.json](../../skills/dev-references/assets/sources.json).
- **No evals in CI.** Trigger cases call a model, so they run on demand ([authoring rule 6](../authoring.md#6-evals-before-prose)).
- **No automatic upload to Claude Desktop.** Its chat and Cowork take skills only through an upload dialog. The daily job stages zips for you to upload ([docs/sync.md](../sync.md)).

## Where it stands

- **No releases.** The repository has no tags, and [SECURITY.md](../../SECURITY.md) supports only the latest commit on `main`.
- **The checks pass.** `make check` reports 36 skills with 0 errors and 0 warnings in own skills, 21 passing unit tests and a current catalog. [Status and decisions](status.md) gives each capability's status and the evidence behind it.
- **A personal, curated set.** [CONTRIBUTING.md](../../CONTRIBUTING.md) asks every new skill to earn its always-on context cost. Suggest a skill or a corpus with the [request template](../../.github/ISSUE_TEMPLATE/skill-request.yml).

## Where to go next

- [Quickstart](quickstart.md): install one skill and read what it costs.
- [Keep agents up to date](keep-agents-up-to-date.md): how updates travel, and the daily job.
- [Write a skill](write-a-skill.md) and [Vendor an upstream skill](vendor-a-skill.md): add to the hub.
- [Context cost](context-cost.md): what the two numbers on every skill measure.
- [Reference](reference.md): make targets, scripts, finding codes and file fields.
- [Status and decisions](status.md): what works, with evidence, and the three ADRs.
