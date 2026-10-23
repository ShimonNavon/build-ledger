# Build ledger

A single-file page that answers "which build is where, and what changed in it" — plus a small
MCP server so an agent can answer the same question without opening a browser.

It came out of reviewing meeting-recorder deploys: the table was useful, but the raw git hashes and
image tags meant nothing to the person reading it.

## The ideas it encodes

- **Date first.** A table of builds is a chronological record; the date column leads.
- **Names, not hashes.** Every build has a human name from a themed word list (Carpal … Dexterity).
  The image tag is still there for copying, never as the label.
- **One change score per row.** Total lines churned (insertions + deletions), colour-coded by
  severity: green < 100, neutral 100–399, amber 400–999, red ≥ 1000. Hover shows +/−/files.
- **Looking is a gesture.** Hovering a row makes its emoji wave and say something. Clicking a row
  copies its one-line description and highlights it for the session. Two-finger click cycles the
  highlight (none → yellow → blue).
- **Notes are loud.** A note is a sticky-note block pinned under the build, with a zoomed, centred
  editor (⌘⏎ save, esc cancel, click outside saves).

## Layout

```
versions.json      the ledger: versions, names, deploy targets, change numbers, notes, rollbacks
template.html      the page's look and behaviour, with __PLACEHOLDERS__ for the data
build.py           versions.json + template.html -> dist/index.html
tools/ledger_mcp.py  stdio MCP server (no dependencies)
dist/index.html    the rendered page (open this)
```

## Use it

```bash
python3 build.py --open          # render and open in Chrome
open -a "Google Chrome" dist/index.html
```

Edit `versions.json` (usually just append a version), then rebuild. Everything else — sorting,
filtering, copy, highlights, notes — happens in the browser and stays local to it.

## MCP

`tools/ledger_mcp.py` speaks MCP over stdio. Tools:

| tool | what it answers |
| --- | --- |
| `list_versions` | builds, newest first; filter by environment or name |
| `get_version` | one build by name or tag |
| `production` | what production is serving right now |
| `render_page` | rebuild `dist/index.html` |

Registered in `~/.config/opencode/opencode.jsonc` as `build-ledger`. Smoke test:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | python3 tools/ledger_mcp.py
```

## Keeping it honest

The ledger is only as true as its last edit. When a build is deployed, rolled back or renamed, update
`versions.json` and rebuild — the page is a record, not a live query.
