"""Tests for the reference index: Markdown parsing, anchors, and a build/search/show round trip."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "dev-references" / "scripts"))
import refs  # noqa: E402

CATALOG = """# Public APIs

## Currency Exchange
API | Description | Auth | HTTPS | CORS |
|:---|:---|:---|:---|:---|
| [Frankfurter](https://www.frankfurter.app/docs) | Exchange rates, currency conversion | No | Yes | Yes |
| ![badge](https://img.shields.io/x.svg) | not a resource | No | No | No |

## Build your own `Database`
* [**C++**: _Build Your Own Redis_](https://build-your-own.org/redis) - James Smith
* [Anchors are skipped](#currency-exchange)

```
* [inside a fence](https://example.com/ignored)
```
"""

PROSE = """---
name: Warp-design
description: A warm charcoal canvas.
---
# Caching

Intro text.

## Cache invalidation

There are only two hard things.

### Write-through

Write to cache and DB together.

## CDN

Edge caches.

## CDN

A duplicate heading gets an -1 anchor.
"""


class ParseTests(unittest.TestCase):
    def test_table_rows_become_labelled_links(self):
        records = refs.parse_markdown(CATALOG, sections=False, whole_doc=False)
        links = [r for r in records if r["kind"] == "link"]
        titles = [r["title"] for r in links]
        self.assertIn("Frankfurter", titles)
        frank = links[titles.index("Frankfurter")]
        self.assertEqual(frank["body"], "Exchange rates, currency conversion · Auth: No · HTTPS: Yes · CORS: Yes")
        self.assertEqual(frank["context"], "Public APIs › Currency Exchange")

    def test_list_items_badges_anchors_and_fences(self):
        records = refs.parse_markdown(CATALOG, sections=False, whole_doc=False)
        titles = [r["title"] for r in records]
        self.assertIn("C++: Build Your Own Redis", titles)
        self.assertNotIn("inside a fence", titles)
        self.assertNotIn("Anchors are skipped", titles)
        self.assertFalse(any("shields.io" in r["url"] for r in records))
        redis = records[titles.index("C++: Build Your Own Redis")]
        self.assertEqual(redis["body"], "James Smith")

    def test_roadmap_resource_type(self):
        text = "# Hangfire\n\n- [@article@Background jobs with Hangfire](https://example.com/a)\n"
        (record,) = [r for r in refs.parse_markdown(text, sections=False, whole_doc=False) if r["kind"] == "link"]
        self.assertEqual((record["rtype"], record["title"]), ("article", "Background jobs with Hangfire"))

    def test_sections_and_github_anchors(self):
        records = refs.parse_markdown(PROSE, sections=True, whole_doc=False)
        anchors = [r["anchor"] for r in records if r["kind"] == "section"]
        self.assertEqual(anchors, ["caching", "cache-invalidation", "write-through", "cdn", "cdn-1"])
        write_through = next(r for r in records if r["anchor"] == "write-through")
        self.assertEqual(write_through["context"], "Caching › Cache invalidation")

    def test_extract_section_includes_subsections_only(self):
        section = refs.extract_section(PROSE, "cache-invalidation")
        self.assertIn("Write to cache and DB together.", section)
        self.assertNotIn("Edge caches.", section)
        self.assertIn("duplicate heading", refs.extract_section(PROSE, "cdn-1"))

    def test_whole_doc_uses_frontmatter(self):
        records = refs.parse_markdown(PROSE, sections=True, whole_doc=True, context="warp")
        doc = records[0]
        self.assertEqual((doc["title"], doc["anchor"], doc["context"]), ("Warp-design", "", "warp"))
        self.assertTrue(doc["body"].startswith("A warm charcoal canvas."))

    def test_heading_keeps_trailing_hash_in_names(self):
        self.assertEqual(refs.HEADING.match("## C#").group(2), "C#")
        self.assertEqual(refs.HEADING.match("## Title ##").group(2), "Title")


class RoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "repos" / "apis").mkdir(parents=True)
        (root / "repos" / "apis" / "README.md").write_text(CATALOG, encoding="utf-8")
        (root / "repos" / "primer").mkdir(parents=True)
        (root / "repos" / "primer" / "README.md").write_text(PROSE, encoding="utf-8")
        sources = {
            "sources": [
                {"name": "apis", "repo": "example/apis", "include": ["README.md"], "license": "MIT"},
                {"name": "primer", "repo": "example/primer", "include": ["README.md"], "sections": True},
            ]
        }
        (root / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
        self.env = {"REFS_HOME": str(root), "REFS_SOURCES": str(root / "sources.json")}
        self.saved = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        refs.build(log=lambda *_: None)

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def test_search_filters_and_stemming(self):
        hits = refs.search("exchange rate", source="apis", kind="link")
        self.assertEqual(hits[0]["title"], "Frankfurter")
        stemmed = refs.search("invalidating caches", source="primer")
        self.assertEqual(stemmed[0]["title"], "Cache invalidation")

    def test_show_section_and_link(self):
        section = refs.show("primer:README.md#cache-invalidation")
        self.assertIn("Write-through", section["content"])
        self.assertFalse(section["truncated"])
        link = refs.show(refs.search("frankfurter")[0]["id"])
        self.assertEqual(link["url"], "https://www.frankfurter.app/docs")
        self.assertEqual(link["license"], "MIT")

    def test_errors_are_user_facing(self):
        with self.assertRaises(refs.RefsError):
            refs.show("nope")
        with self.assertRaises(refs.RefsError):
            refs.search("cache", kind="bogus")
        with self.assertRaises(refs.RefsError):
            refs.search("?!")

    def test_sources_and_index_info(self):
        names = [s["name"] for s in refs.list_sources()]
        self.assertEqual(names, ["apis", "primer"])
        info = refs.index_info()
        self.assertTrue(info["ready"])
        self.assertGreater(sum(r["count"] for r in info["records"]), 5)


if __name__ == "__main__":
    unittest.main()
