#!/usr/bin/env python3
"""A small MCP server (stdio, no dependencies) over the build ledger.

Tools
  list_versions   the ledger, newest first; optional filter by deployment or env
  get_version     one build by name ("Dexterity") or image tag
  production      which build production is serving right now
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
        "name": "render_page",
        "description": "Rebuild dist/index.html from versions.json (the single-file page).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


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
