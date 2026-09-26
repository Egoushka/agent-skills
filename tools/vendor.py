#!/usr/bin/env python3
"""Vendor third-party skills at pinned commits, and review what upstream changed.

  vendor.py status [--json]          pinned commit vs upstream HEAD for every vendored skill
  vendor.py sync [NAME ...]          re-materialize skills at their pinned commits
  vendor.py sync --update [NAME ...] move pins to upstream HEAD and write a review report
  vendor.py verify                   fail if a vendored directory differs from its pinned upstream

vendor.json is the lock file: repo, path inside it, pinned `rev`, license. A vendored skill
is a byte-for-byte copy of upstream at `rev` plus the upstream LICENSE; nobody edits it here.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from common import ROOT, SKILLS_DIR, estimate_tokens, git, load_skill, load_vendor, save_vendor

URL = re.compile(r"https?://[^\s)\"'<>`]+")
EXECUTABLE = {".sh", ".py", ".js", ".mjs", ".cjs", ".ts", ".ps1", ".rb", ".pl"}


def remote_head(entry: dict) -> str:
    out = git("ls-remote", f"https://github.com/{entry['repo']}.git", entry.get("ref", "HEAD"))
    if not out:
        raise RuntimeError(f"{entry['repo']}: ref {entry.get('ref', 'HEAD')} not found")
    return out.split()[0]


def fetch(entry: dict, rev: str, into: Path) -> Path:
    """Materialize upstream `path` (+ license) at `rev` into a fresh directory."""
    work = Path(tempfile.mkdtemp(prefix="vendor-"))
    git("init", "--quiet", str(work))
    git("remote", "add", "origin", f"https://github.com/{entry['repo']}.git", cwd=work)
    git("fetch", "--quiet", "--depth", "1", "--filter=blob:none", "origin", rev, cwd=work)
    paths = [entry["path"]] + ([entry["license_file"]] if entry.get("license_file") else [])
    git("checkout", "--quiet", "FETCH_HEAD", "--", *paths, cwd=work)
    src = work / entry["path"]
    if not (src / "SKILL.md").is_file():
        raise RuntimeError(f"{entry['repo']}@{rev[:7]}: no SKILL.md under {entry['path']}")
    if into.exists():
        shutil.rmtree(into)
    shutil.copytree(src, into)
    license_src = work / entry["license_file"] if entry.get("license_file") else None
    if license_src and license_src.is_file() and not (into / "LICENSE").exists():
        shutil.copyfile(license_src, into / "LICENSE")
    shutil.rmtree(work)
    declared = load_skill(into).meta.get("name")
    if declared != entry["name"]:
        raise RuntimeError(f"{entry['repo']}: SKILL.md declares name {declared!r}, vendor.json expects {entry['name']!r}")
    return into


def snapshot(directory: Path) -> dict[str, bytes]:
    if not directory.exists():
        return {}
    return {
        p.relative_to(directory).as_posix(): p.read_bytes()
        for p in sorted(directory.rglob("*")) if p.is_file()
    }


def frontmatter_field(text: str, field: str) -> str:
    match = re.search(rf"^{field}:\s*(.+)$", text, re.M)
    return match.group(1).strip() if match else ""


def review(name: str, entry: dict, old_rev: str, new_rev: str, before: dict, after: dict) -> tuple[list[str], list[str]]:
    """Markdown lines describing the change, plus attention flags for the reviewer."""
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(p for p in set(before) & set(after) if before[p] != after[p])
    compare = f"https://github.com/{entry['repo']}/compare/{old_rev[:12]}...{new_rev[:12]}"
    lines = [f"### `{name}` — [{entry['repo']}]({compare}) `{old_rev[:7]}` → `{new_rev[:7]}`", ""]
    flags: list[str] = []
    for label, items in (("Added", added), ("Removed", removed), ("Changed", changed)):
        if items:
            lines.append(f"- {label}: " + ", ".join(f"`{p}`" for p in items))
    old_md = before.get("SKILL.md", b"").decode("utf-8", "replace")
    new_md = after.get("SKILL.md", b"").decode("utf-8", "replace")
    if old_md != new_md:
        delta = estimate_tokens(new_md) - estimate_tokens(old_md)
        lines.append(f"- SKILL.md: {len(old_md.splitlines())} → {len(new_md.splitlines())} lines, "
                     f"≈{delta:+} tokens on activation")
        for field in ("description", "allowed-tools"):
            old_value, new_value = frontmatter_field(old_md, field), frontmatter_field(new_md, field)
            if old_value != new_value:
                lines.append(f"- `{field}` changed:\n  - before: {old_value or '(none)'}\n  - after: {new_value or '(none)'}")
                if field == "allowed-tools":
                    flags.append(f"`{name}`: allowed-tools changed (pre-approved commands)")
                if field == "description":
                    flags.append(f"`{name}`: description changed (affects when it triggers)")
    for path in added + changed:
        if Path(path).suffix.lower() in EXECUTABLE or path.startswith("scripts/"):
            flags.append(f"`{name}`: executable content added or changed: `{path}`")
    old_urls = {u for p, b in before.items() if is_text_bytes(p) for u in URL.findall(b.decode("utf-8", "replace"))}
    new_urls = {u for p, b in after.items() if is_text_bytes(p) for u in URL.findall(b.decode("utf-8", "replace"))}
    fresh = sorted(new_urls - old_urls)
    if fresh:
        lines.append("- New URLs: " + ", ".join(f"<{u}>" for u in fresh[:15]) + (" …" if len(fresh) > 15 else ""))
        flags.append(f"`{name}`: {len(fresh)} new URL(s) referenced")
    if old_md != new_md:
        diff = difflib.unified_diff(old_md.splitlines(), new_md.splitlines(), "SKILL.md (pinned)", "SKILL.md (upstream)", lineterm="", n=1)
        body = "\n".join(list(diff)[:200])
        # Four backticks: SKILL.md bodies contain ``` fences of their own.
        lines += ["", "<details><summary>SKILL.md diff (first 200 lines)</summary>", "", "````diff", body, "````", "", "</details>"]
    return lines + [""], flags


def is_text_bytes(path: str) -> bool:
    return Path(path).suffix.lower() in {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".sh", ".js", ".ts", ".html"}


def cmd_status(as_json: bool) -> int:
    rows = []
    for entry in load_vendor()["skills"]:
        try:
            head = remote_head(entry)
        except RuntimeError as exc:
            head, error = None, str(exc)
        else:
            error = None
        rows.append({
            "name": entry["name"], "repo": entry["repo"], "pinned": entry["rev"], "upstream": head,
            "behind": bool(head and head != entry["rev"]), "error": error,
        })
    if as_json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            state = r["error"] or ("update available " + r["upstream"][:7] if r["behind"] else "up to date")
            print(f"{r['name']:<28} {r['repo']:<32} {r['pinned'][:7]}  {state}")
    return 0


def cmd_sync(names: list[str], update: bool, report: str | None) -> int:
    config = load_vendor()
    entries = [e for e in config["skills"] if not names or e["name"] in names]
    sections, flags, changed_any = [], [], False
    for entry in entries:
        dest = SKILLS_DIR / entry["name"]
        old_rev = entry["rev"]
        new_rev = remote_head(entry) if update else old_rev
        before = snapshot(dest)
        fetch(entry, new_rev, dest)
        after = snapshot(dest)
        if before == after and new_rev == old_rev:
            print(f"  = {entry['name']:<28} {old_rev[:7]}")
            continue
        changed_any = True
        entry["rev"] = new_rev
        print(f"  ↻ {entry['name']:<28} {old_rev[:7]} → {new_rev[:7]}")
        lines, found = review(entry["name"], entry, old_rev, new_rev, before, after)
        sections += lines
        flags += found
    save_vendor(config)
    if report:
        body = ["## Upstream skill updates", ""]
        if not changed_any:
            body.append("No vendored skill changed upstream.")
        else:
            body += ["Each vendored skill below moved to its upstream HEAD. Review like a dependency bump: "
                     "the text becomes instructions for your agent, and scripts run on your machine.", ""]
            if flags:
                body += ["**Needs attention**", ""] + [f"- {f}" for f in flags] + [""]
            body += sections
        Path(report).write_text("\n".join(body) + "\n", encoding="utf-8")
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.write(f"changed={'true' if changed_any else 'false'}\n")
    return 0


def cmd_verify() -> int:
    failures = 0
    for entry in load_vendor()["skills"]:
        expected = Path(tempfile.mkdtemp(prefix="verify-")) / entry["name"]
        fetch(entry, entry["rev"], expected)
        local, upstream = snapshot(SKILLS_DIR / entry["name"]), snapshot(expected)
        shutil.rmtree(expected.parent)
        if local != upstream:
            failures += 1
            drift = sorted(set(local) ^ set(upstream) | {p for p in set(local) & set(upstream) if local[p] != upstream[p]})
            print(f"  ✗ {entry['name']}: differs from {entry['repo']}@{entry['rev'][:7]} in {', '.join(drift[:10])}")
        else:
            print(f"  ✓ {entry['name']:<28} identical to {entry['repo']}@{entry['rev'][:7]}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")
    p_sync = sub.add_parser("sync")
    p_sync.add_argument("names", nargs="*")
    p_sync.add_argument("--update", action="store_true", help="move pins to upstream HEAD")
    p_sync.add_argument("--report", help="write a Markdown review report here")
    sub.add_parser("verify")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.command == "status":
        return cmd_status(args.json)
    if args.command == "sync":
        return cmd_sync(args.names, args.update, args.report)
    return cmd_verify()


if __name__ == "__main__":
    sys.exit(main())
