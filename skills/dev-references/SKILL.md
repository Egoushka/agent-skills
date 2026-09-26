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

# Dev references

Answer from the curated corpora first, cite a URL for every resource, and keep context small: search, then read only the one or two hits that matter.

## Pick a backend (first one available)

1. **refs MCP server**, the shared index on the VPS: `refs:search_refs`, `refs:read_ref`, `refs:list_ref_sources`.
2. **Local CLI**, when there is no server: `python3 scripts/refs.py search "<words>" [--source NAME] [--kind link|section]`, then `python3 scripts/refs.py show <id>`. If it reports that no index exists, ask the user before running `python3 scripts/refs.py update` (a one-time download of about 90 MB).
3. **DeepWiki MCP** (`deepwiki:ask_question`) for public repositories outside the corpora, or for "how does X work inside repo Y". Its answers are generated: check them against the files it cites.

For official product documentation use that vendor's docs tools (for .NET and Azure, Microsoft Learn), not this skill.

## Route the question

| Question | `source` | `kind` |
|---|---|---|
| External API for a feature or demo | public-apis | link |
| System design concept, trade-off, worked design | system-design-primer | section |
| Topic explainer or what to learn next (aspnet-core, backend, system-design, postgresql-dba, redis, angular, devops...) | developer-roadmap | section |
| Implement X from scratch | build-your-own-x,project-based-learning | link |
| Free book, course or screencast (file suffix is the language: -uk, -ru, -langs) | free-programming-books | link |
| Interview prep, CS fundamentals | coding-interview-university | section |
| Libraries for a technology | awesome,awesome-python | link |
| Visual system for a UI | awesome-design-md | section |
| Beginner curriculum or exercise ideas | freecodecamp | section |

When unsure, omit `source`; `list_ref_sources` describes every corpus.

## Search well

- Use 2 to 4 content words: `rate limiter`, `consistent hashing`, `currency exchange`. Words are stemmed but there are no synonyms, so if nothing matches, retry with the domain term (for example `message broker` instead of `queue thing`).
- Narrow with `source` and `kind` before raising `limit`.
- Read a hit only when its title or snippet looks like the answer. `read_ref` returns a section together with its subsections.

## Answer

- Lead with the answer, then at most 5 resources as `[title](url) — why it fits`, naming the corpus each came from.
- Link lists go stale. For anything load-bearing (API auth, pricing, whether a project is maintained), open the linked page before recommending it.
- developer-roadmap text is licensed for personal use only: summarize it and link to it, and never paste it into public repositories, posts or docs.
- To adopt a DESIGN.md, read it with `max_chars` 60000 (or fetch its `raw_url`) and save it as `DESIGN.md` in the project root.
- If nothing relevant turns up, say so and name the queries you tried. Don't fill the gap from memory as if it were cited.
