# refs: the reference index as an MCP service

`refs` serves the [`dev-references`](../skills/dev-references/SKILL.md) corpora to every agent from one place. The same `refs.py` engine also runs as a local CLI; this directory wraps it in an MCP server and a container for the VPS.

| Endpoint | Purpose | Auth |
|---|---|---|
| `POST /mcp` | MCP over Streamable HTTP, stateless, JSON responses. Tools: `search_refs`, `read_ref`, `list_ref_sources` | bearer token |
| `GET /stats` | Counters plus the 50 most recent queries that found nothing, which show where the corpora have gaps | bearer token |
| `GET /metrics` | Prometheus text: searches (hit/empty), reads, records per source, index age and size, refresh failures | none |
| `GET /healthz` | Liveness and index readiness | none |

## Run it

The image is published by [`refs-image.yml`](../.github/workflows/refs-image.yml) for amd64 and arm64 after a smoke test against the real corpora.

```bash
export REFS_TOKEN=$(openssl rand -hex 24)
docker compose -f refs/compose.yaml up -d
docker logs -f refs    # first start clones about 90 MB and builds the index in roughly 30 s
```

[`compose.yaml`](compose.yaml) is a starting point: read-only root filesystem, one volume, `mem_limit: 256m` (measured at about 70 MB serving, plus about 30 MB during a rebuild), published on localhost only. Fold it into your GitOps repository and give it a route on your reverse proxy or tailnet.

**Keep it private.** developer-roadmap's license allows personal use only, so expose the endpoint on the tailnet or behind the proxy with `REFS_TOKEN`, never publicly without auth. Set `REFS_ALLOWED_HOSTS` to the hostnames clients use; it enables DNS-rebinding protection.

| Variable | Default | Meaning |
|---|---|---|
| `REFS_TOKEN` | empty (auth off) | Clients send `Authorization: Bearer <token>` |
| `REFS_ALLOWED_HOSTS` | empty (no Host check) | Comma-separated Host values, e.g. `refs.example.ts.net,refs:8765` |
| `REFS_REFRESH_HOURS` | `24` | Re-sync and rebuild interval; `0` builds only on first start |
| `REFS_PORT`, `REFS_HOST` | `8765`, `0.0.0.0` | Listener |
| `REFS_HOME`, `REFS_SOURCES` | `/data`, `/app/sources.json` | Data directory and corpus list |

A refresh builds a new index file and swaps it in atomically, so queries keep working during the rebuild. If a sync fails, the previous index keeps serving and `refs_refresh_failures_total` goes up.

## Connect agents

```bash
# Claude Code (user scope)
claude mcp add --transport http refs https://refs.example.ts.net/mcp --scope user \
  --header "Authorization: Bearer $REFS_TOKEN"

# DeepWiki, the fallback for repositories outside the corpora (free, no auth)
claude mcp add --transport http deepwiki https://mcp.deepwiki.com/mcp --scope user
```

OpenCode (`opencode.json`):

```json
{
  "mcp": {
    "refs": {
      "type": "remote",
      "url": "https://refs.example.ts.net/mcp",
      "headers": { "Authorization": "Bearer {env:REFS_TOKEN}" }
    },
    "deepwiki": { "type": "remote", "url": "https://mcp.deepwiki.com/mcp" }
  }
}
```

Through LiteLLM's MCP gateway, which puts one endpoint and one key in front of every agent, including orchestrator workers:

```yaml
mcp_servers:
  refs:
    url: "http://refs:8765/mcp"
    transport: "http"
    auth_type: "bearer_token"
    auth_value: "os.environ/REFS_TOKEN"
```

Prometheus:

```yaml
- job_name: refs
  static_configs:
    - targets: ["refs:8765"]
```

## Add a corpus

Add an entry to [`sources.json`](../skills/dev-references/assets/sources.json). The fields are documented in its `$comment`; the usual ones are `include` globs, `sparse` paths for big repositories, `sections: true` for prose and `context` to label records by path. Then:

```bash
python3 skills/dev-references/scripts/refs.py sync <name>
python3 skills/dev-references/scripts/refs.py build
python3 skills/dev-references/scripts/refs.py search "<a query it should answer>" --source <name>
```

Add the new corpus to the routing table in the skill as well.

Don't add a corpus for official product documentation, where a vendor MCP already exists (Microsoft Learn for .NET and Azure, for example).
