#!/bin/sh
# Render the page, ship it to the cluster (ns build-ledger, NodePort 30096 on ubuntu04).
set -e
cd "$(dirname "$0")/.."
ssh ubuntu03 'kubectl -n build-ledger get secret access -o name >/dev/null'
python3 tools/sync_branches.py --publish
python3 build.py
{
  cat deploy/app.yaml; echo ---
  python3 - <<'PY'
import json, pathlib
page = pathlib.Path('dist/index.html').read_text()
print(json.dumps({'apiVersion': 'v1', 'kind': 'ConfigMap',
                  'metadata': {'name': 'site', 'namespace': 'build-ledger'},
                  'data': {'index.html': page}}, ensure_ascii=False))
PY
} | ssh ubuntu03 'kubectl apply --server-side --force-conflicts -f - && kubectl -n build-ledger rollout restart deploy/web && kubectl -n build-ledger rollout status deploy/web --timeout=120s'
