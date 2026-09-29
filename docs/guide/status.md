---
title: "Status and decisions"
description: "What works, what is partial and what is not built, each with the test, workflow or file behind it, and the three architecture decisions."
order: 7
section: "Project"
---

Each row names its evidence. `works` means it exists and a test in `tests/` or a workflow step exercises it. `partial` means part of it is manual or missing, or nothing in the repository exercises it. `not yet` means it does not exist.

You can check the offline part yourself: `make check` runs the linter in strict mode, the unit tests and the catalog drift check. At this commit it reports 36 skills with 0 errors and 0 warnings in own skills, 21 passing tests, and a current catalog. CI adds the pin check and actionlint ([ci.yml](../../.github/workflows/ci.yml)).

## Status

| Capability | Status | Evidence |
|---|---|---|
| Skills follow the spec and the authoring rules | works | [test_validate.py](../../tests/test_validate.py), [ci.yml](../../.github/workflows/ci.yml) |
| Secret scan across every skill file | works | [test_validate.py](../../tests/test_validate.py) |
| The layout `npx skills` installs from | works | [validate.py](../../tools/validate.py) in [ci.yml](../../.github/workflows/ci.yml) |
| Vendored skills byte-identical to pin plus patches | works | `vendor.py verify` in [ci.yml](../../.github/workflows/ci.yml) |
| Local patches, applied in order | works | [test_vendor.py](../../tests/test_vendor.py) |
| README catalog generated and checked for drift | works | `catalog.py --check` in [ci.yml](../../.github/workflows/ci.yml) |
| Catalog site with upstream status | works | [pages.yml](../../.github/workflows/pages.yml) |
| Weekly upstream pull request with a review report | works | [upstream-sync.yml](../../.github/workflows/upstream-sync.yml) |
| Reference index: build, search, read | works | [test_refs.py](../../tests/test_refs.py) |
| refs MCP server and its image | works | [refs-image.yml](../../.github/workflows/refs-image.yml) |
| Trigger cases for `dev-references` | partial | [evals/dev-references.json](../../evals/dev-references.json) |
| Daily update job on macOS | partial | [tools/sync/](../../tools/sync/) |
| Updates for Claude Desktop and Cowork | partial | [sync-skills.sh](../../tools/sync/sync-skills.sh), [docs/sync.md](../sync.md) |
| An update job outside macOS | not yet | [tools/sync/](../../tools/sync/) |
| Upload to Claude Desktop with no manual step | not yet | [docs/sync.md](../sync.md) |
| Skills served over MCP (SEP-2640) | not yet | [ADR 0001](../adr/0001-git-repository-as-skills-hub.md) |
| Synonyms or embeddings in the reference search | not yet | [ADR 0003](../adr/0003-reference-corpora-as-a-search-service.md) |

The layout row rests on two checks: every directory under `skills/` has a `SKILL.md` (E010), and every `name` matches its directory (E002). The refs server row rests on the image's smoke test, which waits for the index, runs one `search_refs` call with a token and expects `401` without one. The three partial rows are the trigger cases, which nothing in the repository runs; the daily job, which no test exercises; and Claude Desktop, where the job stages zips and you upload them by hand.

## What the tests cover

The tests call no model and need no network. `make test` runs all 21.

| Test file | Tests | What they check |
|---|--:|---|
| [test_validate.py](../../tests/test_validate.py) | 7 | spec errors, authoring warnings, links, secrets, overlap |
| [test_vendor.py](../../tests/test_vendor.py) | 3 | patch order, a stale patch stopping the run, no patches |
| [test_refs.py](../../tests/test_refs.py) | 11 | Markdown parsing, anchors, a build-search-show round trip |

## Limits of what works

- **No test runs `npx skills add`.** The linter checks the layout the CLI reads; the CLI itself belongs to [vercel-labs/skills](https://github.com/vercel-labs/skills).
- **Vendored skills fail only on errors.** At this commit `python3 tools/validate.py` prints 93 notes for vendored skills, and none of them fails CI. Among them: seven bodies over 5,000 tokens, three broad `allowed-tools` grants (`agentic-actions-auditor`, `playwright-cli`, `supply-chain-risk-auditor`), and three links in the `SKILL.md` of [`loki`](../../skills/loki/SKILL.md) to reference files its folder does not have.
- **The review report has no test of its own.** [test_vendor.py](../../tests/test_vendor.py) covers patches only; nothing checks the flags that `review` in `vendor.py` raises.
- **CI on the sync pull request needs `SYNC_TOKEN`.** Without that secret the pull request carries the linter's output instead ([ADR 0002](../adr/0002-vendor-and-pin-community-skills.md)). The repository cannot show whether it has the secret.
- **The site has no test of its own.** [pages.yml](../../.github/workflows/pages.yml) builds and deploys it; nothing checks what the page shows.
- **Token counts are estimates**: characters divided by 4 ([Context cost](context-cost.md)).
- **Installed copies lag.** A machine gets a change only when it runs `npx skills update`, and the repository cannot revoke a copy ([ADR 0001](../adr/0001-git-repository-as-skills-hub.md)).
- **The reference search is keyword search.** It stems words but knows no synonyms, so a query needs the domain's terms. `/stats` lists recent queries that found nothing ([ADR 0003](../adr/0003-reference-corpora-as-a-search-service.md)).

## What is not built

- **An update job outside macOS.** `tools/sync/` holds a launchd installer only, and no document plans another.
- **Upload to Claude Desktop with no manual step.** No API or CLI exists for account skills. [docs/sync.md](../sync.md#why-claude-desktop-cant-be-fully-automatic) links the open requests and says the zip step can go once one lands.
- **Skills served over MCP.** [ADR 0001](../adr/0001-git-repository-as-skills-hub.md) keeps the `skills/<name>/` layout that a server for SEP-2640 could publish unchanged, once clients support it. No such server exists here.
- **Synonyms or embeddings in the reference search.** [ADR 0003](../adr/0003-reference-corpora-as-a-search-service.md) names a hybrid index, embeddings added to the same records, as the upgrade if the zero-result list shows many near misses.

## Decisions

Each ADR in `docs/adr/` records the options, the decision and its consequences.

- [0001: A Git repository is the skills hub](../adr/0001-git-repository-as-skills-hub.md). Accepted on 2026-09-27. One public repository with the flat `skills/<name>/` layout, installed with `npx skills`; CI enforces the spec and a generated catalog shows cost and provenance. LiteLLM's Skills Gateway, agentgateway and skills over MCP were the alternatives.
- [0002: Vendor and pin community skills](../adr/0002-vendor-and-pin-community-skills.md). Accepted on 2026-09-27 and revised on 2026-09-27 and 2026-09-29. The hub copies community and first-party skills byte for byte at a pinned commit, and they change only through reviewed pull requests. Plugins that carry more than skills stay plugins, and a local patch may only cut a reference to a skill the hub leaves out.
- [0003: Reference corpora are a search service, not skill content](../adr/0003-reference-corpora-as-a-search-service.md). Accepted on 2026-09-27. A standard-library SQLite FTS5 index with BM25 ranking, served read-only over MCP behind a bearer token and rebuilt daily, with a local CLI and DeepWiki as fallbacks. Only the corpus list is public.
