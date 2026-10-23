#!/usr/bin/env python3
"""Install a login LaunchAgent that publishes branch metadata every minute."""
import os,pathlib,plistlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[1]
private=root/'.private';private.mkdir(exist_ok=True);private.chmod(0o700)
label='com.simon.build-ledger-branches'
path=pathlib.Path.home()/'Library/LaunchAgents'/f'{label}.plist'
path.parent.mkdir(parents=True,exist_ok=True)
body={'Label':label,'ProgramArguments':[sys.executable,str(root/'tools/sync_branches.py'),'--publish'],
      'RunAtLoad':True,'StartInterval':60,'WorkingDirectory':str(root),
      'EnvironmentVariables':{'PATH':'/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin'},
      'StandardOutPath':str(private/'branch-sync.log'),'StandardErrorPath':str(private/'branch-sync-error.log')}
if path.exists():subprocess.run(['launchctl','bootout',f'gui/{os.getuid()}',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
path.write_bytes(plistlib.dumps(body));path.chmod(0o600)
subprocess.run(['launchctl','bootstrap',f'gui/{os.getuid()}',str(path)],check=True)
print('Installed minute-by-minute branch sync for this macOS login.')
