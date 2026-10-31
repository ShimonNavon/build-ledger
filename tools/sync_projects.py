#!/usr/bin/env python3
"""Pull the curated project catalogue out of the portfolio site into projects.json.

The gallery at ~/Developer/my-projects/site/index.html already holds the human truth: name,
one-liner, links, tags, and whether a project is live, public code, or private. The ledger reuses it
so both sites tell the same story — this script only extracts it, it never invents anything.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

SRC = pathlib.Path.home() / "Developer/my-projects/site/index.html"
OUT = pathlib.Path(__file__).resolve().parent.parent / "projects.json"

# Ledger names are shorter than gallery names; this is the only hand-kept mapping.
LEDGER_NAMES = {
    "Meeting Recorder · מקליט ביקורים": "Meeting recorder",
    "Projects": "Projects",
}

# Renamed projects keep the slug their links and app URLs already use.
SLUGS = {
    "SETA": "seta",
    "Nativ · נתיב": "imports-crm",
    "Naki · נקי": "naki",
}

def entries(html: str) -> list[str]:
    i = html.index("const P = [")
    i = html.index("{", i)
    depth, start, out = 0, i, []
    for j in range(i, len(html)):
        c = html[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                out.append(html[start:j + 1])
                nxt = html.find("{", j + 1)
                if nxt == -1:
                    break
                start, j = nxt, nxt
    return out

def field(e: str, key: str) -> str:
    m = re.search(key + r":\s*'([^']*)'", e)
    return m.group(1) if m else ""

def links(e: str) -> list[dict]:
    m = re.search(r"links:\s*\[", e)
    if not m:
        return []
    i, depth = m.end() - 1, 0
    for j in range(i, len(e)):
        if e[j] == "[":
            depth += 1
        elif e[j] == "]":
            depth -= 1
            if depth == 0:
                block = e[i + 1:j]
                break
    else:
        return []
    out = []
    for label, url in re.findall(r"\[\s*'([^']*)'\s*,\s*([^\]]+)\]", block):
        url = url.strip()
        gh = re.match(r"GH\('([^']+)'\)", url)
        if gh:
            url = "https://github.com/ShimonNavon/" + gh.group(1)
        else:
            url = url.strip("'\"")
        if url.startswith("/"):
            url = "https://projects.navonsimon.com" + url
        out.append({"label": label, "url": url})
    return out


def slug(name: str) -> str:
    base = SLUGS.get(name) or LEDGER_NAMES.get(name, name)
    s = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return s or "project"

def main() -> None:
    html = SRC.read_text()
    projects = []
    for e in entries(html):
        name = field(e, "t")
        if not name:
            continue
        projects.append({
            "slug": slug(name),
            "name": name,
            "ledgerName": LEDGER_NAMES.get(name, name),
            "blurb": field(e, "d"),
            "category": field(e, "cat"),
            "status": field(e, "s"),          # live | code | private
            "img": field(e, "img"),
            "emoji": field(e, "em"),
            "tags": re.findall(r"'([^']+)'", (re.search(r"tags:\s*\[(.*?)\]", e, re.S) or [None, ""])[1]),
            "links": links(e),
            "note": field(e, "note"),
            "year": int(m.group(1)) if (m := re.search(r"y:\s*(\d{4})", e)) else None,
        })
    if not any(p["ledgerName"] == "Projects" for p in projects):
        projects.insert(0, {
            "slug": "my-projects",
            "name": "My projects",
            "ledgerName": "Projects",
            "blurb": "The portfolio behind projects.navonsimon.com: every project, its story and how to reach it, kept in step with this ledger.",
            "category": "personal",
            "status": "live",
            "img": "",
            "emoji": "🗂️",
            "tags": ["Portfolio", "Ledger"],
            "links": [{"label": "Open portfolio", "url": "https://projects.navonsimon.com/"}],
            "note": "",
            "year": 2026,
        })
    OUT.write_text(json.dumps({"projects": projects}, indent=2, ensure_ascii=False) + "\n")
    print(f"{OUT} · {len(projects)} projects")

if __name__ == "__main__":
    sys.exit(main())
