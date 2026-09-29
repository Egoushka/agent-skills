# Security policy

## Reporting a vulnerability

Use GitHub private vulnerability reporting on this repository (Security tab → "Report a
vulnerability"). Don't open a public issue. Expect an acknowledgement within 7 days.

## Scope

In scope: this repository's own skills, the vendoring and validation tools, the `refs` search
service and its image, and the workflows. That includes a vendored skill that reaches the catalog
with a malicious script, a hidden instruction or a broadened `allowed-tools` grant the review
report did not flag, since catching those is the point of the [security model](README.md#security-model).

A flaw inside a vendored skill itself belongs upstream: its source repository is linked in the
catalog, and vendored skills are not edited here beyond recorded patches that cut references to
skills the hub leaves out. The weekly sync brings the fix back.

## Supported versions

Only the latest commit on `main`.
