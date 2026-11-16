# Brief for a research subagent

Copy and fill. Never add candidate names, "for example X" or "start with Y": that is what anchored the survey this skill grew from. Keep the sealed list to yourself and check it in step 5.

```
Research question: <the problem, one sentence, no product names>
Counts as found: <inclusion bar: kind of artefact, maintained, licence, client>
Freshness window: <e.g. pushed since 2025-11>
Depth: <standard | deep>; budget about 15 tool calls.

Follow the research skill, steps 2-4 and 7.
Channels: node <skill dir>/scripts/search.mjs --log <LOG> --seen <LOG> -n 10 "q1" ... (all channels),
plus --skill for code search, the org of every top hit, and any search MCP tools (web_search_exa, a SearXNG server) when the
script is not enough. Built-in web search standard first, extended only if thin.
Write 8+ queries of your own across facets (problem words, synonyms, artefact nouns, vendor, method).
Stop at saturation: a round of 6+ new queries over 4+ channels adds under 10% new relevant items and no top-tier item.

Return, under 400 words: a table (name, URL, licence, stars/installs, last push, one line on what it is, which channel found it),
round counts per channel, saturated or not, and what you could not verify. No prose recap of pages.
```

The miss-pass searcher gets the same brief plus `--new-only`, and nothing about the findings.
