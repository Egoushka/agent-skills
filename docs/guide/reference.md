---
title: "Reference"
description: "Make targets, the tools/ scripts and their finding codes, the fields of vendor.json and publishers.json, the refs service, the workflows and the skill list."
order: 6
section: "Reference"
---

## Make targets

Run them from the repository root. `PY` picks the interpreter and defaults to `python3`; the tools need PyYAML, pinned in [requirements-dev.txt](../../requirements-dev.txt). `make help` prints the list from the [Makefile](../../Makefile).

| Target | Runs | Network |
|---|---|---|
| `check` | `validate` and `test`, then `catalog.py --check` | no |
| `validate` | `validate.py --strict` | no |
| `test` | `python3 -m unittest discover -s tests -v` | no |
| `catalog` | `catalog.py`, which rewrites the README block | no |
| `site` | `catalog.py --site _site --upstream` | GitHub |
| `vendor-status` | `vendor.py status` | GitHub |
| `vendor-sync` | `vendor.py sync` | GitHub |
| `vendor-update` | `vendor.py sync --update --report upstream-report.md` | GitHub |
| `verify` | `vendor.py verify` | GitHub |
| `refs-update` | `refs.py update`: clone the corpora, build the index | GitHub |
| `refs-serve` | `refs/server.py`; needs `refs/requirements.txt` | GitHub, when no index exists |
| `image` | `docker build -f refs/Dockerfile -t agent-skills-refs .` | Docker |

`check` is what CI runs offline. CI also runs `verify` and actionlint ([ci.yml](../../.github/workflows/ci.yml)).

## Scripts

**[tools/validate.py](../../tools/validate.py)** lints every skill.

| Invocation | Result |
|---|---|
| `validate.py` | a report per skill; exit 1 on any error |
| `validate.py --strict` | also exit 1 on a warning in an own skill |
| `validate.py --json` | the findings as JSON |

Each skill prints `✓` or `✗`, its origin (`own` or `vendored`), and one line per finding marked `✗` for an error, `!` for a warning or `·` for a note. The last line counts the skills, the errors, and the warnings in own skills. `catalog.py` imports the same checks for the site.

**[tools/vendor.py](../../tools/vendor.py)** keeps the vendored skills at their pins. Every command reaches GitHub.

| Invocation | Result |
|---|---|
| `vendor.py status [--json]` | pinned commit against upstream head, per skill |
| `vendor.py sync [NAME ...]` | copy skills again at their pinned commits |
| `vendor.py sync --update [NAME ...]` | move pins to the head of each entry's `ref` |
| `vendor.py sync ... --report FILE` | also write the Markdown review report |
| `vendor.py verify` | exit 1 if a copy differs from its pin plus patches |

`sync` rewrites `vendor.json`. In a GitHub Actions run it also writes `changed=true` or `changed=false` to `$GITHUB_OUTPUT`, which the weekly workflow reads.

**[tools/catalog.py](../../tools/catalog.py)** builds the catalog from the skills, `vendor.json`, `publishers.json`, the corpus list, the linter's findings and git history.

| Invocation | Result |
|---|---|
| `catalog.py` | rewrite the README block between the catalog markers |
| `catalog.py --check` | exit 1 if the README block is stale |
| `catalog.py --site DIR` | also write `DIR/index.html` and `DIR/catalog.json` |
| `catalog.py --site DIR --upstream` | add each pin's upstream status (network) |

The page comes from the template [tools/site/index.html](../../tools/site/index.html).

## Finding codes

`validate.py` raises these codes. An error fails the run; a warning fails it only with `--strict`, and only in an own skill.

| Code | Level | Raised when |
|---|---|---|
| E001 | error | the frontmatter is missing, invalid YAML, or not a mapping |
| E002 | error | `name` is missing, malformed, or not the directory's name |
| E003 | error | `description` is missing or over 1,024 characters |
| E004 | error | `compatibility` is not a string of 1 to 500 characters |
| E005 | error | `metadata` is not a map of strings to strings |
| E006 | error | `allowed-tools` is not a string |
| E008 | error | a relative link in the body points at a missing file |
| E009 | error | a text file in the skill looks like it holds a secret |
| E010 | error | a directory under `skills/` has no `SKILL.md` |
| E011 | error | `vendor.json` lists a skill that is not under `skills/` |
| E012 | error | `description` contains `<` or `>` |
| E013 | error | `name` contains `claude` or `anthropic` |
| W101 | warning | the body is over 500 lines |
| W102 | warning | the body is over 5,000 tokens |
| W103 | warning | the description is in the first or second person |
| W104 | warning | the description does not say when to use the skill |
| W107 | warning | a `.md` file over 100 lines has no contents heading |
| W108 | warning | a file path in the body uses backslashes |
| W109 | warning | a `.md` file other than `SKILL.md` links further `.md` files |
| W110 | warning | `allowed-tools` pre-approves broad command execution |
| W111 | warning | the frontmatter has fields outside the spec |
| W112 | warning | the description overlaps another by 35% or more |

The numbering has gaps: there is no E007, W105 or W106.

In a vendored skill, every warning prints as a note, and so does E008, marked "(upstream)". Its other errors still fail, because they break or endanger the install.

E009 looks for private key blocks, AWS access keys, GitHub tokens, Anthropic keys, OpenAI-style keys and Slack tokens in every file with a text suffix, or none. W110 matches a bare `Bash`, `Bash(*)`, or `Bash(…:*)` for `npx`, `npm`, `sh`, `bash`, `python`, `python3` or `curl`. [Context cost](context-cost.md#overlapping-descriptions) explains how W112 measures overlap.

## Files

### vendor.json

The lock file for vendored skills: a `$comment` and a `skills` array with one entry per skill.

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | directory under `skills/`; equals the upstream `SKILL.md` `name` |
| `repo` | yes | GitHub `owner/name` |
| `path` | yes | the skill's directory inside `repo` |
| `rev` | yes | the pinned commit, a full SHA |
| `ref` | no | the ref whose head `--update` moves to; default `HEAD` |
| `license` | no | the license as the README and the site show it |
| `license_file` | no | upstream path of the license, copied in as `LICENSE` |
| `category` | no | a label on the site's card and in its filter |
| `why` | no | why it earns its context; shown on the site's card |
| `patches` | no | patch files, applied in this order after each fetch |

`vendor.py` needs the four fields marked yes. The README asks for `license` and `why` as well, and all 35 entries carry both, along with `ref` and `category`. 34 have a `license_file`. The exception is `angular-developer`: its repository has no license file, so its `license` reads "MIT (declared in SKILL.md; repository has no license file)" and its folder holds no `LICENSE`. Two entries have `patches`: `executing-plans` and `test-driven-development`.

### publishers.json

Plugins that install from their publishers: a `$comment` and a `plugins` array.

| Field | Meaning | Used by |
|---|---|---|
| `name` | the plugin's name | README, site |
| `repo` | the publisher's GitHub `owner/name`, linked from the name | README, site |
| `license` | the plugin's license | nothing |
| `why` | what the plugin is for | README, site |
| `why_plugin` | why it installs as a plugin | README, site |
| `install` | the command that installs it | README, site |

**Trigger cases** live in `evals/<skill>.json`: a `skill` name, a `should_trigger` array of objects with a `query` and an `expected_behavior` list, and a `should_not_trigger` array of prompts. [evals/dev-references.json](../../evals/dev-references.json) is the only one, and no tool in the repository reads these files.

## The refs service

**[refs.py](../../skills/dev-references/scripts/refs.py)** is the index engine. It ships inside `dev-references`, uses the standard library only, and needs Python 3.9 or later and git 2.25 or later.

| Command | Does |
|---|---|
| `update` | sync every enabled source, then rebuild the index |
| `sync [NAME ...]` | clone or refresh sources, shallow and sparse where set |
| `build` | rebuild the index from what is on disk |
| `search QUERY` | ranked search; `--source`, `--kind`, `--limit`, `--json` |
| `show ID` | a section or document in full, or a link's details |
| `sources [--json]` | what is indexed, from which commit, under which license |

`--kind` takes `link` or `section`. `--limit` defaults to 8, and the search keeps it between 1 and 50. `show --max-chars` defaults to 12000. `REFS_HOME` sets the data directory, by default `~/.local/share/dev-refs`, and `REFS_SOURCES` the corpus list, by default the skill's `assets/sources.json`.

**[refs/server.py](../../refs/server.py)** serves the index over MCP. [refs/README.md](../../refs/README.md) runs it.

| Endpoint | Purpose | Auth |
|---|---|---|
| `POST /mcp` | MCP over stateless Streamable HTTP, JSON responses | bearer token |
| `GET /stats` | counters and the last 50 queries that found nothing | bearer token |
| `GET /metrics` | Prometheus text | none |
| `GET /healthz` | liveness and whether the index is ready | none |

It has three read-only tools: `search_refs` (`query`, `source`, `kind`, and `limit` from 1 to 50, default 8), `read_ref` (`id`, and `max_chars`, default 12000, at most 60000) and `list_ref_sources`.

| Variable | Default | Meaning |
|---|---|---|
| `REFS_TOKEN` | empty, so auth is off | the bearer token clients send |
| `REFS_ALLOWED_HOSTS` | empty, so no Host check | comma-separated Hosts; enables DNS-rebinding protection |
| `REFS_REFRESH_HOURS` | `24` | hours between re-sync and rebuild; `0`: first start only |
| `REFS_PORT`, `REFS_HOST` | `8765`, `0.0.0.0` | the listener |
| `REFS_HOME`, `REFS_SOURCES` | `/data`, `/app/sources.json` in the image | the data directory and the corpus list |

A refresh builds a new index file and swaps it in, so queries keep working during a rebuild. If a sync fails, the old index keeps serving and `refs_refresh_failures_total` goes up.

**[sources.json](../../skills/dev-references/assets/sources.json)** lists the corpora, 11 of them at this commit. Its `$comment` documents the fields:

| Field | Meaning |
|---|---|
| `name` | the source name that `--source` and `source` filter on |
| `repo` | GitHub `owner/name` |
| `include`, `exclude` | globs relative to the repository root |
| `sparse` | check out only these top-level paths |
| `sections` | index prose chunks, not only links |
| `whole_doc` | one record per file |
| `context` | a regex whose `ctx` group labels records by path |
| `parser` | `markdown` or `fcc-blocks` |
| `enabled` | `false` leaves the source out |
| `license`, `about`, `use_for` | returned by `list_ref_sources` |

The catalog site's corpus table shows each enabled source's `use_for` and `license`.

## Workflows

| Workflow | Runs on | Does |
|---|---|---|
| [ci](../../.github/workflows/ci.yml) | push to `main`, pull requests, by hand | lint, pin check, catalog check, tests, actionlint |
| [pages](../../.github/workflows/pages.yml) | push to `main`, daily at 06:17 UTC, by hand | builds the site with upstream status and deploys it |
| [upstream-sync](../../.github/workflows/upstream-sync.yml) | Mondays at 05:23 UTC, by hand | moves the pins; on a change, opens the review pull request |
| [refs-image](../../.github/workflows/refs-image.yml) | push to `main` that touches the refs code, by hand | builds, smoke-tests and publishes the refs image |

The refs code means `refs/`, the `scripts/` and `assets/` of `dev-references`, and the workflow file. The smoke test waits for `/healthz` to report the index ready, calls `search_refs` over `/mcp` with a token, and expects `401` without one. The workflow builds the image, `ghcr.io/egoushka/agent-skills-refs`, for amd64 and arm64.

The workflows pin every action by commit. Dependabot proposes updates weekly for the actions, the pip requirements in `/` and `/refs`, and the refs image's base ([dependabot.yml](../../.github/dependabot.yml)).

## The skill list

The current list is in four places:

- the [README catalog](../../README.md#catalog), which `catalog.py` generates and CI keeps current;
- the [catalog site](https://egoushka.github.io/agent-skills/), with a `catalog.json` beside the page;
- `npx skills add Egoushka/agent-skills`, which asks you to choose from it;
- `skills/` itself, one directory per skill.

By origin, from `vendor.json` and `skills/` at this commit:

- **Own** (1): `dev-references`.
- **[dotnet/skills](https://github.com/dotnet/skills)** (12, MIT): `analyzing-dotnet-performance`, `configuring-opentelemetry-dotnet`, `convert-to-cpm`, `create-datadriven-aspnetcore`, `dotnet-trace-collect`, `dotnet-webapi`, `dump-collect`, `microbenchmarking`, `migrate-dotnet10-to-dotnet11`, `migrate-dotnet9-to-dotnet10`, `migrate-nullable-references`, `optimizing-ef-core-queries`.
- **[obra/superpowers](https://github.com/obra/superpowers)** (10, MIT): `brainstorming`, `executing-plans`, `finishing-a-development-branch`, `requesting-code-review`, `subagent-driven-development`, `systematic-debugging`, `test-driven-development`, `using-git-worktrees`, `verification-before-completion`, `writing-plans`.
- **[grafana/skills](https://github.com/grafana/skills)** (5, Apache-2.0): `alerting-irm`, `dashboarding`, `loki`, `prometheus`, `promql`.
- **[mattpocock/skills](https://github.com/mattpocock/skills)** (2, MIT): `grill-me`, `grilling`.
- **[trailofbits/skills](https://github.com/trailofbits/skills)** (2, CC-BY-SA-4.0): `agentic-actions-auditor`, `supply-chain-risk-auditor`.
- **[angular/skills](https://github.com/angular/skills)** (1, MIT as declared in its `SKILL.md`): `angular-developer`.
- **[cloudflare/skills](https://github.com/cloudflare/skills)** (1, Apache-2.0): `cloudflare-one`.
- **[Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)** (1, MIT): `design-taste-frontend`.
- **[microsoft/playwright-cli](https://github.com/microsoft/playwright-cli)** (1, Apache-2.0): `playwright-cli`.
