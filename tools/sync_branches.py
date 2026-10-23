#!/usr/bin/env python3
"""Read local Git refs and publish metadata to the private ledger; never fetch or push Git."""
import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

def git(repo, *args):
    return subprocess.check_output(['/usr/bin/git','-C',str(repo),*args],text=True,stderr=subprocess.DEVNULL,timeout=10).strip()

def scan(root):
    branches, errors, repositories = [], [], []
    if not root.is_dir():
        raise RuntimeError('Configured repository directory is unavailable')
    for repo in sorted(root.iterdir()):
        if not repo.is_dir() or not (repo/'.git').exists():
            continue
        repositories.append(repo.name)
        try:
            current = git(repo,'symbolic-ref','--quiet','--short','HEAD')
        except subprocess.CalledProcessError:
            current = ''  # Detached HEAD is not a branch.
        except (OSError,subprocess.TimeoutExpired):
            errors.append(repo.name); continue
        try:
            refs = git(repo,'for-each-ref','--format=%(refname:short)%00%(objectname)%00%(committerdate:iso-strict)%00%(subject)','refs/heads/')
            pending=[]
            for line in refs.splitlines():
                name,commit,date,subject=line.split('\0',3)
                pending.append({'repository':repo.name,'name':name,'commit':commit,'date':date,'subject':subject,'current':name==current})
            branches.extend(pending)
        except (OSError,subprocess.SubprocessError,ValueError):
            errors.append(repo.name)
    return {'schema':1,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'repositories':repositories,'branches':branches,'errors':errors}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=pathlib.Path,default=pathlib.Path.home()/'Developer')
    p.add_argument('--out',type=pathlib.Path,default=ROOT/'.private/branches.json')
    p.add_argument('--publish',action='store_true')
    args=p.parse_args()
    snapshot=scan(args.root)
    encoded=json.dumps(snapshot,ensure_ascii=False)
    if len(encoded.encode())>700000:raise RuntimeError('Branch snapshot exceeds safe ConfigMap size')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    temp=args.out.with_suffix('.tmp');temp.write_text(encoded);temp.replace(args.out)
    if args.publish:
        obj={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'branches','namespace':'build-ledger'},'data':{'branches.json':encoded}}
        subprocess.run(['/usr/bin/ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','ubuntu03',
            'kubectl apply --server-side --field-manager=ledger-branches -f -'],input=json.dumps(obj),text=True,check=True,timeout=40)
    print(f"Scanned {len(snapshot['repositories'])} repositories, {len(snapshot['branches'])} local branches; {len(snapshot['errors'])} unavailable.")

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Branch sync failed ('+type(exc).__name__+'); previous cluster snapshot retained.',file=sys.stderr)
        sys.exit(1)
