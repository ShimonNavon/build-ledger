#!/usr/bin/env python3
"""Render versions.json into a single, self-contained HTML page.

    python3 build.py                    # dist/index.html
    python3 build.py --open             # ...and open it in Chrome
    python3 build.py --out /tmp/v.html  # somewhere else

The template holds the look and the behaviour; versions.json holds the ledger.
Nothing is fetched at runtime, so the output works from a file:// URL.
"""
from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
DATA = HERE / "versions.json"
PROJECTS = HERE / "projects.json"
DEFAULT_OUT = HERE / "dist" / "index.html"


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"{path}: not valid JSON ({exc})")
    if not isinstance(data.get("versions"), list) or not data["versions"]:
        sys.exit(f"{path}: needs a non-empty 'versions' list")
    return data


def rows_for_js(data: dict) -> list[dict]:
    keys = ("tag", "built", "commit", "subject", "deployed")
    return [{**{k: v.get(k, "") for k in keys}, "deployed": v.get("deployed") or []} for v in data["versions"]]


def prod_card(data: dict) -> str:
    """The little card in the header: which build production is serving."""
    prod = next((v for v in data["versions"] if "prod" in (v.get("deployed") or [])), None)
    if prod is None:
        return ""
    name = html.escape(prod.get("name") or "")
    built = html.escape(prod.get("built") or "")
    date, _, clock = built.partition(" ")
    meta = html.escape((prod.get("subject") or "")[:64])
    return f'''<div class="prod-card" title="Live on production ({html.escape(prod["tag"])})">
        <span class="prod-dot"></span>
        <div>
          <div class="prod-label">Production · {html.escape((prod.get("name") or "").split(" · ")[0] or "app")}</div>
          <div class="prod-ver">{name}</div>
          <div class="prod-meta">{date}, {clock} build · {meta}</div>
        </div>
      </div>'''


def render(template: str, data: dict) -> str:
    names = data.get("names") or [v.get("name", "") for v in data["versions"]]
    meta = {v["tag"]: v["meta"] for v in data["versions"] if v.get("meta")}
    rolled = {v["tag"]: v["rolledBack"] for v in data["versions"] if v.get("rolledBack")}
    values = {
        "__ROWS__": json.dumps(rows_for_js(data), ensure_ascii=False),
        "__VERSIONNAMES__": json.dumps(names, ensure_ascii=False),
        "__QUIPS__": json.dumps(data.get("quips") or [], ensure_ascii=False),
        "__COMMITMETA__": json.dumps(meta, ensure_ascii=False),
        "__ROLLEDBACK__": json.dumps(rolled, ensure_ascii=False),
        "__PROD_CARD__": prod_card(data),
        "__PROJECTS__": json.dumps(json.loads(PROJECTS.read_text(encoding="utf-8"))["projects"], ensure_ascii=False),
    }
    out = template
    for key, value in values.items():
        if key not in out:
            sys.exit(f"template is missing {key}")
        out = out.replace(key, value)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--template", type=Path, default=TEMPLATE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--open", action="store_true", help="open the result in Chrome")
    args = ap.parse_args()

    data = load(args.data)
    page = render(args.template.read_text(encoding="utf-8"), data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(f"{args.out} · {len(data['versions'])} versions")
    if args.open:
        subprocess.run(["open", "-a", "Google Chrome", str(args.out)], check=False)


if __name__ == "__main__":
    main()
