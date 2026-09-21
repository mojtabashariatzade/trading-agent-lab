"""Approved operator deployment through host-key-verified SSH. No server yet.

No SSH action occurs without --deploy-approved. Credentials stay in the operator's
secure key file/agent, never in this repository, command output or package.
"""
from __future__ import annotations
import argparse
import io
from pathlib import Path
import re
import shlex
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent
FILES = ['compose.json','Dockerfile','gateway.py','install.py','init-postgres.sh',
         'workflows.json','bootstrap-ubuntu.sh','.dockerignore','.gitignore','README.md']


def host_target(host, user):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', host):
        raise ValueError('Use a validated IPv4 address or hostname, not a shell expression')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', user):
        raise ValueError('Invalid SSH user')
    return user + '@' + host


def bundle():
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w:gz') as tf:
        for name in FILES:
            path = ROOT / name
            if path.is_symlink() or not path.is_file():
                raise ValueError('Missing or unsafe package member: ' + name)
            tf.add(path, arcname=name, recursive=False)
    return out.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--user', default='root')
    parser.add_argument('--port', type=int, default=22)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--known-hosts', type=Path, required=True)
    parser.add_argument('--owner-email', required=True)
    parser.add_argument('--security-reviewed-on', required=True)
    parser.add_argument('--fresh-ubuntu-approved', action='store_true')
    parser.add_argument('--deploy-approved', action='store_true')
    args = parser.parse_args()
    target = host_target(args.host, args.user)
    if not (1 <= args.port <= 65535):
        parser.error('Invalid port')
    if not args.deploy_approved:
        print('PREVIEW ONLY: package prepared; no server contact or deployment performed.')
        return
    if not args.key_file.is_file() or not args.known_hosts.is_file():
        parser.error('Secure SSH key and independently verified known_hosts entry required')
    ssh = ['ssh','-p',str(args.port),'-i',str(args.key_file),'-o','BatchMode=yes',
           '-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',
           '-o','UserKnownHostsFile='+str(args.known_hosts),'-o','ConnectTimeout=15',target]
    # New dedicated path only: do not overwrite an existing deployment or secrets.
    command = 'umask 077; mkdir "$HOME/trading-lab-n8n" && tar --no-same-owner -xzf - -C "$HOME/trading-lab-n8n"'
    subprocess.run(ssh + [command], input=bundle(), check=True, timeout=60)
    sudo = '' if args.user == 'root' else 'sudo -n '
    if args.fresh_ubuntu_approved:
        subprocess.run(ssh + ['cd "$HOME/trading-lab-n8n" && ' + sudo + 'sh bootstrap-ubuntu.sh --fresh-server-approved'],
                       check=True, timeout=600)
    for action, extra in [('prepare', '--owner-email ' + shlex.quote(args.owner_email)),
                           ('apply','--security-reviewed-on ' + shlex.quote(args.security_reviewed_on))]:
        cmd = 'cd "$HOME/trading-lab-n8n" && ' + sudo + 'python3 install.py ' + action + ' --approved ' + extra
        subprocess.run(ssh + [cmd], check=True, timeout=600)
    print('Install command completed. Verify receipt/readiness before enabling integrations or schedules.')


if __name__ == '__main__':
    main()
