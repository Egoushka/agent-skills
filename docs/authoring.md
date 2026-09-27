# Authoring rules

These are the rules `tools/validate.py` enforces, or at least points at, and the reasoning behind each. They follow the [Agent Skills spec](https://agentskills.io/specification) and Anthropic's [authoring guidance](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

## Contents

1. The description is the router
2. Budget the body
3. Scripts for deterministic work
4. Match freedom to fragility
5. One default, not a menu
6. Evals before prose
7. Few sharp skills beat many overlapping ones
8. Third-party skills are dependencies
9. Keep private skills private
10. Small rules that save debugging

## 1. The description is the router

An agent reads every skill's `name` and `description` at startup and nothing else until a task matches. The description decides whether the skill is ever used. It works like a route template in ASP.NET Core, with one important difference: two ambiguous routes throw `AmbiguousMatchException`, while two ambiguous skills fail silently, because the agent just picks one.

- Say **what** the skill does and **when** to use it, in the third person, because the text is injected into the system prompt (W103, W104).
- Use the words users actually type, such as "public API", "roadmap" or "DESIGN.md", not internal names.
- Add a boundary when a neighbouring skill exists: `Not for official product documentation.`
- Stay under 1,024 characters, and avoid angle brackets and the reserved words `claude` and `anthropic`, which some clients reject (E003, E012, E013).

## 2. Budget the body

The body loads in full whenever the skill fires. Keep it under 500 lines and roughly 5,000 tokens (W101, W102). SKILL.md holds the decision procedure, the controller. Catalogs, API tables and long examples go in `references/`, the services it calls. Link references directly from SKILL.md, one level deep (W109), and give any file over 100 lines a contents list so a partial read still shows its scope (W107).

## 3. Scripts for deterministic work

The agent runs a script without reading it, so only the script's output enters the context. Parsing, indexing, validation and API calls belong in `scripts/`. Handle errors inside the script with messages the agent can act on, not tracebacks. Write "Run `scripts/x.py`" when the agent should execute it and "See `scripts/x.py`" when it should read it. Prefer the standard library: a skill has no dependency installer.

## 4. Match freedom to fragility

For judgment tasks such as reviews or design, give heuristics and let the agent choose. For fragile tasks such as migrations or releases, give an exact script with few parameters. Most skills mix both: exact steps where a mistake is expensive, guidance everywhere else.

## 5. One default, not a menu

Five equally weighted options produce five different behaviours. State the default path and keep escape hatches for the cases that need them. `dev-references`, for example, names one backend order: MCP server, then local CLI, then DeepWiki.

## 6. Evals before prose

Write three or more realistic prompts before polishing the text, including prompts that must **not** trigger the skill. Run them once without the skill for a baseline, then with it. Keep the cases in `evals/<skill>.json` next to the expected behaviour. Anthropic's `skill-creator` skill can run the loop and tune descriptions. Evals call a model and cost money, so they run on demand, never in CI.

## 7. Few sharp skills beat many overlapping ones

Each installed skill adds its description to every session, and overlapping descriptions compete for the same requests. `validate.py` warns when two descriptions share too many content words (W112). For example, taste-skill ships thirteen skills that mostly share one trigger vocabulary; this repository vendors only its default.

## 8. Third-party skills are dependencies

Treat a skill from someone else like a NuGet package that can also rewrite your agent's instructions: pin it, verify it and review every bump. `vendor.json` pins a commit, `vendor.py verify` proves the copy is untouched, and the weekly PR report calls out changes to `allowed-tools`, scripts, URLs and descriptions. First-party and community skills go through the same review; only plugins that carry more than skills (hooks, a language server, sub-agents, commands) install from their publishers, and `publishers.json` lists them.

## 9. Keep private skills private

Anything under `skills/` is public and installable by anyone. Employer-specific workflows, internal hostnames, log queries and customer terms belong in a private repository that uses the same tooling. `validate.py` scans for common token formats (E009), but it cannot recognise an internal hostname.

## 10. Small rules that save debugging

- Refer to MCP tools by fully qualified name (`refs:search_refs`), or the agent may not find them when several servers are connected.
- Use forward slashes in paths (W108).
- Don't write dates or "new in version X" into instructions. They go stale while the skill keeps sounding confident.
- Bump `metadata.version` when behaviour changes, and write conventional commit messages so the activity feed on the catalog site reads as a changelog.
