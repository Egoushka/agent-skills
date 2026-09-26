# 0003: Reference corpora are a search service, not skill content

- Status: accepted
- Date: 2026-09-27

## Context

Repositories such as public-apis, system-design-primer, developer-roadmap, build-your-own-x and free-programming-books are useful day to day, but they are catalogs and curricula, not instructions. Together they come to about 90 MB, 41k links and 12k prose sections, and they change daily. Their licenses vary: developer-roadmap allows personal use only. The planned orchestrator needs every worker to see the same corpus.

| Option | Why not (or why) |
|---|---|
| Put them in skills | A description that matches everything and a body nobody can afford to load, plus redistribution of content whose license forbids it |
| Vector RAG | Needs an embedding model or API calls, a vector store and more RAM on a memory-constrained VPS. It is also fuzzy where the content is keyword-shaped (API names, headings, titles) |
| Hosted only (DeepWiki MCP) | No setup and broad coverage, but it is a third party, has no offline mode and answers with generated prose |
| Keyword index served over MCP | Deterministic, cheap and citable; the one weakness is the lack of synonyms |

## Decision

- `refs.py` (standard library only) shallow-clones the configured repositories, sparse where possible, parses Markdown into *link* and *section* records, and builds a SQLite FTS5 index with Porter stemming and BM25 ranking. It builds into a temporary file and swaps it in atomically, so readers never see a half-built index.
- `refs/server.py` exposes that index as a read-only MCP server (`search_refs`, `read_ref`, `list_ref_sources`) on the VPS, behind a bearer token and a Host allow-list. It re-syncs daily.
- The same engine runs locally as a CLI for offline use, and the `dev-references` skill falls back to it.
- DeepWiki MCP is the documented fallback for repositories outside the corpora.
- Only the configuration (`sources.json`) is public. Content is cloned where the index is built and never committed.

## Consequences

- Measured on the current corpora: the index builds in about 5 s from local clones (27 s including a fresh sync), is about 55 MB on disk, and the server uses about 70 MB RSS.
- Queries must use the domain's words. The skill teaches query craft, and `/stats` lists recent zero-result queries so that missing corpora or vocabulary gaps become visible. If that list shows many near misses, the upgrade path is a hybrid: embeddings added to the same records, keeping BM25 for exact terms.
- The endpoint must stay private (tailnet, or proxy plus token) because of developer-roadmap's license.
