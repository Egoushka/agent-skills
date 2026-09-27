#!/usr/bin/env python3
"""Generate the skill catalog: the README table and the GitHub Pages site.

  catalog.py                    rewrite the catalog block in README.md
  catalog.py --check            exit 1 if the README block is stale (CI)
  catalog.py --site DIR         also write DIR/index.html and DIR/catalog.json
  catalog.py --site DIR --upstream   include upstream status for vendored skills (network)

Everything is derived from the skills themselves, vendor.json, validate.py findings
and git history, so the catalog cannot drift from what actually ships.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

from common import REPO_SLUG, ROOT, git, iter_skills, load_vendor
from validate import run as validate

START, END = "<!-- catalog:start -->", "<!-- catalog:end -->"
README = ROOT / "README.md"
TEMPLATE = ROOT / "tools" / "site" / "index.html"
SOURCES = ROOT / "skills" / "dev-references" / "assets" / "sources.json"
PUBLISHERS = ROOT / "publishers.json"
GUIDE_TOKENS = 5000


def first_sentence(text: str, limit: int = 170) -> str:
    text = re.sub(r"\s*\([^)]*\)", "", text)  # parenthetical lists read badly in a table cell
    sentence = text.split(". ")[0].rstrip(".") + "."
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rsplit(" ", 1)[0] + "…"


def fmt(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def history(path: str) -> tuple[str | None, int | None]:
    try:
        log = git("log", "--format=%ad", "--date=short", "--", path)
    except RuntimeError:
        return None, None
    dates = log.splitlines()
    return (dates[0] if dates else None), len(dates)


def upstream_heads(entries: list[dict]) -> dict[str, str | None]:
    heads = {}
    for entry in entries:
        try:
            out = git("ls-remote", f"https://github.com/{entry['repo']}.git", entry.get("ref", "HEAD"))
            heads[entry["name"]] = out.split()[0] if out else None
        except RuntimeError:
            heads[entry["name"]] = None
    return heads


def build(with_upstream: bool) -> dict:
    vendor_entries = load_vendor()["skills"]
    vendor = {e["name"]: e for e in vendor_entries}
    findings = validate()
    heads = upstream_heads(vendor_entries) if with_upstream else {}
    skills = []
    for skill in iter_skills():
        entry = vendor.get(skill.name)
        files = skill.files()
        updated, commits = history(f"skills/{skill.name}")
        item = {
            "name": skill.name,
            "description": skill.description,
            "category": (entry or {}).get("category") or (skill.meta.get("metadata") or {}).get("category", ""),
            "origin": "vendored" if entry else "own",
            "metadata_tokens": skill.metadata_tokens,
            "body_tokens": skill.body_tokens,
            "body_lines": skill.body_lines,
            "files": len(files),
            "references": sum(1 for f in files if "references" in f.relative_to(skill.path).parts),
            "scripts": sum(1 for f in files if "scripts" in f.relative_to(skill.path).parts),
            "allowed_tools": skill.meta.get("allowed-tools"),
            "findings": findings.get(skill.name, {}).get("findings", []),
            "updated": updated,
            "commits": commits,
            "install": f"npx skills add {REPO_SLUG} --skill {skill.name}",
            "license": (entry or {}).get("license") or skill.meta.get("license", ""),
        }
        if entry:
            head = heads.get(skill.name)
            item.update({
                "repo": entry["repo"], "path": entry["path"], "rev": entry["rev"], "why": entry.get("why", ""),
                "upstream": {"head": head, "behind": head != entry["rev"]} if head else None,
            })
        skills.append(item)
    bodies = [s["body_tokens"] for s in skills] or [0]
    try:
        activity = [
            dict(zip(("sha", "date", "subject"), line.split("\x1f")))
            for line in git("log", "-n", "15", "--date=short", "--format=%H\x1f%ad\x1f%s").splitlines()
        ]
        commit = git("rev-parse", "--short", "HEAD")
    except RuntimeError:
        activity, commit = [], None
    corpora = json.loads(SOURCES.read_text(encoding="utf-8"))["sources"] if SOURCES.exists() else []
    return {
        "repo": REPO_SLUG,
        "commit": commit,
        "generated_at": time.strftime("%Y-%m-%d"),
        "install": f"npx skills add {REPO_SLUG}",
        "totals": {
            "skills": len(skills),
            "own": sum(s["origin"] == "own" for s in skills),
            "vendored": sum(s["origin"] == "vendored" for s in skills),
            "metadata_tokens": sum(s["metadata_tokens"] for s in skills),
            "median_body_tokens": int(statistics.median(bodies)),
            "updates_pending": sum(bool(s.get("upstream") and s["upstream"]["behind"]) for s in skills)
            if with_upstream else None,
        },
        "skills": skills,
        "corpora": [
            {k: c.get(k, "") for k in ("name", "repo", "about", "use_for", "license")}
            for c in corpora if c.get("enabled", True)
        ],
        "activity": activity,
        "publishers": json.loads(PUBLISHERS.read_text(encoding="utf-8"))["plugins"] if PUBLISHERS.exists() else [],
    }


def readme_block(data: dict) -> str:
    rows = [
        "| Skill | Origin | What it is for | Always loaded | On activation |",
        "|---|---|---|--:|--:|",
    ]
    for s in data["skills"]:
        if s["origin"] == "vendored":
            origin = f"[{s['repo']}@{s['rev'][:7]}](https://github.com/{s['repo']}/tree/{s['rev']}/{s['path']}) · {s['license']}"
        else:
            origin = "own"
        over = " ⚠" if s["body_tokens"] > GUIDE_TOKENS else ""
        rows.append(
            f"| [`{s['name']}`](skills/{s['name']}) | {origin} | {first_sentence(s['description'])} "
            f"| ≈{fmt(s['metadata_tokens'])} | ≈{fmt(s['body_tokens'])}{over} |"
        )
    t = data["totals"]
    rows += [
        "",
        f"All {t['skills']} skills together cost ≈{fmt(t['metadata_tokens'])} tokens in every session (names and "
        f"descriptions); a body loads only when its skill fires. ⚠ marks a body over the {GUIDE_TOKENS:,}-token "
        "guideline. Token counts are estimates (characters ÷ 4).",
    ]
    if data["publishers"]:
        rows += [
            "",
            "**From publishers.** These carry more than skills (hooks, a language server, sub-agents, commands), "
            "so they install as plugins from their publishers; their pure skills are vendored above.",
            "",
            "| Plugin | What it is for | Why a plugin | Install |",
            "|---|---|---|---|",
        ]
        rows += [
            f"| [`{p['name']}`](https://github.com/{p['repo']}) | {p['why']} | {p['why_plugin']} | `{p['install']}` |"
            for p in data["publishers"]
        ]
    return "\n".join([START, "<!-- generated by tools/catalog.py; do not edit by hand -->", *rows, END])


def replace_block(text: str, block: str) -> str:
    start, end = text.index(START), text.index(END) + len(END)
    return text[:start] + block + text[end:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if README.md is stale")
    parser.add_argument("--site", help="write the Pages site into this directory")
    parser.add_argument("--upstream", action="store_true", help="query upstream heads (network)")
    args = parser.parse_args()

    data = build(args.upstream)
    current = README.read_text(encoding="utf-8")
    updated = replace_block(current, readme_block(data))
    if args.check:
        if updated != current:
            print("README.md catalog is stale: run `python3 tools/catalog.py` and commit the result.")
            return 1
        print("README.md catalog is up to date.")
    elif updated != current:
        README.write_text(updated, encoding="utf-8")
        print("README.md catalog updated.")
    if args.site:
        out = Path(args.site)
        out.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        html = TEMPLATE.read_text(encoding="utf-8").replace("__CATALOG_JSON__", payload)
        (out / "index.html").write_text(html, encoding="utf-8")
        (out / "catalog.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"site written to {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
