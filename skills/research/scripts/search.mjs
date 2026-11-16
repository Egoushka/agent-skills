#!/usr/bin/env node
// search.mjs: one query, several independent channels, one deduped list.
// Zero dependencies (Node 18+). Channels: SearXNG (your own instance, optional), Exa (hosted MCP, keyless),
// GitHub repository search, the skills.sh directory, curated awesome lists and plugin marketplaces
// (RESEARCH_LISTS overrides them), GitHub code search, then one GraphQL call that adds stars, licence and
// last push to every GitHub repo found by any channel.
//
//   node search.mjs [options] "query" ["another query" ...]
//
//   -c, --channels LIST   searx,exa,gh,skills,lists,ghcode (default: all but ghcode)
//   -n, --num N           results per channel per query (default 10)
//       --pages N         SearXNG pages per category (default 1)
//       --cats LIST       SearXNG categories (default general,it)
//       --skill           ghcode searches filename:SKILL.md (adds ghcode to the channels)
//       --seen FILE       URLs already logged (lines or JSONL with "url"); marks new ones, prints the new share
//       --new-only        print only results not in --seen
//       --log FILE        append every result as JSONL (date, query, channels, url, stars, licence, pushed)
//       --snippets        print a short snippet per result (costs tokens; off by default)
//       --json            print JSON instead of lines
//       --no-enrich       skip the GitHub metadata call
//
// Env: SEARXNG_URL (base URL of a SearXNG instance with the json format enabled; the searx channel runs only when set),
// EXA_MCP_URL (default https://mcp.exa.ai/mcp), EXA_API_KEY or EXA_API_KEY_FILE (keyless when neither exists, sent only to the Exa URL),
// GH_TOKEN or GITHUB_TOKEN (else `gh auth token`). Tokens are sent only to api.github.com and never printed.

import { execFileSync } from 'node:child_process'
import { readFileSync, appendFileSync, existsSync, realpathSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

const SEARX = process.env.SEARXNG_URL || ''
const EXA = process.env.EXA_MCP_URL || 'https://mcp.exa.ai/mcp'
const TIMEOUT = 20000
// Keyless Exa shares a small free quota per IP, so a key is used whenever one is configured.
const EXA_KEY = process.env.EXA_API_KEY || (() => {
  const f = process.env.EXA_API_KEY_FILE
  try { return f && existsSync(f) ? readFileSync(f, 'utf8').trim() : '' } catch { return '' }
})()
const GH_NON_REPO = new Set(['topics', 'orgs', 'search', 'features', 'marketplace', 'settings', 'sponsors', 'apps',
  'collections', 'trending', 'explore', 'about', 'pricing', 'enterprise', 'login', 'signup', 'notifications', 'site', 'readme'])

export function parseArgs(argv) {
  const o = { channels: [...(SEARX ? ['searx'] : []), 'exa', 'gh', 'skills', 'lists'], num: 10, pages: 1, cats: ['general', 'it'], queries: [], enrich: true }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i], next = () => argv[++i]
    if (a === '-c' || a === '--channels') o.channels = next().split(',').map(s => s.trim()).filter(Boolean)
    else if (a === '-n' || a === '--num') o.num = +next()
    else if (a === '--pages') o.pages = +next()
    else if (a === '--cats') o.cats = next().split(',')
    else if (a === '--skill') { o.skill = true; if (!o.channels.includes('ghcode')) o.channels.push('ghcode') }
    else if (a === '--seen') o.seen = next()
    else if (a === '--new-only') o.newOnly = true
    else if (a === '--log') o.log = next()
    else if (a === '--snippets') o.snippets = true
    else if (a === '--json') o.json = true
    else if (a === '--no-enrich') o.enrich = false
    else if (a === '-h' || a === '--help') o.help = true
    else o.queries.push(a)
  }
  return o
}

// One key per resource: GitHub URLs collapse to owner/repo, everything else drops www, hash, tracking and trailing slash.
export function keyOf(raw) {
  let u
  try { u = new URL(raw) } catch { return null }
  const host = u.hostname.toLowerCase().replace(/^www\./, '')
  const parts = u.pathname.split('/').filter(Boolean)
  if (host === 'github.com' && parts.length >= 2 && !GH_NON_REPO.has(parts[0].toLowerCase()))
    return { key: `github.com/${parts[0]}/${parts[1].replace(/\.git$/, '')}`.toLowerCase(), repo: `${parts[0]}/${parts[1].replace(/\.git$/, '')}` }
  for (const p of [...u.searchParams.keys()]) if (/^(utm_|ref$|ref_src$|fbclid$|gclid$)/.test(p)) u.searchParams.delete(p)
  const qs = u.searchParams.toString()
  return { key: `${host}${u.pathname.replace(/\/+$/, '')}${qs ? '?' + qs : ''}`.toLowerCase(), repo: null }
}

export function parseExa(text) {
  const out = []
  for (const block of text.split(/\n(?=Title: )/)) {
    const url = block.match(/^URL: (.+)$/m)?.[1]?.trim()
    if (!url) continue
    const pub = block.match(/^Published: (.+)$/m)?.[1]?.trim()
    const hl = block.split(/^Highlights:\s*$/m)[1] || ''
    out.push({ url, title: block.match(/^Title: (.+)$/m)?.[1]?.trim() || '', date: pub && pub !== 'N/A' ? pub.slice(0, 10) : '',
      snippet: hl.replace(/\s+/g, ' ').trim().slice(0, 300) })
  }
  return out
}

export function merge(lists) {
  const by = new Map()
  for (const { channel, query, items } of lists) for (const it of items) {
    const k = keyOf(it.url)
    if (!k) continue
    let e = by.get(k.key)
    if (!e) by.set(k.key, e = { key: k.key, url: k.repo ? `https://github.com/${k.repo}` : it.url, repo: k.repo,
      title: it.title || '', snippet: it.snippet || '', date: it.date || '', channels: new Set(), queries: new Set(), paths: new Set() })
    e.channels.add(channel); e.queries.add(query)
    if (k.repo && it.url !== e.url) e.paths.add(it.url.replace(/^https:\/\/github\.com\/[^/]+\/[^/]+/, ''))
    if (!e.title && it.title) e.title = it.title
    if (!e.snippet && it.snippet) e.snippet = it.snippet
    if (!e.date && it.date) e.date = it.date
    if (it.installs != null) e.installs = Math.max(e.installs || 0, it.installs)
    if (it.stars != null) Object.assign(e, { stars: it.stars, licence: it.licence, pushed: it.pushed })
  }
  return [...by.values()]
}

const wait = ms => new Promise(r => setTimeout(r, ms))
async function getJSON(url, init = {}, tries = 2) {
  const r = await fetch(url, { ...init, signal: AbortSignal.timeout(TIMEOUT) })
  const t = await r.text()
  if ((r.status === 429 || r.status === 403 && /rate limit/i.test(t)) && tries > 1) { await wait(6000); return getJSON(url, init, tries - 1) }
  if (!r.ok) throw new Error(`HTTP ${r.status} ${t.slice(0, 120).replace(/\s+/g, ' ')}`)
  return t
}

// Keyless Exa and GitHub search rate-limit bursts, so their calls queue one after another; SearXNG runs in parallel.
const lanes = {}
function lane(name, fn) {
  const prev = lanes[name] || Promise.resolve()
  const run = prev.then(fn, fn)
  lanes[name] = run.then(() => wait(700), () => wait(700))
  return run
}

let ghTok
function ghToken() {
  if (ghTok !== undefined) return ghTok
  ghTok = process.env.GH_TOKEN || process.env.GITHUB_TOKEN || ''
  if (!ghTok) try { ghTok = execFileSync('gh', ['auth', 'token'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim() } catch { ghTok = '' }
  return ghTok
}
const ghHeaders = () => ({ accept: 'application/vnd.github+json', 'user-agent': 'research-search', ...(ghToken() ? { authorization: `Bearer ${ghToken()}` } : {}) })

const CH = {
  async searx(q, o) {
    const out = []
    for (const cat of o.cats) for (let p = 1; p <= o.pages; p++) {
      if (!SEARX) throw new Error('SEARXNG_URL is not set')
      const j = JSON.parse(await getJSON(`${SEARX}/search?q=${encodeURIComponent(q)}&format=json&categories=${cat}&pageno=${p}`))
      for (const r of j.results || []) out.push({ url: r.url, title: r.title, snippet: (r.content || '').slice(0, 300),
        date: (r.publishedDate || '').slice(0, 10) })
    }
    return out.slice(0, o.num * o.cats.length * o.pages)
  },
  async exa(q, o) {
    const t = await getJSON(EXA, { method: 'POST', headers: { 'content-type': 'application/json', accept: 'application/json, text/event-stream',
      ...(EXA_KEY && { authorization: `Bearer ${EXA_KEY}` }) },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'web_search_exa',
        arguments: { query: q, numResults: o.num, objective: `Find primary sources (repositories, official docs, maintainers' pages) about: ${q}` } } }) })
    const line = t.match(/^data: (.*)$/m)?.[1] ?? t
    const j = JSON.parse(line)
    if (j.error) throw new Error(j.error.message)
    return (j.result?.content || []).flatMap(c => parseExa(c.text || ''))
  },
  async gh(q, o) {
    const j = JSON.parse(await getJSON(`https://api.github.com/search/repositories?q=${encodeURIComponent(q)}&sort=stars&order=desc&per_page=${o.num}`, { headers: ghHeaders() }))
    return (j.items || []).map(r => ({ url: r.html_url, title: r.description || r.full_name, stars: r.stargazers_count,
      licence: r.license?.spdx_id || 'none', pushed: (r.pushed_at || '').slice(0, 10) }))
  },
  // skills.sh: the open agent-skills directory; install counts are its popularity signal.
  async skills(q, o) {
    const j = JSON.parse(await getJSON(`https://skills.sh/api/search?q=${encodeURIComponent(q)}`))
    return (j.skills || []).slice(0, o.num).map(r => ({ url: `https://github.com/${r.source}#${r.skillId}`, title: `skill ${r.skillId}`, installs: r.installs }))
  },
  // Curated lists and plugin marketplaces, read whole once per run; a line matches when it holds most of the query's words.
  async lists(q, o) {
    const words = q.toLowerCase().split(/\W+/).filter(w => w.length > 3 && !/^(topic|filename|path)$/.test(w))
    if (!words.length) return []
    const need = Math.max(1, Math.ceil(words.length * 0.6)), out = []
    for (const [name, text] of await listTexts()) for (const line of text.split('\n')) {
      const l = line.toLowerCase()
      if (words.filter(w => l.includes(w)).length < need) continue
      for (const m of line.matchAll(/https?:\/\/[^\s)\]>"'`]+/g)) if (usefulLink(m[0])) out.push({ url: m[0], title: `${name}: ${line.replace(/\s+/g, ' ').trim().slice(0, 120)}` })
    }
    return out.slice(0, o.num * 3)
  },
  async ghcode(q, o) {
    if (!ghToken()) throw new Error('code search needs GH_TOKEN')
    const qq = o.skill && !/\b(filename|path):/.test(q) ? `${q} filename:SKILL.md` : q
    const j = JSON.parse(await getJSON(`https://api.github.com/search/code?q=${encodeURIComponent(qq)}&per_page=${Math.min(100, o.num * 3)}`, { headers: ghHeaders() }))
    return (j.items || []).map(r => ({ url: r.html_url, title: `${r.repository.full_name}: ${r.path}` }))
  },
}

export const LISTS = (process.env.RESEARCH_LISTS || [
  'hesreallyhim/awesome-claude-code/README.md', 'VoltAgent/awesome-agent-skills/README.md', 'travisvn/awesome-claude-skills/README.md',
  'sickn33/agentic-awesome-skills/README.md', 'github/awesome-copilot/README.md',
  'anthropics/claude-plugins-official/.claude-plugin/marketplace.json', 'anthropics/claude-plugins-community/.claude-plugin/marketplace.json',
].join(',')).split(',')
// A plugin marketplace becomes one line per plugin: name, description and a GitHub URL for its source.
export function marketplaceLines(text, repo) {
  let j
  try { j = JSON.parse(text) } catch { return '' }
  return (j.plugins || []).map(p => {
    const src = p.source, s = typeof src === 'string' ? src : src?.repo || src?.url || ''
    const url = /^\.?\//.test(s) ? `https://github.com/${repo}/tree/HEAD/${s.replace(/^\.?\//, '')}`
      : /^[\w.-]+\/[\w.-]+$/.test(s) ? `https://github.com/${s}` : s.replace(/\.git$/, '')
    return `${p.name} - ${(p.description || '').replace(/\s+/g, ' ')} ${url}`
  }).join('\n')
}
const NOISE = /(^|\.)(shields\.io|badgen\.net|star-history\.com|githubusercontent\.com)$/
function usefulLink(raw) {
  try {
    const u = new URL(raw), parts = u.pathname.split('/').filter(Boolean)
    return !NOISE.test(u.hostname) && parts.length > 0 && !(u.hostname === 'github.com' && parts.length < 2)
  } catch { return false }
}
let listCache
function listTexts() {
  return listCache ||= Promise.all(LISTS.map(async p => {
    const [owner, repo, ...rest] = p.split('/')
    try {
      const j = JSON.parse(await getJSON(`https://api.github.com/repos/${owner}/${repo}/contents/${rest.join('/')}`, { headers: ghHeaders() }))
      const text = Buffer.from(j.content || '', 'base64').toString('utf8')
      return [`${owner}/${repo}`, p.endsWith('.json') ? marketplaceLines(text, `${owner}/${repo}`) : text]
    } catch (err) { process.stderr.write(`lists: ${p}: ${err.message}\n`); return [p, ''] }
  }))
}

// One GraphQL call per 40 repos: stars, licence, last push, archived.
async function enrich(entries) {
  const todo = entries.filter(e => e.repo && e.stars == null)
  if (!todo.length || !ghToken()) return
  for (let i = 0; i < todo.length; i += 40) {
    const chunk = todo.slice(i, i + 40)
    const body = chunk.map((e, n) => {
      const [owner, name] = e.repo.split('/')
      return `r${n}: repository(owner: ${JSON.stringify(owner)}, name: ${JSON.stringify(name)}) { stargazerCount pushedAt isArchived licenseInfo { spdxId } description }`
    }).join('\n')
    try {
      const j = JSON.parse(await getJSON('https://api.github.com/graphql', { method: 'POST', headers: { ...ghHeaders(), 'content-type': 'application/json' },
        body: JSON.stringify({ query: `{ ${body} }` }) }))
      chunk.forEach((e, n) => {
        const r = j.data?.[`r${n}`]
        if (!r) { e.stars = null; e.note = 'repo not found'; return }
        Object.assign(e, { stars: r.stargazerCount, licence: r.licenseInfo?.spdxId || 'none', pushed: (r.pushedAt || '').slice(0, 10),
          archived: r.isArchived })
        if (!e.title || e.title.includes(': ')) e.title = r.description || e.title
      })
    } catch (err) { process.stderr.write(`enrich: ${err.message}\n`) }
  }
}

function loadSeen(file) {
  const s = new Set()
  if (!file || !existsSync(file)) return s
  for (const line of readFileSync(file, 'utf8').split('\n')) {
    const t = line.trim()
    if (!t) continue
    let url = t
    if (t.startsWith('{')) try { url = JSON.parse(t).url } catch { continue }
    const k = keyOf(url)
    if (k) s.add(k.key)
  }
  return s
}

async function main() {
  const o = parseArgs(process.argv.slice(2))
  if (o.help || !o.queries.length) {
    process.stdout.write(readFileSync(new URL(import.meta.url), 'utf8').split('\n').filter(l => l.startsWith('//')).map(l => l.slice(3)).join('\n') + '\n')
    process.exit(o.help ? 0 : 2)
  }
  const jobs = o.queries.flatMap(q => o.channels.filter(c => CH[c]).map(c => ({ c, q })))
  const counts = {}
  const lists = await Promise.all(jobs.map(async ({ c, q }) => {
    try {
      const items = await (c === 'searx' ? CH[c](q, o) : lane(c.startsWith('gh') ? 'gh' : c, () => CH[c](q, o)))
      counts[c] = (counts[c] || 0) + items.length
      return { channel: c, query: q, items }
    } catch (err) {
      process.stderr.write(`${c} failed for "${q}": ${err.message}\n`)
      counts[c] = counts[c] || 0
      return { channel: c, query: q, items: [] }
    }
  }))
  const entries = merge(lists)
  if (o.enrich) await enrich(entries)
  const seen = loadSeen(o.seen)
  for (const e of entries) e.new = !seen.has(e.key)
  entries.sort((a, b) => b.channels.size - a.channels.size || (b.stars ?? -1) - (a.stars ?? -1))
  const shown = o.newOnly ? entries.filter(e => e.new) : entries
  const today = new Date().toISOString().slice(0, 10)
  if (o.log) appendFileSync(o.log, entries.map(e => JSON.stringify({ found: today, queries: [...e.queries], channels: [...e.channels],
    url: e.url, title: e.title, installs: e.installs, date: e.date || undefined, stars: e.stars ?? undefined, licence: e.licence, pushed: e.pushed, archived: e.archived || undefined })).join('\n') + '\n')
  if (o.json) {
    process.stdout.write(JSON.stringify(shown.map(e => ({ ...e, channels: [...e.channels], queries: [...e.queries], paths: [...e.paths] })), null, 1) + '\n')
  } else {
    for (const e of shown) {
      const meta = e.repo ? `★${e.stars ?? '?'} ${e.licence || '?'} ${e.pushed || '?'}${e.archived ? ' ARCHIVED' : ''}${e.installs ? ` ${e.installs} installs` : ''}` : (e.date || '')
      const extra = e.paths.size ? ` [${[...e.paths].slice(0, 2).join(' ')}]` : ''
      process.stdout.write(`${seen.size ? (e.new ? '+ ' : '  ') : ''}${[...e.channels].join(',')} | ${meta} | ${e.url}${extra} | ${(e.title || '').slice(0, 90)}\n`)
      if (o.snippets && e.snippet) process.stdout.write(`    ${e.snippet.slice(0, 160)}\n`)
    }
  }
  const fresh = entries.filter(e => e.new).length
  process.stderr.write(`raw per channel: ${Object.entries(counts).map(([k, v]) => `${k}=${v}`).join(' ')}; unique ${entries.length}` +
    (seen.size ? `; new ${fresh}/${entries.length} (${entries.length ? Math.round(100 * fresh / entries.length) : 0}%)` : '') + '\n')
}

if (import.meta.url === pathToFileURL(realpathSync(process.argv[1] || '.')).href) main()
