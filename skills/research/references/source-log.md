# Source log

Two layers, both kept with the task (the brief or proposal folder, not the repo unless the repo keeps research notes):

1. **Raw log**, `LOG.jsonl`, written by `search.mjs --log`: one line per unique result per run with `found` (date), `queries`, `channels`, `url`, `title`, `stars`, `installs`, `licence`, `pushed`, `archived`. Pass it to `--seen` on the next round and to the miss pass; the stderr line `new N/M` is the saturation number.
2. **Read log**, a Markdown table of every source you opened, which the report cites:

| URL | What | Licence (API / file) | Stars or installs | Last push | Release | SHA read | Read on | Channel | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| https://github.com/cloudflare/security-audit-skill | six-phase audit, isolated hunters, fresh verifiers, schema-checked findings | MIT / MIT | about 69k | 2025-01-01 | none | c1c8a8c | 2025-01-01 | (missed; found by the requester) | adopted |

Rules:
- Licence by SPDX id; when the API says NOASSERTION or none, read the LICENSE file and quote its first line.
- Stars, installs and dates come from the API on the day you read, never from memory or a blog.
- SHA read is what any later vendoring pins.
