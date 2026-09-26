#!/usr/bin/env python3
"""refs: a keyword index over developer reference repositories.

Shallow-clones curated GitHub repositories (link catalogs such as public-apis,
prose such as system-design-primer), parses their Markdown into records and
serves ranked search from a single SQLite FTS5 file.

Record kinds
  link     one external resource taken from a list item or a table row
  section  one heading-delimited chunk of prose, or a whole document

Commands
  refs.py update                  sync every enabled source, then rebuild the index
  refs.py sync [NAME ...]         clone or refresh sources (shallow, sparse where configured)
  refs.py build                   rebuild the index from what is on disk
  refs.py search QUERY [options]  ranked search (--source, --kind, --limit, --json)
  refs.py show ID [--max-chars N] full text of a section or document, or a link's details
  refs.py sources [--json]        what is indexed, from which commit, under which license

Environment
  REFS_HOME     data directory (default: ~/.local/share/dev-refs)
  REFS_SOURCES  sources file (default: ../assets/sources.json next to this script)

Standard library only. Python 3.9+, git 2.25+.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

__version__ = "0.1.0"

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCES = SCRIPT_DIR.parent / "assets" / "sources.json"
DB_NAME = "refs.db"
STATE_NAME = "state.json"
SCHEMA_VERSION = "1"

# Section bodies are stored for ranking only; `show` re-reads the file, so a cap
# keeps the database small without truncating what the agent eventually reads.
MAX_INDEXED_BODY = 4000
SNIPPET_TOKENS = 18

STOPWORDS = frozenset(
    "a an and are as at be by can do does for from how i in is it me my of on or "
    "please show tell that the this to use using what when where which with".split()
)

HEADING = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
LINK = re.compile(r"(?<!!)\[((?:[^\[\]]|\[[^\]]*\])+)\]\((https?://[^)\s]+)(?:\s+\"[^\"]*\")?\)")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
RESOURCE_TYPE = re.compile(r"^@(\w+)@\s*")
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


class RefsError(RuntimeError):
    """A user-facing failure: printed without a traceback."""


# --------------------------------------------------------------------------- config


def data_home() -> Path:
    return Path(os.environ.get("REFS_HOME") or Path.home() / ".local" / "share" / "dev-refs")


def sources_file() -> Path:
    return Path(os.environ.get("REFS_SOURCES") or DEFAULT_SOURCES)


def load_sources(names: list[str] | None = None) -> list[dict]:
    path = sources_file()
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RefsError(f"sources file not found: {path}") from None
    sources = [s for s in config["sources"] if s.get("enabled", True)]
    if names:
        known = {s["name"] for s in config["sources"]}
        unknown = sorted(set(names) - known)
        if unknown:
            raise RefsError(f"unknown source(s): {', '.join(unknown)}; known: {', '.join(sorted(known))}")
        sources = [s for s in config["sources"] if s["name"] in names]
    return sources


def read_state(root: Path) -> dict:
    try:
        return json.loads((root / STATE_NAME).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_state(root: Path, state: dict) -> None:
    tmp = root / (STATE_NAME + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, root / STATE_NAME)


# --------------------------------------------------------------------------- sync


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RefsError(f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def sync_source(source: dict, root: Path) -> str:
    """Clone or refresh one source at the tip of its default branch; return the commit."""
    dest = root / "repos" / source["name"]
    url = source.get("url") or f"https://github.com/{source['repo']}.git"
    sparse = source.get("sparse") or []
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        args = ["clone", "--quiet", "--depth", "1", "--filter=blob:none"]
        if sparse:
            args.append("--sparse")
        git(*args, url, str(dest))
        if sparse:
            git("sparse-checkout", "set", *sparse, cwd=dest)
    else:
        if sparse:
            git("sparse-checkout", "set", *sparse, cwd=dest)
        git("fetch", "--quiet", "--depth", "1", "origin", "HEAD", cwd=dest)
        git("reset", "--quiet", "--hard", "FETCH_HEAD", cwd=dest)
    return git("rev-parse", "HEAD", cwd=dest)


def sync(names: list[str] | None = None, log=print) -> dict:
    root = data_home()
    root.mkdir(parents=True, exist_ok=True)
    state = read_state(root)
    failures = {}
    for source in load_sources(names):
        started = time.time()
        try:
            rev = sync_source(source, root)
        except RefsError as exc:
            failures[source["name"]] = str(exc)
            log(f"  ✗ {source['name']}: {exc}")
            continue
        state[source["name"]] = {"rev": rev, "synced_at": int(time.time())}
        log(f"  ✓ {source['name']:<28} {rev[:10]}  {time.time() - started:5.1f}s")
    write_state(root, state)
    return failures


# --------------------------------------------------------------------------- markdown parsing


def strip_markdown(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[((?:[^\[\]]|\[[^\]]*\])*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(\*\*|__|`)", "", text)
    text = re.sub(r"(?<![\w*])[*_](?=\S)(.+?)(?<=\S)[*_](?![\w*])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify(heading: str, seen: dict[str, int]) -> str:
    """GitHub-style heading anchor, deduplicated the way GitHub does it (-1, -2, …)."""
    slug = strip_markdown(heading).lower()
    slug = re.sub(r"[^\w\- ]", "", slug).replace(" ", "-")
    count = seen.get(slug, 0)
    seen[slug] = count + 1
    return slug if count == 0 else f"{slug}-{count}"


def split_row(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip())
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text
    meta = {}
    for line in match.group(1).splitlines():
        found = re.match(r"^(name|title|description):\s*(.+)$", line)
        if found:
            meta[found.group(1)] = found.group(2).strip().strip("'\"")
    return meta, text[match.end():]


def link_record(title_md: str, url: str, rest: str, *, line: int) -> dict:
    rtype = ""
    found = RESOURCE_TYPE.match(title_md)
    if found:  # developer-roadmap marks resources as [@article@Title](url)
        rtype, title_md = found.group(1), title_md[found.end():]
    title = strip_markdown(title_md)
    description = strip_markdown(re.sub(r"^\s*[-–—:|,]\s*", "", rest))
    return {"kind": "link", "title": title, "url": url, "body": description, "rtype": rtype, "line": line}


def parse_markdown(text: str, *, sections: bool, whole_doc: bool, context: str = "") -> list[dict]:
    """Turn one Markdown file into link and section records."""
    meta, body_text = parse_frontmatter(text)
    offset = text[: len(text) - len(body_text)].count("\n")
    lines = body_text.splitlines()
    records: list[dict] = []
    stack: list[tuple[int, str]] = []
    seen: dict[str, int] = {}
    in_fence = False
    table_header: list[str] = []
    chunk = {"title": "", "anchor": "", "context": context, "lines": [], "line": offset + 1}

    def crumb() -> str:
        parts = [context] if context else []
        return " › ".join(parts + [t for _, t in stack[:-1]])

    def close_chunk() -> None:
        body = "\n".join(chunk["lines"]).strip()
        if sections and (chunk["title"] or body):
            records.append({
                "kind": "section",
                "title": chunk["title"] or meta.get("name") or meta.get("title") or "",
                "anchor": chunk["anchor"],
                "context": chunk["context"],
                "body": strip_markdown(body)[:MAX_INDEXED_BODY],
                "line": chunk["line"],
            })

    for index, line in enumerate(lines):
        lineno = offset + index + 1
        if FENCE.match(line):
            in_fence = not in_fence
            chunk["lines"].append(line)
            continue
        if in_fence:
            chunk["lines"].append(line)
            continue
        heading = HEADING.match(line)
        if heading:
            close_chunk()
            level, title = len(heading.group(1)), strip_markdown(heading.group(2))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            anchor = slugify(heading.group(2), seen)
            chunk = {"title": title, "anchor": anchor, "context": crumb(), "lines": [], "line": lineno}
            table_header = []
            continue
        chunk["lines"].append(line)
        if TABLE_SEP.match(line):
            # The header is the row above the separator; some tables omit its leading pipe.
            if index and "|" in lines[index - 1]:
                table_header = [strip_markdown(c) for c in split_row(lines[index - 1])]
            continue
        if TABLE_ROW.match(line):
            cells = split_row(line)
            found = next((LINK.search(c) for c in cells if LINK.search(c)), None)
            if not found:
                table_header = [strip_markdown(c) for c in cells]
                continue
            if found.group(1).lstrip().startswith("!["):
                continue
            rest = []
            for i, cell in enumerate(cells):
                if LINK.search(cell) and LINK.search(cell).group(0) == found.group(0):
                    continue
                label = table_header[i] if i < len(table_header) else ""
                value = strip_markdown(cell)
                if value:
                    rest.append(value if not label or label.lower() == "description" else f"{label}: {value}")
            record = link_record(found.group(1), found.group(2), " · ".join(rest), line=lineno)
            record["context"] = " › ".join(p for p in [crumb(), chunk["title"]] if p)
            records.append(record)
            continue
        if LIST_ITEM.match(line):
            found = LINK.search(line)
            if not found or found.group(1).lstrip().startswith("!["):
                continue
            record = link_record(found.group(1), found.group(2), line[found.end():], line=lineno)
            record["context"] = " › ".join(p for p in [crumb(), chunk["title"]] if p)
            records.append(record)
    close_chunk()

    if whole_doc:
        first_heading = next((t for _, t in stack[:1]), "")
        title = meta.get("name") or meta.get("title") or first_heading
        summary = meta.get("description", "")
        records = [r for r in records if r["kind"] == "link"]
        records.insert(0, {
            "kind": "section",
            "title": title,
            "anchor": "",
            "context": context,
            "body": (summary + "\n" + strip_markdown(body_text))[:MAX_INDEXED_BODY],
            "line": 1,
        })
    return records


def parse_fcc_block(text: str, *, context: str = "") -> list[dict]:
    """freeCodeCamp curriculum/structure/blocks/*.json → one record per block."""
    block = json.loads(text)
    name = block.get("dashedName", "")
    titles = [c.get("title", "") for c in block.get("challengeOrder", [])]
    label = " · ".join(x for x in [block.get("blockLabel"), block.get("helpCategory")] if x)
    return [{
        "kind": "section",
        "title": name.replace("-", " ").title(),
        "anchor": "",
        "context": " › ".join(x for x in [context, label] if x),
        "body": "; ".join(titles)[:MAX_INDEXED_BODY],
        "line": 1,
        "block": name,
    }]


def path_context(source: dict, rel: str) -> str:
    pattern = source.get("context")
    if not pattern:
        return ""
    found = re.search(pattern, rel)
    return found.group("ctx").replace("-", " ") if found else ""


def iter_files(repo: Path, source: dict):
    excluded = source.get("exclude", [])
    seen = set()
    for pattern in source.get("include", ["README.md"]):
        for path in sorted(repo.glob(pattern)):
            rel = path.relative_to(repo).as_posix()
            if path.is_file() and rel not in seen and not any(Path(rel).match(e) for e in excluded):
                seen.add(rel)
                yield path, rel


# --------------------------------------------------------------------------- index

SCHEMA = f"""
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE sources(
  name TEXT PRIMARY KEY, repo TEXT, rev TEXT, synced_at INTEGER,
  license TEXT, about TEXT, use_for TEXT, links INTEGER, sections INTEGER
);
CREATE TABLE docs(
  rowid INTEGER PRIMARY KEY,
  id TEXT UNIQUE NOT NULL,
  source TEXT NOT NULL, kind TEXT NOT NULL,
  title TEXT, url TEXT, origin TEXT, context TEXT,
  path TEXT, anchor TEXT, line INTEGER, rtype TEXT, body TEXT
);
CREATE INDEX docs_source ON docs(source, kind);
CREATE VIRTUAL TABLE docs_fts USING fts5(
  title, context, body, content='docs', content_rowid='rowid',
  tokenize='porter unicode61 remove_diacritics 2'
);
INSERT INTO meta VALUES ('schema_version', '{SCHEMA_VERSION}');
"""


def blob_url(source: dict, rev: str, rel: str) -> str:
    base = source.get("web") or f"https://github.com/{source['repo']}"
    return f"{base}/blob/{rev}/{rel}"


def build(log=print) -> dict:
    """Parse every synced source into a fresh database, then swap it in atomically."""
    root = data_home()
    repos = root / "repos"
    state = read_state(root)
    tmp = root / (DB_NAME + ".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    totals = {}
    for source in load_sources():
        repo = repos / source["name"]
        if not repo.is_dir():
            log(f"  - {source['name']:<28} not synced, skipped")
            continue
        rev = state.get(source["name"], {}).get("rev", "HEAD")
        counts = {"link": 0, "section": 0}
        parser = source.get("parser", "markdown")
        for path, rel in iter_files(repo, source):
            text = path.read_text(encoding="utf-8", errors="replace")
            ctx = path_context(source, rel)
            if parser == "fcc-blocks":
                records = parse_fcc_block(text, context=ctx)
            else:
                records = parse_markdown(
                    text,
                    sections=source.get("sections", False) or source.get("whole_doc", False),
                    whole_doc=source.get("whole_doc", False),
                    context=ctx,
                )
            for rec in records:
                if rec["kind"] == "link":
                    key = f"{source['name']}:{rel}:L{rec['line']}"
                    url, origin = rec["url"], f"{blob_url(source, rev, rel)}#L{rec['line']}"
                else:
                    key = f"{source['name']}:{rel}#{rec['anchor']}" if rec["anchor"] else f"{source['name']}:{rel}"
                    origin = blob_url(source, rev, rel) + (f"#{rec['anchor']}" if rec["anchor"] else "")
                    url = origin
                    if rec.get("block"):
                        base = source.get("web") or f"https://github.com/{source['repo']}"
                        url = f"{base}/tree/{rev}/curriculum/challenges/english/blocks/{rec['block']}"
                cur = con.execute(
                    "INSERT OR IGNORE INTO docs(id, source, kind, title, url, origin, context, path, anchor, line, rtype, body)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (key, source["name"], rec["kind"], rec["title"], url, origin, rec.get("context", ""),
                     rel, rec.get("anchor", ""), rec["line"], rec.get("rtype", ""), rec["body"]),
                )
                if cur.rowcount:
                    con.execute(
                        "INSERT INTO docs_fts(rowid, title, context, body) VALUES (?,?,?,?)",
                        (cur.lastrowid, rec["title"], rec.get("context", ""), rec["body"]),
                    )
                    counts[rec["kind"]] += 1
        con.execute(
            "INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?)",
            (source["name"], source.get("repo", ""), rev, state.get(source["name"], {}).get("synced_at"),
             source.get("license", ""), source.get("about", ""), source.get("use_for", ""),
             counts["link"], counts["section"]),
        )
        totals[source["name"]] = counts
        log(f"  ✓ {source['name']:<28} {counts['link']:>6} links {counts['section']:>6} sections")
    con.execute("INSERT INTO docs_fts(docs_fts) VALUES ('optimize')")
    con.execute("INSERT INTO meta VALUES ('built_at', ?)", (str(int(time.time())),))
    con.commit()
    con.close()
    os.replace(tmp, root / DB_NAME)  # readers never observe a half-built index
    return totals


def connect() -> sqlite3.Connection:
    path = data_home() / DB_NAME
    if not path.exists():
        raise RefsError(
            f"no index at {path}. Run `python3 {Path(__file__).resolve()} update` once "
            "(clones the configured repositories, roughly 90 MB)."
        )
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def fts_queries(query: str) -> tuple[str, str]:
    terms = re.findall(r"\w+", query.lower())
    kept = [t for t in terms if t not in STOPWORDS] or terms
    if not kept:
        raise RefsError("query has no searchable words")
    quoted = [f'"{t}"' for t in kept]
    if len(kept[-1]) >= 3:
        quoted[-1] += "*"  # prefix-match the last word: "kube" finds kubernetes
    return " ".join(quoted), " OR ".join(quoted)


def search(query: str, source: str | None = None, kind: str | None = None, limit: int = 8) -> list[dict]:
    if kind not in (None, "", "link", "section"):
        raise RefsError("kind must be 'link' or 'section'")
    limit = max(1, min(int(limit), 50))
    strict, loose = fts_queries(query)
    sql = (
        "SELECT d.id, d.source, d.kind, d.title, d.url, d.origin, d.context, d.rtype, d.body,"
        f" snippet(docs_fts, 2, '«', '»', '…', {SNIPPET_TOKENS}) AS snip,"
        " bm25(docs_fts, 6.0, 2.0, 1.0) AS score"
        " FROM docs_fts JOIN docs d ON d.rowid = docs_fts.rowid"
        " WHERE docs_fts MATCH ?"
    )
    args: list = []
    if source:
        names = [s.strip() for s in source.split(",") if s.strip()]
        sql += f" AND d.source IN ({','.join('?' * len(names))})"
        args += names
    if kind:
        sql += " AND d.kind = ?"
        args.append(kind)
    sql += " ORDER BY score LIMIT ?"
    with closing(connect()) as con:
        rows = con.execute(sql, [strict, *args, limit * 3]).fetchall()
        if not rows:
            rows = con.execute(sql, [loose, *args, limit * 3]).fetchall()
    hits, seen = [], set()
    for row in rows:
        text = row["body"] if row["kind"] == "link" else row["snip"]
        # The same resource is often listed in several places; show it once.
        key = row["url"] if row["kind"] == "link" else (row["title"], text)
        if key in seen:
            continue
        seen.add(key)
        hits.append({
            "id": row["id"],
            "source": row["source"],
            "kind": row["kind"],
            "title": row["title"],
            "url": row["url"],
            "listed_at": row["origin"] if row["kind"] == "link" else None,
            "context": row["context"],
            "type": row["rtype"] or None,
            "text": (text or "")[:300],
        })
        if len(hits) == limit:
            break
    return hits


def extract_section(text: str, anchor: str) -> str:
    """The heading with this anchor plus everything under it, subsections included."""
    _, body = parse_frontmatter(text)
    lines = body.splitlines()
    seen: dict[str, int] = {}
    in_fence = False
    start, level = None, 0
    for index, line in enumerate(lines):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = HEADING.match(line)
        if not heading:
            continue
        this_level = len(heading.group(1))
        if start is not None and this_level <= level:
            return "\n".join(lines[start:index]).strip()
        if start is None and slugify(heading.group(2), seen) == anchor:
            start, level = index, this_level
    return "\n".join(lines[start:]).strip() if start is not None else ""


def show(ref_id: str, max_chars: int = 12000) -> dict:
    with closing(connect()) as con:
        row = con.execute("SELECT * FROM docs WHERE id = ?", (ref_id,)).fetchone()
        if row is None:
            raise RefsError(f"unknown id: {ref_id} (ids come from search results)")
        source = con.execute("SELECT repo, rev, license FROM sources WHERE name = ?", (row["source"],)).fetchone()
    result = {
        "id": row["id"], "source": row["source"], "kind": row["kind"], "title": row["title"],
        "url": row["url"], "context": row["context"], "license": source["license"] if source else "",
    }
    if row["kind"] == "link":
        result.update({"description": row["body"], "listed_at": row["origin"], "type": row["rtype"] or None})
        return result
    path = data_home() / "repos" / row["source"] / row["path"]
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        text = ""
    if path.suffix == ".json":
        content = row["body"]
    elif row["anchor"]:
        content = extract_section(text, row["anchor"]) or row["body"]
    else:
        content = text or row["body"]
    if source and source["repo"] and source["rev"]:
        result["raw_url"] = f"https://raw.githubusercontent.com/{source['repo']}/{source['rev']}/{row['path']}"
    max_chars = max(500, int(max_chars))
    result["truncated"] = len(content) > max_chars
    result["content"] = content[:max_chars] + (
        f"\n\n[truncated: {len(content) - max_chars} more characters; open url or raw_url for the rest]"
        if result["truncated"] else ""
    )
    return result


def list_sources() -> list[dict]:
    with closing(connect()) as con:
        rows = con.execute("SELECT * FROM sources ORDER BY name").fetchall()
    return [
        {
            "name": r["name"], "repo": r["repo"], "commit": (r["rev"] or "")[:12],
            "synced_at": time.strftime("%Y-%m-%d", time.gmtime(r["synced_at"])) if r["synced_at"] else None,
            "license": r["license"], "about": r["about"], "use_for": r["use_for"],
            "links": r["links"], "sections": r["sections"],
        }
        for r in rows
    ]


def index_info() -> dict:
    path = data_home() / DB_NAME
    if not path.exists():
        return {"ready": False}
    with closing(connect()) as con:
        meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
        counts = con.execute("SELECT source, kind, COUNT(*) FROM docs GROUP BY source, kind").fetchall()
    return {
        "ready": True,
        "built_at": int(meta.get("built_at", 0)),
        "bytes": path.stat().st_size,
        "records": [{"source": s, "kind": k, "count": c} for s, k, c in counts],
    }


def update(log=print) -> dict:
    failures = sync(log=log)
    totals = build(log=log)
    return {"failures": failures, "totals": totals}


# --------------------------------------------------------------------------- CLI


def print_hits(hits: list[dict]) -> None:
    if not hits:
        print("no matches — try the domain term, fewer words, or drop --source/--kind")
        return
    for hit in hits:
        label = f"[{hit['type']}] " if hit.get("type") else ""
        print(f"[{hit['source']}] {hit['kind']}  {label}{hit['title']}")
        if hit["context"]:
            print(f"    in: {hit['context']}")
        if hit["text"]:
            print(f"    {hit['text']}")
        print(f"    {hit['url']}")
        print(f"    id: {hit['id']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="refs.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", action="version", version=f"refs {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("update", help="sync every enabled source, then rebuild the index")
    p_sync = sub.add_parser("sync", help="clone or refresh sources")
    p_sync.add_argument("names", nargs="*")
    sub.add_parser("build", help="rebuild the index from what is on disk")
    p_search = sub.add_parser("search", help="ranked keyword search")
    p_search.add_argument("query", nargs="+")
    p_search.add_argument("--source", help="comma-separated source names")
    p_search.add_argument("--kind", choices=["link", "section"])
    p_search.add_argument("--limit", type=int, default=8)
    p_search.add_argument("--json", action="store_true")
    p_show = sub.add_parser("show", help="full text of one hit")
    p_show.add_argument("id")
    p_show.add_argument("--max-chars", type=int, default=12000)
    p_show.add_argument("--json", action="store_true")
    p_sources = sub.add_parser("sources", help="list indexed sources")
    p_sources.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "update":
            print(f"syncing into {data_home()}")
            failures = sync()
            print("building index")
            build()
            return 1 if failures else 0
        if args.command == "sync":
            return 1 if sync(args.names or None) else 0
        if args.command == "build":
            build()
            return 0
        if args.command == "search":
            hits = search(" ".join(args.query), args.source, args.kind, args.limit)
            print(json.dumps(hits, indent=2, ensure_ascii=False)) if args.json else print_hits(hits)
            return 0
        if args.command == "show":
            result = show(args.id, args.max_chars)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(f"{result['title']}  [{result['source']}, {result['license']}]\n{result['url']}\n")
                print(result.get("content") or result.get("description", ""))
            return 0
        if args.command == "sources":
            rows = list_sources()
            if args.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            else:
                for r in rows:
                    print(f"{r['name']:<28} {r['links']:>6} links {r['sections']:>6} sections  "
                          f"{r['commit'][:7]}  {r['synced_at'] or '-'}  {r['license']}")
                    print(f"{'':<28} {r['use_for']}")
            return 0
    except RefsError as exc:
        print(f"refs: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
