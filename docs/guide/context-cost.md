---
title: "Context cost"
description: "What the Always loaded and On activation numbers on every skill measure, how the catalog estimates them, and what they leave out."
order: 5
section: "Concepts"
---

Every skill in the catalog carries two token numbers. This page says where they come from, so you can weigh a skill before you install it.

## How an agent loads a skill

An agent loads a skill in three steps, and only the first costs something in every session. The catalog site describes the steps ([tools/site/index.html](../../tools/site/index.html)), and the authoring rules give the reasons:

1. **Always:** the name and description of every installed skill. They are the router: the agent picks a skill by reading them ([rule 1](../authoring.md#1-the-description-is-the-router)).
2. **On match:** the body of `SKILL.md`, in full, when a task matches the description ([rule 2](../authoring.md#2-budget-the-body)).
3. **On demand:** files under `references/` and `scripts/`, only when the body points at them. The agent runs a script without reading it, so only its output enters the context ([rule 3](../authoring.md#3-scripts-for-deterministic-work)).

## The two numbers

| Catalog column | Field in `catalog.json` | What it counts |
|---|---|---|
| Always loaded | `metadata_tokens` | the text `name: description` |
| On activation | `body_tokens` | `SKILL.md` after its frontmatter |

Both come from one estimate in [common.py](../../tools/common.py), characters divided by 4 and rounded up:

```python title="tools/common.py"
def estimate_tokens(text: str) -> int:
    """Rough token count (characters / 4). Good enough to compare skills, not to bill."""
    return (len(text) + 3) // 4
```

The README's footer adds up the Always loaded column: all 36 skills together come to about 3.7k tokens in every session. The catalog site also shows the median body, about 2.6k tokens, and the largest.

## Reading them

- **You pay Always loaded for every installed skill, used or not.** The catalog runs from `grill-me` at ≈16 to `migrate-dotnet9-to-dotnet10` at ≈262. Installing only the skills you use, one at a time with `-s`, keeps the sum down.
- **You pay On activation only when the skill fires.** `dev-references` costs ≈146 in every session and ≈740 more when it fires.
- **Neither is a bill.** Use the numbers to compare skills with each other; `common.py` calls its estimate good enough for that and not for billing.

## The 5,000-token guideline

A body over 5,000 tokens gets ⚠ in the README and a warning-coloured bar on the site (`GUIDE_TOKENS` in [catalog.py](../../tools/catalog.py)). The linter raises W102 for it, and W101 for a body over 500 lines ([validate.py](../../tools/validate.py)). In an own skill either one fails `make check`, which runs the linter in strict mode. In a vendored skill they are notes, because upstream owns its practices.

Seven bodies are over the guideline, all of them vendored, per the README catalog:

| Skill | On activation |
|---|--:|
| `design-taste-frontend` | ≈21.7k |
| `migrate-nullable-references` | ≈8.8k |
| `subagent-driven-development` | ≈8.1k |
| `dotnet-trace-collect` | ≈6.0k |
| `cloudflare-one` | ≈5.7k |
| `dotnet-webapi` | ≈5.3k |
| `agentic-actions-auditor` | ≈5.3k |

## Overlapping descriptions

Two skills whose descriptions share many words compete for the same requests, and the agent picks one without saying so ([rule 1](../authoring.md#1-the-description-is-the-router), [rule 7](../authoring.md#7-few-sharp-skills-beat-many-overlapping-ones)). W112 measures it. It takes the content words of each description, lower-case words longer than two letters outside a short stop list, and divides the words both share by the words either has. At 0.35 or more, validate.py warns on both skills. No pair reaches it at this commit: `python3 tools/validate.py` prints no W112.

## What the numbers leave out

- **References and scripts.** The site counts the files under `references/` and `scripts/` for the third step, but gives them no tokens.
- **The rest of the frontmatter**, and any text an agent wraps around its list of skills. Always loaded counts `name: description` and nothing else.
- **Plugins from publishers.** The catalog lists them without numbers, and a plugin can add context of its own. The SessionStart hook the hub left out of superpowers injects about 800 tokens into every session ([ADR 0002](../adr/0002-vendor-and-pin-community-skills.md)).

## When a number changes

Every upstream bump shows in the weekly review report: each changed `SKILL.md` gets its old and new line count and its change in tokens on activation (`review` in [vendor.py](../../tools/vendor.py)). A bump that grows a body shows before anyone merges it. [Vendor an upstream skill](vendor-a-skill.md#review-the-weekly-update) describes the report.
