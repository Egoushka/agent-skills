#!/usr/bin/env python3
"""refs MCP server: the dev-references index as one shared, read-only MCP service.

Run it on the machine that should own the corpus (the VPS); every agent then
queries the same index over Streamable HTTP instead of keeping its own copy.

Environment
  REFS_HOST            bind address (default 0.0.0.0)
  REFS_PORT            port (default 8765)
  REFS_TOKEN           if set, every request except /healthz and /metrics needs
                       "Authorization: Bearer <token>"
  REFS_ALLOWED_HOSTS   comma-separated Host values (e.g. "refs.example.ts.net,refs:8765");
                       enables DNS-rebinding protection
  REFS_REFRESH_HOURS   re-sync and rebuild interval (default 24; 0 = only on first start)
  REFS_HOME, REFS_SOURCES  passed through to refs.py

Endpoints
  POST /mcp      MCP (stateless Streamable HTTP, JSON responses)
  GET  /healthz  liveness plus index readiness
  GET  /metrics  Prometheus text format
  GET  /stats    JSON: counters and the most recent queries that found nothing
"""
from __future__ import annotations

import collections
import hmac
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
for candidate in (HERE, HERE.parent / "skills" / "dev-references" / "scripts"):
    if (candidate / "refs.py").exists():
        sys.path.insert(0, str(candidate))
        break

import refs  # noqa: E402  (located above: next to this file in the image, in the skill in the repo)
import uvicorn  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse, PlainTextResponse  # noqa: E402

HOST = os.environ.get("REFS_HOST", "0.0.0.0")
PORT = int(os.environ.get("REFS_PORT", "8765"))
TOKEN = os.environ.get("REFS_TOKEN", "")
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("REFS_ALLOWED_HOSTS", "").split(",") if h.strip()]
REFRESH_HOURS = float(os.environ.get("REFS_REFRESH_HOURS", "24"))
MAX_READ_CHARS = 60000
PUBLIC_PATHS = frozenset({"/healthz", "/metrics"})

log = logging.getLogger("refs")


class Metrics:
    """In-process counters; restart resets them, Prometheus keeps the history."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.searches = collections.Counter()
        self.reads = 0
        self.errors = 0
        self.refreshes = 0
        self.refresh_failures = 0
        self.building = False
        self.last_refresh = 0.0
        self.empty_queries: collections.deque = collections.deque(maxlen=50)

    def searched(self, query: str, source: str, hits: int) -> None:
        with self.lock:
            self.searches["hit" if hits else "empty"] += 1
            if not hits:
                self.empty_queries.appendleft({"query": query, "source": source or None, "at": int(time.time())})


metrics = Metrics()


def require_index() -> None:
    if refs.index_info().get("ready"):
        return
    if metrics.building:
        raise ToolError("the index is being built (first start); retry in about a minute")
    raise ToolError("no index yet; the server builds it on start, check the container logs")


server = MCPServer(
    name="refs",
    title="Developer references",
    version=refs.__version__,
    instructions=(
        "Curated developer reference corpora (public-apis, system-design-primer, developer-roadmap, "
        "build-your-own-x, free-programming-books, coding-interview-university, awesome lists, "
        "awesome-design-md, freeCodeCamp outline). Call search_refs with 2-4 content words, then "
        "read_ref on the one or two hits that matter. Cite the url of every resource you use. "
        "developer-roadmap text is licensed for personal use only: summarize and link, never republish."
    ),
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)


@server.tool(name="search_refs", title="Search developer references", annotations=READ_ONLY, structured_output=True)
def search_refs(query: str, source: str = "", kind: str = "", limit: int = 8) -> dict[str, Any]:
    """Ranked keyword search over curated developer references.

    Args:
        query: 2-4 content words, e.g. "rate limiter", "currency exchange api", "build your own redis".
        source: optional comma-separated source names (see list_ref_sources), e.g. "public-apis".
        kind: "link" for external resources, "section" for prose chunks, empty for both.
        limit: number of hits, 1-50.

    Returns hits with id, source, kind, title, url and a text snippet. Pass an id to read_ref.
    """
    require_index()
    try:
        hits = refs.search(query, source or None, kind or None, limit)
    except refs.RefsError as exc:  # anticipated: the model reads the message and retries
        with metrics.lock:
            metrics.errors += 1
        raise ToolError(str(exc)) from exc
    metrics.searched(query, source, len(hits))
    return {"query": query, "hits": hits}


@server.tool(name="read_ref", title="Read a reference", annotations=READ_ONLY, structured_output=True)
def read_ref(id: str, max_chars: int = 12000) -> dict[str, Any]:
    """Full text of a search hit: a section with its subsections, a whole document such as a
    DESIGN.md, or a link's details. Use max_chars up to 60000 for whole documents."""
    require_index()
    with metrics.lock:
        metrics.reads += 1
    try:
        return refs.show(id, min(max_chars, MAX_READ_CHARS))
    except refs.RefsError as exc:
        raise ToolError(str(exc)) from exc


@server.tool(name="list_ref_sources", title="List reference sources", annotations=READ_ONLY, structured_output=True)
def list_ref_sources() -> dict[str, Any]:
    """Every indexed corpus with what it is for, its license, commit and record counts."""
    require_index()
    return {"sources": refs.list_sources(), "index": refs.index_info()}


@server.custom_route("/healthz", methods=["GET"])
async def healthz(_: Request) -> JSONResponse:
    info = refs.index_info()
    return JSONResponse({"status": "ok", "ready": info.get("ready", False), "building": metrics.building})


@server.custom_route("/stats", methods=["GET"])
async def stats(_: Request) -> JSONResponse:
    with metrics.lock:
        body = {
            "searches": dict(metrics.searches),
            "reads": metrics.reads,
            "errors": metrics.errors,
            "refreshes": metrics.refreshes,
            "refresh_failures": metrics.refresh_failures,
            "last_refresh": int(metrics.last_refresh) or None,
            "recent_empty_queries": list(metrics.empty_queries),
        }
    body["index"] = refs.index_info()
    return JSONResponse(body)


@server.custom_route("/metrics", methods=["GET"])
async def prometheus(_: Request) -> PlainTextResponse:
    info = refs.index_info()
    lines = [
        "# HELP refs_searches_total Search calls, by whether anything matched.",
        "# TYPE refs_searches_total counter",
    ]
    with metrics.lock:
        for result in ("hit", "empty"):
            lines.append(f'refs_searches_total{{result="{result}"}} {metrics.searches[result]}')
        lines += [
            "# HELP refs_reads_total read_ref calls.",
            "# TYPE refs_reads_total counter",
            f"refs_reads_total {metrics.reads}",
            "# HELP refs_refresh_failures_total Failed sync-and-rebuild runs.",
            "# TYPE refs_refresh_failures_total counter",
            f"refs_refresh_failures_total {metrics.refresh_failures}",
        ]
    lines += [
        "# HELP refs_index_ready 1 when an index is available.",
        "# TYPE refs_index_ready gauge",
        f"refs_index_ready {1 if info.get('ready') else 0}",
    ]
    if info.get("ready"):
        lines += [
            "# HELP refs_index_built_timestamp_seconds When the current index was built.",
            "# TYPE refs_index_built_timestamp_seconds gauge",
            f"refs_index_built_timestamp_seconds {info['built_at']}",
            "# HELP refs_index_bytes Size of the index file.",
            "# TYPE refs_index_bytes gauge",
            f"refs_index_bytes {info['bytes']}",
            "# HELP refs_index_records Indexed records per source and kind.",
            "# TYPE refs_index_records gauge",
        ]
        lines += [
            f'refs_index_records{{source="{r["source"]}",kind="{r["kind"]}"}} {r["count"]}' for r in info["records"]
        ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


class BearerAuth:
    """ASGI middleware: a shared bearer token in front of everything but health and metrics."""

    def __init__(self, app, token: str) -> None:
        self.app = app
        self.expected = f"Bearer {token}".encode() if token else b""

    async def __call__(self, scope, receive, send) -> None:
        if self.expected and scope["type"] == "http" and scope["path"] not in PUBLIC_PATHS:
            supplied = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(supplied, self.expected):
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")],
                })
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        await self.app(scope, receive, send)


def refresh() -> None:
    metrics.building = True
    try:
        result = refs.update(log=log.info)
        with metrics.lock:
            metrics.refreshes += 1
            metrics.last_refresh = time.time()
            if result["failures"]:
                metrics.refresh_failures += 1
        for name, error in result["failures"].items():
            log.warning("sync failed for %s: %s", name, error)
    except Exception:  # keep serving the previous index
        log.exception("refresh failed")
        with metrics.lock:
            metrics.refresh_failures += 1
    finally:
        metrics.building = False


def refresher() -> None:
    if not refs.index_info().get("ready"):
        refresh()
    while REFRESH_HOURS > 0:
        time.sleep(REFRESH_HOURS * 3600)
        refresh()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", force=True)
    security = (
        TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=ALLOWED_HOSTS)
        if ALLOWED_HOSTS else None
    )
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=security, host=HOST
    )
    threading.Thread(target=refresher, name="refresher", daemon=True).start()
    log.info("refs %s on %s:%s (auth %s, data %s)", refs.__version__, HOST, PORT,
             "on" if TOKEN else "off", refs.data_home())
    uvicorn.run(BearerAuth(app, TOKEN), host=HOST, port=PORT, log_level="warning",
                proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
