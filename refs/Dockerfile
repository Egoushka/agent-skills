# refs MCP server. Build from the repository root:
#   docker build -f refs/Dockerfile -t agent-skills-refs .
FROM python:3.13-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY refs/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# The engine ships inside the skill so the same code runs as a local CLI and here.
WORKDIR /app
COPY skills/dev-references/scripts/refs.py skills/dev-references/assets/sources.json refs/server.py ./

RUN useradd --uid 10001 --create-home refs && mkdir /data && chown refs /data
USER refs
ENV REFS_HOME=/data \
    REFS_SOURCES=/app/sources.json \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os, urllib.request as u; u.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('REFS_PORT', '8765'), timeout=4)"

CMD ["python", "server.py"]
