---
title: "Vendor an upstream skill"
description: "Pin a skill from another repository in vendor.json, copy it byte for byte, cut dangling references with a patch, and review weekly updates."
order: 4
section: "Guides"
---

A skill from someone else is text that steers your agent and, often, code it runs. This hub treats it as a dependency ([ADR 0002](../adr/0002-vendor-and-pin-community-skills.md)): `vendor.py` copies it at a pinned commit and checks the copy byte for byte, and every upstream change arrives as a pull request. [Authoring rule 8](../authoring.md#8-third-party-skills-are-dependencies) gives the reasons. First-party sets such as dotnet/skills, Grafana, Cloudflare and Angular take the same path.

## Skill or plugin

Vendor it when it is only skills. If the upstream plugin also ships a hook, a language server, a sub-agent or a command, copying its skills would drop that part. List it in [publishers.json](../../publishers.json) instead, and people install it from its publisher ([Add a plugin instead](#add-a-plugin-instead)).

Vendor only the skills that earn their context, and say why in the entry's `why` field, which the catalog site shows on the skill's card. The hub took one of taste-skill's thirteen overlapping skills, `design-taste-frontend`. It took superpowers without the SessionStart hook that injects the using-superpowers skill, about 800 tokens, into every session ([ADR 0002](../adr/0002-vendor-and-pin-community-skills.md)).

## Add the entry

Add an object to the `skills` array in [vendor.json](../../vendor.json). This is the entry for `grilling`:

```json title="vendor.json"
{
  "name": "grilling",
  "path": "skills/productivity/grilling",
  "repo": "mattpocock/skills",
  "ref": "HEAD",
  "rev": "c55ee46073ed923f86ce59a5eb3b6d895095d1b7",
  "license": "MIT",
  "license_file": "LICENSE",
  "category": "planning",
  "why": "Interviews you about a plan as a design tree, one round of frontier questions at a time, each with a recommended answer; looks up facts itself and leaves decisions to you. The engine behind grill-me."
}
```

`name` must equal the `name` in the upstream `SKILL.md`, and `rev` is the full commit you reviewed. To read the upstream HEAD, run what `vendor.py` runs:

```bash
git ls-remote https://github.com/<owner>/<repo>.git HEAD
```

[Reference](reference.md#vendorjson) describes every field.

## Copy it

```bash
python3 tools/vendor.py sync <name>
```

`make vendor-sync` does the same for every entry. For each entry, [vendor.py](../../tools/vendor.py):

1. Fetches `rev` from `https://github.com/<repo>.git` at depth 1 and checks out `path` and `license_file`.
2. Stops if `path` holds no `SKILL.md`.
3. Applies the entry's `patches`, in order.
4. Replaces `skills/<name>/` with the result, and copies `license_file` in as `LICENSE` unless the skill ships its own.
5. Stops if the copied `SKILL.md` declares a different `name`.

> [!CAUTION]
> `sync` deletes `skills/<name>/` before it copies upstream in, so a hand edit there is lost. Make the change upstream, or, when it cuts a reference to a skill the hub leaves out, as a patch.

## Check it

```bash
make validate verify catalog
```

- `validate` lints every skill, the new one included. For a vendored skill, warnings become notes, and so does a link to a missing file (E008), marked "(upstream)": upstream owns them. Other errors, such as a broken spec field or a secret, still fail.
- `verify` fetches every pin again and fails if a vendored directory differs by one byte from upstream at `rev` plus its patches. CI runs it on every push to `main` and every pull request.
- `catalog` adds the README row: the repository at the short commit, the license, and a "local patch" link when the entry has patches.

Commit `vendor.json`, `skills/<name>/` and the README together, with a message such as `feat(vendor): …`, the form the history uses for new vendored skills.

## Cut a reference to a skill you left out

Curating a set can leave a vendored skill naming or linking an upstream skill the hub does not vendor, which sends the agent to something that is not installed. Vendor that skill too, or cut the reference with a patch ([README](../../README.md#maintaining)):

1. Write `patches/<name>/<what-it-drops>.patch`: a few lines on why, a blank line, then a git diff whose paths are relative to the upstream repository's root. `vendor.py` applies it with `git apply` in its checkout of upstream. The two existing patches show the form: [executing-plans](../../patches/executing-plans/drop-using-superpowers-reference.patch) and [test-driven-development](../../patches/test-driven-development/drop-writing-skills-reference.patch).
2. List it in the entry's `patches` array. Patches apply in the listed order, so a later one can build on an earlier one ([test_vendor.py](../../tests/test_vendor.py)).
3. Run `python3 tools/vendor.py sync <name>`, then `make verify`, which reports the skill as identical to `<repo>@<rev> + 1 patch`.

A patch only cuts such a reference; every other fix goes upstream ([CONTRIBUTING.md](../../CONTRIBUTING.md)). When upstream later rewrites a patched line, the sync stops with `<patch> no longer applies to <repo>@<rev>`. Refresh the patch against the new upstream, or drop it if upstream removed the reference.

## Review the weekly update

[upstream-sync.yml](../../.github/workflows/upstream-sync.yml) runs every Monday at 05:23 UTC, or when you start it by hand:

1. `vendor.py sync --update --report` moves every pin to the head of its `ref` and writes the review report.
2. If anything changed, it regenerates the README catalog and appends the output of `validate.py` to the report.
3. It opens or updates one pull request from the branch `bot/upstream-sync`, labelled `upstream` and titled `chore(vendor): upstream skill updates`.

For each changed skill the report lists the added, removed and changed files, the patches it re-applied, the change in the `SKILL.md` line count and in its tokens on activation, the old and new `description` and `allowed-tools`, any new URLs, and the first 200 lines of the `SKILL.md` diff. Its "Needs attention" list flags four kinds of change (`review` in [vendor.py](../../tools/vendor.py)):

| Flag | Why it matters |
|---|---|
| `allowed-tools` changed | it changes which commands run without asking |
| `description` changed | it changes when the skill fires |
| executable content added or changed | a script will run on your machine |
| new URLs referenced | the skill sends the agent somewhere new |

Executable content means a file ending in `.sh`, `.py`, `.js`, `.mjs`, `.cjs`, `.ts`, `.ps1`, `.rb` or `.pl`, or any file under `scripts/`. The report asks you to review it like a dependency bump: the text becomes your agent's instructions, and the scripts run on your machine.

> [!IMPORTANT]
> A pull request opened with the default `GITHUB_TOKEN` does not trigger other workflows. CI runs on the sync pull request only when the repository has a `SYNC_TOKEN` secret, a fine-grained personal access token; otherwise the validation output in the pull request body stands in for it ([ADR 0002](../adr/0002-vendor-and-pin-community-skills.md)).

To look before the job does:

```bash
make vendor-status   # pinned commit against upstream HEAD, per skill
make vendor-update   # move every pin and write upstream-report.md (gitignored)
```

## Add a plugin instead

An entry in [publishers.json](../../publishers.json) has six fields: `name`, `repo`, `license`, `why`, `why_plugin` and `install`. The README's "From publishers" table and the catalog site use every field except `license`. [Reference](reference.md#publishersjson) describes each one.
