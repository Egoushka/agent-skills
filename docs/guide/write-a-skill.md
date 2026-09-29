---
title: "Write a skill"
description: "Add a skill under skills/: frontmatter the linter accepts, a body within budget, trigger cases, a regenerated catalog and a pull request."
order: 3
section: "Guides"
---

[docs/authoring.md](../authoring.md) holds the ten authoring rules and the reasons behind them, and [validate.py](../../tools/validate.py) enforces most of them. This page is the procedure, with the finding code each step can raise. [Reference](reference.md#finding-codes) lists every code.

## Before you write

- **It must earn its context.** Every installed skill adds its description to every session, and overlapping descriptions compete for the same requests ([rule 7](../authoring.md#7-few-sharp-skills-beat-many-overlapping-ones)). [CONTRIBUTING.md](../../CONTRIBUTING.md) asks this of every new skill.
- **It must be fit to publish.** Anyone can install anything under `skills/`. Employer-specific workflows, internal hostnames, log queries and customer terms belong in a private repository ([rule 9](../authoring.md#9-keep-private-skills-private)). The linter scans for common token formats (E009), but it cannot recognise an internal hostname.
- **Write the trigger cases first** ([rule 6](../authoring.md#6-evals-before-prose)). See [Add trigger cases](#add-trigger-cases).

## Create the folder

```text
skills/<name>/
  SKILL.md       the decision procedure; loads in full when the skill fires
  references/    catalogs, API tables, long examples; read when SKILL.md points at them
  scripts/       parsing, indexing, API calls; the agent runs them without reading them
```

The directory's name is the skill's `name`. A skill needs only `SKILL.md`; `dev-references` also keeps a data file under `assets/`.

## Write the frontmatter

`dev-references`, the one own skill, passes the linter with no findings:

```markdown title="skills/dev-references/SKILL.md"
---
name: dev-references
description: Searches curated developer reference corpora (public-apis, system-design-primer, developer-roadmap topics including ASP.NET Core and backend, build-your-own-x, free-programming-books, coding-interview-university, awesome lists, awesome-design-md, the freeCodeCamp outline) and answers with cited links or sections. Use when the user wants a public API for a feature, a system-design concept with sources, a learning path or roadmap topic, a from-scratch tutorial, a free book or course, interview prep, or a DESIGN.md for a UI. Not for official product documentation.
license: MIT
compatibility: Best with the refs MCP server; otherwise needs python3 and git for a local index. DeepWiki MCP is optional.
metadata:
  author: Egoushka
  version: "0.1.0"
  category: research
---
```

It says what the skill does in the third person, when to use it in the words users type, and where its boundary lies: `Not for official product documentation.` ([rule 1](../authoring.md#1-the-description-is-the-router)). The linter checks each field:

| Field | Rule | Code |
|---|---|---|
| `name` | required; a-z, 0-9, single hyphens; matches the directory | E002 |
| `name` | no `claude` or `anthropic` in it | E013 |
| `description` | required; at most 1,024 characters | E003 |
| `description` | no `<` or `>` | E012 |
| `description` | written in the third person | W103 |
| `description` | says when to use the skill | W104 |
| `license` | optional | |
| `compatibility` | optional; 1 to 500 characters | E004 |
| `metadata` | optional; strings to strings, so quote `"0.1.0"` | E005 |
| `allowed-tools` | optional; one space-separated string | E006 |
| `allowed-tools` | no broad grant such as `Bash` or `Bash(npx:*)` | W110 |
| any other field | allowed, but outside the spec | W111 |

A `name` is at most 64 characters. W104 passes when the description contains "use when", "use it when", "use this when", "when the user", "use for" or "use to". W103 flags "I can", "I will", "I'll", "I help", "you can", "you should" and "you'll".

> [!NOTE]
> Rule 1 also asks you to keep `claude` and `anthropic` out of the description. validate.py checks only the `name` for them, so a description with either word passes.

## Write the body

- Keep `SKILL.md` under 500 lines (W101) and about 5,000 tokens (W102). It loads in full every time the skill fires ([rule 2](../authoring.md#2-budget-the-body)).
- Move catalogs, API tables and long examples to `references/`, linked straight from `SKILL.md`. A reference that links further `.md` files raises W109, and one over 100 lines without a contents heading raises W107.
- Every relative link in the body of `SKILL.md` must point at a file that exists, counted from the skill's folder (E008). The check skips links inside code, and drops the `{baseDir}/` prefix, Claude Code's placeholder for that folder.
- Use forward slashes in file paths (W108).
- Put deterministic work in `scripts/`, using the standard library, with errors the agent can act on. Write "Run `scripts/x.py`" when the agent should execute a script and "See `scripts/x.py`" when it should read it ([rule 3](../authoring.md#3-scripts-for-deterministic-work)).
- Give MCP tools their full name, such as `refs:search_refs`, and leave dates and "new in version X" out of instructions ([rule 10](../authoring.md#10-small-rules-that-save-debugging)).

## Add trigger cases

Put them in `evals/<name>.json`, in the shape of [evals/dev-references.json](../../evals/dev-references.json):

```json title="evals/<name>.json"
{
  "skill": "<name>",
  "should_trigger": [
    { "query": "A prompt a user would type", "expected_behavior": ["What the agent should do"] }
  ],
  "should_not_trigger": ["A prompt that must not fire the skill"]
}
```

Write three or more realistic prompts, including some that must not fire the skill. Run them once without the skill for a baseline, then with it ([rule 6](../authoring.md#6-evals-before-prose)).

> [!NOTE]
> Nothing in this repository runs the cases. They call a model, so they run on demand and never in CI. Rule 6 points at Anthropic's `skill-creator` skill for the loop.

## Check, regenerate, commit

The tools need PyYAML, pinned in [requirements-dev.txt](../../requirements-dev.txt):

```bash
pip install -r requirements-dev.txt
make catalog check
```

`make catalog` rewrites the README block between `<!-- catalog:start -->` and `<!-- catalog:end -->`, which now has a row for your skill. `make check` then runs `validate.py --strict`, the unit tests and `catalog.py --check`. In strict mode an own skill fails on any warning as well as on errors.

> [!WARNING]
> Run `make catalog` before `make check`. The README and CONTRIBUTING.md give the order `make check catalog`, but `check` includes the catalog drift check: with a new skill it fails on the stale catalog, and make stops before `catalog` runs.

> [!TIP]
> `make` runs `python3` unless you set `PY`, for example `make catalog check PY=.venv/bin/python`.

Commit the skill, its eval file and the regenerated README together. Write conventional commit messages such as `feat(skill): …` ([CONTRIBUTING.md](../../CONTRIBUTING.md)): the catalog site shows the last 15 commit subjects as its activity feed ([catalog.py](../../tools/catalog.py)). Bump `metadata.version` when the skill's behaviour changes ([rule 10](../authoring.md#10-small-rules-that-save-debugging)).

The [pull request template](../../.github/pull_request_template.md) asks you to confirm four things: `make check` passes, you regenerated the catalog, the description says what and when with trigger cases in `evals/`, and the skill holds no hostnames, tokens or employer-specific details.
