// node --test skills/research/scripts/search.test.mjs  (offline: parsing and dedupe only)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { keyOf, parseExa, merge, parseArgs, marketplaceLines } from './search.mjs'

test('GitHub URLs collapse to the repo', () => {
  assert.equal(keyOf('https://www.github.com/Cloudflare/security-audit-skill/blob/main/SKILL.md').key, 'github.com/cloudflare/security-audit-skill')
  assert.equal(keyOf('https://github.com/topics/claude-skills').repo, null)
  assert.equal(keyOf('https://example.com/a/?utm_source=x#top').key, 'example.com/a')
  assert.equal(keyOf('not a url'), null)
})

test('Exa text blocks parse', () => {
  const t = 'Title: A\nURL: https://a.dev/x\nPublished: 2026-10-01T00:00:00Z\nAuthor: N/A\nHighlights:\nhello  world\n\nTitle: B\nURL: https://b.dev\nPublished: N/A\n'
  const r = parseExa(t)
  assert.equal(r.length, 2); assert.equal(r[0].date, '2026-10-01'); assert.equal(r[0].snippet, 'hello world'); assert.equal(r[1].date, '')
})

test('merge dedupes across channels and keeps paths', () => {
  const m = merge([
    { channel: 'exa', query: 'q', items: [{ url: 'https://github.com/o/r/blob/main/SKILL.md', title: 't' }] },
    { channel: 'gh', query: 'q', items: [{ url: 'https://github.com/o/r', title: 'repo', stars: 5, licence: 'MIT', pushed: '2026-11-01' }] },
  ])
  assert.equal(m.length, 1); assert.deepEqual([...m[0].channels], ['exa', 'gh']); assert.equal(m[0].stars, 5)
  assert.deepEqual([...m[0].paths], ['/blob/main/SKILL.md'])
})

test('args and marketplaces', () => {
  const o = parseArgs(['--skill', '-n', '3', 'a b'])
  assert.ok(o.channels.includes('ghcode')); assert.equal(o.num, 3); assert.deepEqual(o.queries, ['a b'])
  const lines = marketplaceLines(JSON.stringify({ plugins: [{ name: 'p', description: 'd', source: './plugins/p' }, { name: 'q', source: { source: 'github', repo: 'o/q' } }] }), 'a/m')
  assert.match(lines, /github\.com\/a\/m\/tree\/HEAD\/plugins\/p/); assert.match(lines, /github\.com\/o\/q/)
})
