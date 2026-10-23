#!/usr/bin/env python3
"""A small MCP server (stdio, no dependencies) over the build ledger.

Tools
  list_versions   the ledger, newest first; optional filter by deployment or env
  get_version     one build by name ("Dexterity") or image tag
  production      which build production is serving right now
  list_projects   the portfolio: every active project, with its production build and counters
  get_project     one project by slug or name: links, production build, its builds, notes
  render_page     rebuild dist/index.html from versions.json

Run standalone to smoke-test:  echo '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | python3 tools/ledger_mcp.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "versions.json"
PROJECTS = ROOT / "projects.json"
PROTOCOL = "2024-11-05"

TOOLS = [
    {
        "name": "list_versions",
        "description": "List meeting-recorder builds from the ledger, newest first. Each build has a "
                       "human name (Carpal…Dexterity); refer to builds by that name, never by the tag.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "env": {"type": "string", "description": "only builds deployed to this environment: prod, test, integration"},
                "name": {"type": "string", "description": "case-insensitive substring of the build name or commit subject"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20},
            },
        },
    },
    {
        "name": "get_version",
        "description": "One build in full: name, date, image tag, commit subject, change score and where it is deployed.",
        "inputSchema": {
            "type": "object",
            "properties": {"version": {"type": "string", "description": "build name ('Dexterity') or image tag"}},
            "required": ["version"],
        },
    },
    {
        "name": "production",
        "description": "Which build production is serving, with its date and change score.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_projects",
        "description": "The portfolio dashboard as data: every project Simon works on, with status "
                       "(live/code/private), links, production build and build count. Pair with get_project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "case-insensitive filter over name, blurb and tags"},
                "status": {"type": "string", "description": "only projects with this status: live, code, private"},
            },
        },
    },
    {
        "name": "get_project",
        "description": "One project by slug or name: description, links (site, repo), production build "
                       "and the full build list. Same data the dashboard shows when you open a project.",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string", "description": "slug ('screen-pointer') or name ('Screen Pointer')"}},
            "required": ["project"],
        },
    },
    {
        "name": "render_page",
        "description": "Rebuild dist/index.html from versions.json (the single-file page).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def load_projects() -> list[dict]:
    return json.loads(PROJECTS.read_text(encoding="utf-8"))["projects"]


LEDGER_ALIASES = {"meeting recorder": "Meeting recorder", "projects": "Projects"}


def ledger_name(p: dict) -> str:
    return LEDGER_ALIASES.get(p["name"].lower(), p.get("ledgerName") or p["name"])


def project_of(v: dict) -> str:
    name = v.get("name") or ""
    return name.split(" · ")[0].strip() if " · " in name else "Meeting recorder"


def builds_for(data: dict, p: dict) -> list[dict]:
    target = ledger_name(p).lower()
    return [v for v in data["versions"] if project_of(v).lower() == target]


def project_summary(data: dict, p: dict) -> dict:
    builds = builds_for(data, p)
    prod = next((b for b in builds if "prod" in (b.get("deployed") or [])), None)
    return {
        "slug": p["slug"],
        "name": p["name"],
        "blurb": p.get("blurb"),
        "status": p.get("status"),
        "category": p.get("category"),
        "links": p.get("links") or [],
        "production": prod.get("name") if prod else None,
        "builds": len(builds),
        "last_build": builds[-1].get("built") if builds else None,
    }


def project_by_ref(projects: list[dict], ref: str) -> dict | None:
    ref = ref.strip().lower()
    for p in projects:
        if ref in (p["slug"].lower(), p["name"].lower(), ledger_name(p).lower()):
            return p
    return None


def summary(v: dict) -> dict:
    meta = v.get("meta") or {}
    return {
        "name": v.get("name"),
        "built": v.get("built"),
        "subject": v.get("subject"),
        "tag": v["tag"],
        "deployed": v.get("deployed") or [],
        "change_score": (meta.get("ins", 0) + meta.get("del", 0)) or None,
        "rolled_back": v.get("rolledBack"),
    }


def find(data: dict, needle: str) -> dict | None:
    needle = needle.strip().lower()
    for v in data["versions"]:
        if needle == v["tag"].lower() or needle == (v.get("name") or "").lower():
            return v
    for v in data["versions"]:
        if needle in (v.get("name") or "").lower():
            return v
    return None


def text(payload) -> dict:
    body = payload if isinstance(payload, str) else json.dumps(payload, indent=2, ensure_ascii=False)
    return {"content": [{"type": "text", "text": body}]}


def call(name: str, args: dict) -> dict:
    data = load()
    if name == "list_versions":
        env = (args.get("env") or "").lower()
        needle = (args.get("name") or "").lower()
        limit = int(args.get("limit") or 20)
        rows = []
        for v in reversed(data["versions"]):
            if env and env not in (v.get("deployed") or []):
                continue
            if needle and needle not in f"{v.get('name','')} {v.get('subject','')}".lower():
                continue
            rows.append(summary(v))
            if len(rows) >= limit:
                break
        return text(rows)
    if name == "get_version":
        v = find(data, str(args.get("version") or ""))
        return text(summary(v)) if v else text(f"no build called {args.get('version')!r}")
    if name == "production":
        v = next((v for v in data["versions"] if "prod" in (v.get("deployed") or [])), None)
        return text(summary(v) if v else "nothing is marked as deployed to prod")
    if name == "list_projects":
        q = (args.get("query") or "").lower()
        status = (args.get("status") or "").lower()
        out = []
        for p in load_projects():
            if status and (p.get("status") or "").lower() != status:
                continue
            hay = f"{p['name']} {p.get('blurb','')} {' '.join(p.get('tags') or [])} {p.get('category','')}".lower()
            if q and q not in hay:
                continue
            out.append(project_summary(data, p))
        return text(out)
    if name == "get_project":
        p = project_by_ref(load_projects(), str(args.get("project") or ""))
        if not p:
            return text(f"no project called {args.get('project')!r}")
        builds = builds_for(data, p)
        return text({**project_summary(data, p),
                     "note": p.get("note"),
                     "year": p.get("year"),
                     "builds_detail": [summary(v) for v in reversed(builds)]})
    if name == "render_page":
        out = subprocess.run([sys.executable, str(ROOT / "build.py")], capture_output=True, text=True)
        return text((out.stdout or out.stderr).strip())
    return text(f"unknown tool {name}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method, rid = req.get("method"), req.get("id")
        if method == "initialize":
            result = {"protocolVersion": PROTOCOL,
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "build-ledger", "version": "1.0.0"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = req.get("params") or {}
            result = call(params.get("name", ""), params.get("arguments") or {})
        elif method in ("notifications/initialized", "notifications/cancelled"):
            continue
        else:
            result = {}
        if rid is not None:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
