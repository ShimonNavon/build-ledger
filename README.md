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

## Private access (October 23, 2026)

Open **https://builds.navonsimon.com/** while connected to Simon's Tailscale network.
The DNS-only A record points at ubuntu01's Tailscale address. The former public
Cloudflare Tunnel hostname route was removed; the public edge returns 403 for
this host. Public internet clients cannot route to the private endpoint.

The dedicated nginx gateway on ubuntu01 binds **only** its Tailscale address on
443 and allows tailnet source addresses. It proxies to the existing Kubernetes
app on ubuntu04. The cluster CNI masks remote addresses, so the backend also
requires a random gateway header stored in Kubernetes Secret `access` and in the
private gateway's configuration. Direct NodePort requests without it return 403.
The unauthenticated `/healthz` endpoint exposes only `ok` for readiness checks.
Membership and device access remain controlled by the tailnet's existing policy.

Gateway files: `/home/simon/build-ledger-private` on ubuntu01. TLS is issued by
Let's Encrypt using Cloudflare DNS validation; the certificate is renewed daily
at 04:23 server time by `renew.sh`, followed by nginx reload. The credentials file
is mode 0600 in a mode 0700 secrets folder, never served by nginx or committed.
The first certificate expires January 21, 2027. Renewal failures are logged to
`renew.log`; no external alert is configured.

Repository templates: `deploy/private-edge.conf`, `deploy/backend.conf`,
`deploy/private-compose.yml`, `deploy/renew-private-tls.sh`. Replace the gateway
token placeholder only at deployment; `.private/` is ignored. Regular site
publishing preserves the existing gateway Secret and fails if it is missing.
`deploy/private_dns.py` manages the DNS-only record, removes the public tunnel
route and purges its cached root URL using runtime Cloudflare credentials.

Browsers that cached the former public endpoint can briefly show a Cloudflare
error until DNS/connection caches expire. Do not re-enable Cloudflare proxying:
the hostname must resolve directly to the tailnet address.

## Automatic Git branch tracking

The Git branches section reads a separate live snapshot from `/branches/branches.json` every 30 seconds. The macOS LaunchAgent `com.simon.build-ledger-branches` scans Git repositories immediately under `~/Developer` every 60 seconds while the user is logged in and the Mac is awake. It reports local branch names, latest commit time/subject/ID, and the currently checked-out branch. It never fetches, pushes, changes branches, reads file contents, or publishes repository paths or remote credentials. Remote-only branches appear once checked out locally. Linked worktrees are supported.

Create, rename and delete operations are picked up automatically. This does not mark a branch as deployed: build history and deployment records remain in `versions.json`. Unreadable repositories are reported by name instead of silently appearing empty. An offline Mac or failed SSH keeps the last successful snapshot; after four minutes the page marks updates as delayed. Updates typically arrive within one to three minutes, including Kubernetes volume propagation.

Install/update the sync from the canonical repository, not a temporary clone:

```sh
cd ~/Developer/build-ledger
python3 tools/sync_branches.py --publish
python3 tools/install_branch_sync.py
```

The snapshot is a dedicated ConfigMap mounted by directory, so updates require no app restart. It inherits the existing private gateway protection. Logs and the local snapshot are under ignored `.private/`. Stop the job with `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.simon.build-ledger-branches.plist`; reinstall to resume. Run the focused lifecycle test with `python3 -m unittest discover -s tests`.
