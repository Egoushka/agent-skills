#!/usr/bin/env python3
"""Lint every skill against the Agent Skills spec and this repository's authoring rules.

  validate.py            human-readable report; exit 1 on any error
  validate.py --strict   also exit 1 on warnings in skills authored here (not vendored ones)
  validate.py --json     machine-readable findings (used by catalog.py)

Errors break the spec or a client (the skill may not load). Warnings are authoring
practices from docs/authoring.md; vendored skills get them as notes, since they are
fixed upstream rather than here.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import SKILLS_DIR, Skill, is_text, iter_skills, vendored

NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
RESERVED = ("anthropic", "claude")
LOCAL_LINK = re.compile(r"\]\((?!https?://|mailto:|#)([^)\s]+)\)")
FIRST_OR_SECOND_PERSON = re.compile(r"\b(I can|I will|I'll|I help|you can|you should|you'll)\b", re.I)
BROAD_TOOLS = re.compile(r"Bash\((\*|npx:\*|npm:\*|sh:\*|bash:\*|python3?:\*|curl:\*)\)|^Bash$|\sBash(\s|$)")
SECRETS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b"),
    "Anthropic key": re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}\b"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
}
MAX_BODY_LINES = 500
MAX_BODY_TOKENS = 5000
OVERLAP_THRESHOLD = 0.35
STOP = set("a an and are as at be by for from if in into is it its of on or that the this to use used using when with".split())


def prose(text: str) -> str:
    """Markdown with fenced blocks and inline code removed: links inside examples are not links."""
    text = re.sub(r"^(\s*)(`{3,}|~{3,}).*?^\1\2[ \t]*$", "", text, flags=re.S | re.M)
    return re.sub(r"`[^`\n]*`", "", text)


def finding(level: str, code: str, message: str) -> dict:
    return {"level": level, "code": code, "message": message}


def check_frontmatter(skill: Skill) -> list[dict]:
    out = []
    if skill.error:
        return [finding("error", "E001", skill.error)]
    meta = skill.meta
    name = meta.get("name")
    if not isinstance(name, str) or not name:
        out.append(finding("error", "E002", "`name` is required"))
    else:
        if len(name) > 64 or not NAME.match(name):
            out.append(finding("error", "E002", f"`name` {name!r}: 1-64 chars of a-z, 0-9 and single hyphens"))
        if name != skill.name:
            out.append(finding("error", "E002", f"`name` {name!r} must match its directory {skill.name!r}"))
        if any(word in name for word in RESERVED):
            out.append(finding("error", "E013", f"`name` contains a reserved word ({', '.join(RESERVED)}); some clients reject it"))
    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        out.append(finding("error", "E003", "`description` is required"))
    else:
        if len(description) > 1024:
            out.append(finding("error", "E003", f"`description` is {len(description)} chars; the limit is 1024"))
        if "<" in description or ">" in description:
            out.append(finding("error", "E012", "`description` contains angle brackets; some clients reject XML-like text"))
        if FIRST_OR_SECOND_PERSON.search(description):
            out.append(finding("warning", "W103", "write the description in third person; it is injected into the system prompt"))
        if not re.search(r"\b(use (it |this )?when|when the user|use for|use to)\b", description, re.I):
            out.append(finding("warning", "W104", "the description should say when to use the skill, not only what it does"))
    compatibility = meta.get("compatibility")
    if compatibility is not None and (not isinstance(compatibility, str) or not 1 <= len(compatibility) <= 500):
        out.append(finding("error", "E004", "`compatibility` must be a 1-500 character string"))
    metadata = meta.get("metadata")
    if metadata is not None and (
        not isinstance(metadata, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in metadata.items())
    ):
        out.append(finding("error", "E005", "`metadata` must map strings to strings (quote versions: \"1.0\")"))
    tools = meta.get("allowed-tools")
    if tools is not None:
        if not isinstance(tools, str):
            out.append(finding("error", "E006", "`allowed-tools` must be a space-separated string"))
        elif BROAD_TOOLS.search(tools):
            out.append(finding("warning", "W110", f"`allowed-tools` pre-approves broad command execution: {tools}"))
    extra = sorted(set(meta) - SPEC_FIELDS)
    if extra:
        out.append(finding("warning", "W111", f"fields outside the Agent Skills spec (client-specific): {', '.join(extra)}"))
    return out


def check_body(skill: Skill) -> list[dict]:
    out = []
    if skill.body_lines > MAX_BODY_LINES:
        out.append(finding("warning", "W101", f"SKILL.md body is {skill.body_lines} lines; keep it under {MAX_BODY_LINES} and move detail to references/"))
    if skill.body_tokens > MAX_BODY_TOKENS:
        out.append(finding("warning", "W102", f"SKILL.md body is ≈{skill.body_tokens} tokens; the guideline is under {MAX_BODY_TOKENS}"))
    if re.search(r"\b[\w.-]+\\[\w.-]+\.(md|py|sh|json)\b", prose(skill.body)):
        out.append(finding("warning", "W108", "use forward slashes in file paths"))
    for target in LOCAL_LINK.findall(prose(skill.body)):
        # {baseDir} is a client placeholder for the skill's own folder (Claude Code).
        clean = target.split("#")[0].replace("{baseDir}/", "")
        if clean and not (skill.path / clean).exists():
            out.append(finding("error", "E008", f"link to missing file: {target}"))
    for ref in sorted(skill.path.rglob("*.md")):
        if ref.name == "SKILL.md" or ref.name == "LICENSE.md":
            continue
        text = ref.read_text(encoding="utf-8", errors="replace")
        rel = ref.relative_to(skill.path).as_posix()
        if len(text.splitlines()) > 100 and not re.search(r"^#{1,3}\s+(table of )?contents\b", text, re.I | re.M):
            out.append(finding("warning", "W107", f"{rel} is over 100 lines without a contents section"))
        nested = [t for t in LOCAL_LINK.findall(prose(text)) if t.split("#")[0].endswith(".md")]
        if nested:
            out.append(finding("warning", "W109", f"{rel} links to further .md files; keep references one level deep"))
    return out


def check_secrets(skill: Skill) -> list[dict]:
    out = []
    for path in skill.files():
        if not is_text(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in SECRETS.items():
            if pattern.search(text):
                rel = path.relative_to(skill.path).as_posix()
                out.append(finding("error", "E009", f"possible {label} in {rel}"))
    return out


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9-]+", text.lower()) if w not in STOP and len(w) > 2}


def check_overlap(skills: list[Skill]) -> dict[str, list[dict]]:
    """Similar descriptions compete for the same requests, so one of them mis-triggers."""
    out: dict[str, list[dict]] = {}
    for i, a in enumerate(skills):
        for b in skills[i + 1:]:
            wa, wb = words(a.description), words(b.description)
            if not wa or not wb:
                continue
            score = len(wa & wb) / len(wa | wb)
            if score >= OVERLAP_THRESHOLD:
                msg = f"description overlaps {int(score * 100)}% with `{b.name}`; sharpen both so each triggers alone"
                out.setdefault(a.name, []).append(finding("warning", "W112", msg))
                out.setdefault(b.name, []).append(finding("warning", "W112", msg.replace(f"`{b.name}`", f"`{a.name}`")))
    return out


def run() -> dict[str, dict]:
    skills = iter_skills()
    vendor = vendored()
    overlap = check_overlap(skills)
    results = {}
    for skill in skills:
        items = check_frontmatter(skill) + check_body(skill) + check_secrets(skill) + overlap.get(skill.name, [])
        is_vendored = skill.name in vendor
        if is_vendored:
            # Upstream owns its practices and its own links: keep both visible, never failing.
            # Spec violations and secrets still fail, because they break or endanger the install.
            items = [
                dict(f, level="note", message=f["message"] + " (upstream)") if f["code"] == "E008"
                else dict(f, level="note") if f["level"] == "warning" else f
                for f in items
            ]
        results[skill.name] = {"vendored": is_vendored, "findings": items}
    for name in sorted(set(vendor) - {s.name for s in skills}):
        results[name] = {"vendored": True, "findings": [finding("error", "E011", "listed in vendor.json but missing; run tools/vendor.py sync")]}
    orphans = sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and not (p / "SKILL.md").exists())
    for name in orphans:
        results[name] = {"vendored": False, "findings": [finding("error", "E010", "directory under skills/ without SKILL.md")]}
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--strict", action="store_true", help="fail on warnings in own skills")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    results = run()
    if args.json:
        print(json.dumps(results, indent=2))
    errors = sum(f["level"] == "error" for r in results.values() for f in r["findings"])
    own_warnings = sum(f["level"] == "warning" for r in results.values() for f in r["findings"] if not r["vendored"])
    if not args.json:
        icons = {"error": "✗", "warning": "!", "note": "·"}
        for name, result in sorted(results.items()):
            tag = "vendored" if result["vendored"] else "own"
            worst = "✗" if any(f["level"] == "error" for f in result["findings"]) else "✓"
            print(f"{worst} {name} ({tag})")
            for f in result["findings"]:
                print(f"    {icons[f['level']]} {f['code']} {f['message']}")
        print(f"\n{len(results)} skills · {errors} error(s) · {own_warnings} warning(s) in own skills")
    if errors or (args.strict and own_warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
