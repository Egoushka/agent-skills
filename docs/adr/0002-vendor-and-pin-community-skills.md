# 0002: Vendor and pin community skills

- Status: accepted
- Date: 2026-09-27

## Context

A skill is both text that steers the agent and, often, code it runs. Snyk's February 2026 [ToxicSkills study](https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/) scanned 3,984 public skills. It found security flaws in 1,467 of them (36%) and confirmed malicious payloads in 76. Installing straight from a community repository's default branch means taking whatever it contains the next time anyone runs `npx skills update`.

## Decision

- **Community skills are vendored.** `vendor.json` records the repository, the path, a pinned commit and the license. `tools/vendor.py` copies the skill byte-for-byte at that commit, together with its upstream `LICENSE`. CI's `vendor.py verify` fails on any local modification that isn't a recorded patch (see below).
- **Updates are pull requests.** A weekly workflow moves pins to upstream HEAD and opens one PR whose report lists changed files, token deltas and SKILL.md diffs. It flags changed `allowed-tools`, added or changed scripts, new URLs and description changes.
- **Curate, don't mirror.** Only the skill that earns its context is vendored; for example, one of taste-skill's thirteen overlapping skills. Each entry says why in its `why` field, and the catalog shows it.
- **First-party skills are vendored too.** Revised on 2026-09-27: publisher sets such as [dotnet/skills](https://github.com/dotnet/skills), Grafana, Cloudflare and Angular go through the same pin-and-review path, curated to the skills that are actually used. One repository then holds and installs everything, and the catalog shows the whole setup.
- **Plugins that are more than skills stay plugins.** A plugin that ships a hook, a language server, a sub-agent or a command (`dotnet`, several Trail of Bits plugins) loses that part when only its skills are copied. These are installed from their publishers and recorded in `publishers.json`, which the catalog renders. Revised on 2026-09-29: superpowers moved to vendored skills. Its only non-skill part is a SessionStart hook that injects the whole using-superpowers skill (≈800 tokens) into every session, again after `/clear` and compaction. The skills in use are kept, curated with the sub-skills they call; the hook and that bootstrap skill are left out.
- **Local patches only cut references to skills left out.** Revised on 2026-09-29: curating a set can leave a vendored skill naming or linking an upstream skill the hub doesn't vendor, which sends the agent to something that isn't installed. Such a reference is cut by a patch: a diff in upstream paths under `patches/<skill>/`, listed in the entry's `patches` field and applied by `vendor.py` after every fetch. `verify` then proves the copy is upstream at `rev` plus exactly those patches, and the catalog marks the skill as patched. Every other fix still goes upstream.

## Consequences

- A weekly review chore, which is also the point: every change is seen once.
- Upstream fixes arrive at most a week late unless the workflow is run by hand.
- Each patch is a small fork. When upstream rewrites a patched line, the weekly sync stops with the patch's name until it is refreshed, or dropped because upstream removed the reference.
- Pull requests opened with `GITHUB_TOKEN` don't trigger other workflows. The sync job therefore appends validation output to the PR body, and a `SYNC_TOKEN` secret (a fine-grained PAT) makes CI run on those PRs as well.
