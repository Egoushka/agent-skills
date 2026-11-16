# Channels

Run them all in round 1; they fail differently. `search.mjs` covers rows 1–6 in one call. Note in the log which channel found each kept item.

| # | Channel | How | Cost and limits | Good at |
|---|---|---|---|---|
| 1 | SearXNG, a self-hosted metasearch (optional) | `search.mjs` (`searx`, when `SEARXNG_URL` is set), or a SearXNG MCP server; raw: `$SEARXNG_URL/search?q=Q&format=json&categories=it&pageno=2` | free, no quota; Brave inside it rate-limits, Google CSE and DuckDuckGo carry it | blogs, docs, GitHub pages by title, publish dates |
| 2 | Exa, hosted MCP, keyless | `search.mjs` (`exa`), or MCP `web_search_exa` / `web_fetch_exa`; raw: JSON-RPC `tools/call` to `https://mcp.exa.ai/mcp` with `accept: application/json, text/event-stream` | free with a burst limit (429); the script queues and retries once | semantic matches: describe the page you want, not keywords; deep files inside big repos |
| 3 | GitHub repository search | `search.mjs` (`gh`); `gh api 'search/repositories?q=Q&sort=stars'`; qualifiers `topic:`, `org:`, `pushed:>YYYY-MM-DD`, `stars:>100` | 30 a minute with GH_TOKEN | popular repos by description; topics `claude-skills`, `agent-skills`, `claude-code`, `claude-code-plugin`, `mcp-server` |
| 4 | skills.sh directory | `search.mjs` (`skills`); `https://skills.sh/api/search?q=Q` | free | skills by install count across vendors |
| 5 | Curated lists and marketplaces | `search.mjs` (`lists`), `RESEARCH_LISTS` overrides the set: awesome-claude-code, awesome-agent-skills, awesome-claude-skills, agentic-awesome-skills, awesome-copilot, the official and community plugin marketplaces | one fetch per list per run | curated, already filtered by someone |
| 6 | GitHub code search | `search.mjs --skill` (`ghcode`, adds `filename:SKILL.md`); `gh api 'search/code?q=KW+filename:SKILL.md'`; also `filename:marketplace.json`, `path:.claude/agents` | 10 a minute; needs a token; 2–3 keywords, not a sentence | skills buried in big monorepos that repo search ranks low |
| 7 | Vendor orgs | `gh api 'orgs/ORG/repos?sort=pushed&per_page=100' --jq '.[]\|[.name,.stargazers_count,.description]'`, then `search/code?q=org:ORG+filename:SKILL.md` | cheap | official skills: anthropics, cloudflare, vercel-labs, trailofbits, google, microsoft, openai, github, getsentry, stripe, supabase, firebase, hashicorp, aws-samples, elastic, grafana, and any vendor a hit belongs to |
| 8 | Built-in WebSearch | standard mode first; extended only when two rounds came back thin or stale | counts against the subscription | news, launches, pages the indexes above lag on |

Caveats seen in use:
- **SearXNG degrades under load.** With three parallel searchers, its upstreams were suspended (Brave "too many requests", Google CSE suspended) and DuckDuckGo answered with a CAPTCHA, so it returned near-empty pages while reporting success. Check `unresponsive_engines` in the JSON (a SearXNG MCP server may expose it as an instance-info tool), don't run more than one searcher's rounds through it at once, and when it is degraded let Exa and GitHub carry the round and say so in the report.
- **Exa's keyless tier returns 429 in bursts.** `search.mjs` queues its calls and retries once; a second 429 means skip it for that round.

Hand checks that caught misses before:
- **The org of every top hit.** cloudflare/security-audit-skill sits next to cloudflare/skills; an org sweep finds siblings repo search ranks low.
- **Stars and installs disagree.** A repo with few stars can carry a skill with 100k installs on skills.sh; read both.
- **Successors.** Archived or quiet repos often name a successor in the README; follow it.
