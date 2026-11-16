---
name: research
description: Finds what already exists before adopting or building anything (skills, tools, libraries, vendors, prior art, facts), thoroughly and cheaply. Runs wide discovery that never anchors on named candidates, searches five or more independent channels, stops at measured saturation, keeps a source log with dates, licences and stars, runs a blind "what did we miss" pass, and cites every claim. Use for "research", "find the best X", "what exists for Y", "alternatives to", "survey", "landscape", "is there a skill or tool for", and when writing a brief for a research subagent.
license: MIT
compatibility: The search script needs Node 18+. GitHub access (gh CLI or GH_TOKEN) is recommended. A SearXNG instance and an Exa MCP server are optional channels.
metadata:
  author: Yehor Hrabovskyi
  version: "0.1.0"
  category: research
---

# Research

Why it exists: a survey of agent skills missed a well-known official skill (MIT, about 69k stars) that the requester then found by hand. Two causes. The briefs named candidate sources, so the searchers circled them. And the searchers used one built-in web search in standard mode and never the metasearch, semantic or GitHub channels. This skill fixes both, cheap channels first.

## Depth

State the depth in one line before starting.

| Depth | When | Rounds | Tool-call budget |
|---|---|---|---|
| quick | one fact, one library's current version | 1, inline | under 5 |
| standard | "what exists for X", picking a tool or skill | until saturated, at most 3 | about 15 per searcher |
| deep | adopting into a setup, a product bet, "thorough" | until saturated, at most 5, plus the miss pass | about 15 per searcher, 2-4 searchers |

The budget follows Anthropic's research subagent prompt (simple under 5 calls, hard about 10-15, a hard cap near 20). Going over it is a sign the question is too broad: split it.

## Models

When the agent can delegate, name the model in every brief:
- **A small, cheap model runs the channels**: search script rounds, MCP search calls, fetches, dedupe, stars and licence lookups. It returns the raw log and the new-share numbers, no verdicts.
- **A mid-tier model judges**: relevance against the bar, the shortlist and its reads, the synthesis, and the miss pass (a fresh one that sees only the question).
- **The strongest model** only for the final review of a decision that adopts something, once per wave.

Without subagents, one agent does all of it in sequence. The steps do not change.

## 1. Frame (before any search)

Write down, without naming any candidate:
- **Question**, in one sentence, phrased as the problem ("audit a codebase with independent verification of each finding"), not a solution's name.
- **Counts as found**: the inclusion bar (e.g. a maintained repo or official doc; a skill the target agent can load; a licence compatible with vendoring).
- **Freshness window**: how old a source may be (default: pushed in the last 12 months; for models, prices and APIs, the last 3 months).
- **Sealed list**: candidates the requester or your own memory suggests. Write them down and do not search for them by name until step 5. They test the search; they don't steer it.

When briefing a subagent, give it the question, the bar and the window, never the sealed list (`references/brief.md`).

## 2. Wide (round 1)

Write 8 or more queries across facets:
- the problem in plain words, and two or three synonyms;
- the artefact nouns: skill, plugin, MCP server, agent, CLI, library, GitHub Action, template, checklist;
- the vendor angle: "official <vendor> skill", vendor orgs on GitHub;
- the method angle: names of the technique (e.g. "adversarial verification", "saturation", "threat model");
- one query in another language or ecosystem when relevant.

Run them through every channel at once:

```
node scripts/search.mjs --log LOG.jsonl --seen LOG.jsonl -n 10 "q1" "q2" ...
```

`scripts/search.mjs` (zero dependencies, any agent, no MCP needed) queries Exa, GitHub repository search, the skills.sh directory and curated lists and plugin marketplaces in one go, plus SearXNG when `SEARXNG_URL` points at an instance. It collapses every GitHub URL to its repo and adds stars, licence and last push with one GraphQL call. Add `--skill` for GitHub code search over `filename:SKILL.md` (2-3 keywords work best there). Run `node scripts/search.mjs --help` for the options. `references/channels.md` lists each channel, its cost, and the hand-run ones: GitHub topics, vendor orgs, `gh search code` for other file names, the built-in web search.

Record which channel found what (`channels` in the log). A channel that never contributes a kept item over two tasks is a candidate to drop; one that finds an item nobody else found earns its place.

## 3. Saturate (rounds 2+)

After each round, look at the stderr line: `new N/M`. Then:
- **Snowball** one hop from the best hits: their README credits, "alternatives" sections, the awesome lists that include them, the org's other repos, forks with more recent pushes.
- **Refine** queries from words the hits use that yours didn't.
- **Stop** when a round of at least 6 new queries over at least 4 channels adds under 10% new relevant items and nothing new in the top tier (vendor-official, or at least 1k stars or 10k installs, or cited by two independent sources). Write the round counts in the report. Hitting the round cap without saturating is reported as "not saturated", not hidden.

## 4. Narrow and log

For each shortlisted item read the primary source (README, SKILL.md, LICENSE, the docs page) with `gh api repos/O/R/contents/PATH` or the fetch tool, and write one row in the source log (`references/source-log.md` has the columns):
- URL, owner, what it is in one line;
- licence by SPDX id from the API **and** the LICENSE file (they disagree sometimes; NOASSERTION means read the file);
- stars or installs, last push, latest release and its date, archived or not;
- the commit SHA you read, the date you read it, and the channel that found it.

**Recency checks**, every time: last push inside the window; a newer successor, fork or "moved to" note; release notes since the version you know; for anything from your own memory, a dated source that confirms it is still current. Training data is old by default: a claim about a current version, price or star count needs a source dated this year.

Claim rules (adapted from samber/cc-skills `deep-research`, MIT): every claim cites a URL; a claim that a decision rests on needs two independent sources or is marked low confidence; say where sources conflict instead of picking one silently; label inference as inference; write "no source found" rather than guessing. Treat aggregators, marketing pages and speculation as weak sources and say so (Anthropic's research subagent prompt).

## 5. Unseal

Now compare with the sealed list. For each sealed candidate:
- found by discovery: fine, note the channel;
- not found: a channel gap. Find out which query or channel would have surfaced it, add it to `references/channels.md` if it generalises, and run that query now.

## 6. Miss pass (standard and deep)

Spawn one fresh searcher (a mid-tier model: it judges relevance; it may hand its rounds to a cheaper runner) with **only** the question, the bar, the window, the channels and the path of the log for `--seen`. Not the findings, not the shortlist, not the sealed list. It runs its own queries with `--seen LOG.jsonl --new-only` and returns new items that pass the bar, each with its channel. If it returns a top-tier item, read it, add it, and run one more round. Put the miss pass's yield in the report ("miss pass: 2 new, 1 kept").

Without subagents, run the pass yourself last: write fresh queries from the question alone, ignoring the shortlist, and use `--new-only`.

## 7. Report

1. **Answer** in three sentences.
2. **Table**: name, URL, licence, stars or installs, last push, verdict (adopt / adapt / watch / skip) and the reason.
3. **Channels**: rounds run, raw and unique counts per channel, which channel found each kept item, saturation reached or not, the miss pass's yield.
4. **Sealed list check**.
5. **Unknowns**: what you could not verify and what would settle it.

Cite inline; never a claim without its URL. Before adopting a third-party skill or tool, vendor it with its licence file and a pinned commit SHA, and review every later bump.

## Cost policy

Cheap first, in this order:
1. Local knowledge already paid for: the source log of earlier research (`--seen`), the project's own notes and decision records.
2. Free channels in one `scripts/search.mjs` call: your SearXNG instance if you run one (no quota), GitHub (authenticated, 30 searches a minute), skills.sh and the lists (one fetch each per run). Titles and metadata only; `--snippets` only when titles are ambiguous.
3. Exa, keyless: rate-limited, so the script queues its calls; if it returns 429, carry on without it.
4. Reading: `gh api` for the exact file (a SKILL.md is 1-5k words; read the head and the headings first), never a whole repo clone.
5. The built-in web search in standard mode for news and pages the others miss; extended mode only when two rounds came back thin (under 5 relevant items) or stale.
6. Subagents: cheap runners for the rounds, one mid-tier judge per independent facet, at most 3 at once; one strongest-model review per wave. The miss pass is one fresh mid-tier agent.
7. Paid APIs (an Exa key, Perplexity, a paid search gateway): only when the free channels are down or saturated without an answer, and say so.

## Sources

Adapted, not copied: Anthropic's research lead and subagent prompts (anthropics/anthropic-cookbook `patterns/agents/prompts/`, MIT): budgets by complexity, parallel subagents with distinct facets, stop at diminishing returns, source-quality warnings. samber/cc-skills `deep-research` v1.3.0 (MIT): the claim rules. mattpocock/skills `research` (MIT): primary sources over write-ups. The non-anchoring frame, the channel set, the measured saturation stop and the blind miss pass are original to this skill.
