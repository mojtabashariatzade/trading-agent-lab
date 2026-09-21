"""Operator-facing staged installer. Default action is a read-only preflight.

Use only after the owner authorizes deployment on the named server. External
integrations remain off until configured separately. No secrets printed.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time
from urllib import request, error

ROOT = Path(__file__).resolve().parent
REVIEWED_ON = date(2026, 9, 22)
N8N_VERSION = '2.39.10'
IMAGES = {'N8N_IMAGE': 'docker.n8n.io/n8nio/n8n:' + N8N_VERSION,
          'POSTGRES_IMAGE': 'postgres:16-alpine', 'PYTHON_IMAGE': 'python:3.13-slim-bookworm'}
IDS = ['tradingLabSync001', 'tradingLabPoll001', 'tradingLabSend001', 'tradingLabDaily01']


def run(*args, capture=False):
    proc = subprocess.run(list(args), cwd=ROOT, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode:
        # CLI output may contain credentials; keep it off the public transcript.
        raise RuntimeError('Command failed: ' + args[0] + ' (exit ' + str(proc.returncode) + ')')
    return proc.stdout if capture else None


def compose(*args, capture=False):
    return run('docker', 'compose', '--project-name', 'trading-lab-n8n', '--env-file',
               str(ROOT / '.private/images.env'), '-f', str(ROOT / 'compose.json'), *args, capture=capture)


def assert_review(reviewed: date):
    age = (date.today() - reviewed).days
    if age < 0 or age > 7:
        raise ValueError('Version/security review is stale. Recheck upstream releases/advisories before installation.')


def private_write(path: Path, value: str, mode=0o444):
    # Parent is private. Files mounted as Docker secrets must be readable by UID 1000.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        fh.write(value)
    os.chmod(path, mode)


def prepare(email: str, root: Path = ROOT):
    if not email or '@' not in email or any(c.isspace() for c in email):
        raise ValueError('Owner email required')
    p = root / '.private'
    marker = p / 'prepared.json'
    required = ('pg_root', 'pg_app', 'encryption', 'control_key', 'worker_key', 'connections',
                'bootstrap_credentials.json', 'owner.json', 'images.env')
    if marker.exists():
        if not all((p / name).is_file() for name in required):
            raise RuntimeError('Partial state: preserve existing encryption keys; reconcile before retrying')
        return 'EXISTING_KEYS_PRESERVED'
    if p.exists():
        raise RuntimeError('Unmarked private directory: do not overwrite existing secrets')
    p.mkdir(mode=0o700)
    os.chmod(p, 0o700)
    keys = {name: secrets.token_hex(32) for name in ('pg_root','pg_app','encryption','control_key','worker_key')}
    for name, val in keys.items():
        private_write(p / name, val)
    private_write(p / 'owner.json', json.dumps({'email': email, 'firstName': 'Trading', 'lastName': 'Lab',
                                               'password': 'Aa9!' + secrets.token_urlsafe(32)}), 0o600)
    private_write(p / 'connections', json.dumps({
        'github_sync_enabled': False, 'github_read_token': '',
        'telegram_sending_enabled': False, 'telegram_polling_enabled': False,
        'telegram_bot_token': '', 'telegram_owner_id': None, 'telegram_chat_id': None,
        'telegram_handoff': {'old_consumer_stopped': False, 'bot_id': None, 'verified_by': '', 'verified_at': ''},
        'worker_handoff_enabled': False}, indent=2))
    private_write(p / 'bootstrap_credentials.json', json.dumps([{
        'id': 'tradingLabBridge1', 'name': 'Trading Lab private bridge', 'type': 'httpHeaderAuth',
        'data': {'name': 'X-Control-Key', 'value': keys['control_key']}}]))
    private_write(p / 'images.env', '\n'.join(k+'='+v for k,v in IMAGES.items())+'\n', 0o600)
    private_write(marker, json.dumps({'prepared_at': datetime.now(timezone.utc).isoformat(),
                                     'version': N8N_VERSION}), 0o600)
    return 'PREPARED_NO_SERVICES_STARTED'


def wait_ready(timeout=120):
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        try:
            with request.urlopen('http://127.0.0.1:5678/healthz/readiness', timeout=3) as resp:
                if resp.status == 200:
                    return
        except (error.URLError, TimeoutError):
            pass
        time.sleep(2)
    raise RuntimeError('n8n readiness did not pass')


def exported():
    compose('run', '--rm', '--no-deps', 'n8n', 'export:workflow', '--all',
            '--output=/home/node/.n8n/workflows-audit.json')
    raw = compose('exec', '-T', 'n8n', 'cat', '/home/node/.n8n/workflows-audit.json', capture=True)
    rows = json.loads(raw)
    if not isinstance(rows, list):
        raise RuntimeError('Cannot verify imported workflows')
    return {row['id']: row for row in rows}


def apply(reviewed: date):
    assert_review(reviewed)
    if not (ROOT / '.private/prepared.json').exists():
        raise RuntimeError('Run prepare with a verified owner email first')
    if (ROOT / '.private/installed.json').exists():
        raise RuntimeError('Already installed: use status. Upgrades require a backup and new reviewed release.')
    run('docker', 'compose', 'version')
    compose('config', '--quiet')
    compose('pull', 'db', 'n8n')
    run('docker', 'pull', IMAGES['PYTHON_IMAGE'])
    # Resolve mutable upstream tags once, then pin the deployment to actual digests.
    locked = {}
    for name, image in IMAGES.items():
        digests = json.loads(run('docker', 'image', 'inspect', image, '--format', '{{json .RepoDigests}}', capture=True))
        if not digests:
            raise RuntimeError('Image digest missing')
        locked[name] = digests[0]
    (ROOT / '.private/images.env').write_text('\n'.join(k+'='+v for k,v in locked.items())+'\n')
    os.chmod(ROOT / '.private/images.env', 0o600)
    compose('build', 'bridge')
    compose('up', '-d', '--wait', '--wait-timeout', '180')
    wait_ready()
    marker = ROOT / '.private/owner-created.json'
    if not marker.exists():
        payload = (ROOT / '.private/owner.json').read_bytes()
        req = request.Request('http://127.0.0.1:5678/rest/owner/setup', data=payload,
                              headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read())
            if not result.get('data', {}).get('id'):
                raise RuntimeError('Owner setup response invalid')
            private_write(marker, json.dumps({'id': result['data']['id']}), 0o600)
        except error.HTTPError:
            raise RuntimeError('Owner setup refused; do not reset an existing owner/database') from None
    # Import only on this new dedicated instance, with schedules disabled.
    compose('stop', 'n8n')
    compose('run', '--rm', '--no-deps', 'n8n', 'import:credentials', '--input=/run/secrets/bootstrap_credentials')
    compose('run', '--rm', '--no-deps', 'n8n', 'import:workflow', '--input=/bootstrap/workflows.json', '--activeState=false')
    compose('up', '-d', 'n8n')
    wait_ready()
    rows = exported()
    if set(rows) != set(IDS) or any(rows[i].get('active') or rows[i].get('activeVersionId') for i in IDS):
        raise RuntimeError('Import verification failed; do not activate schedules')
    receipt = {'state': 'INSTALLED_INACTIVE', 'at': datetime.now(timezone.utc).isoformat(),
               'images': locked, 'workflows': IDS, 'live_trading': False,
               'telegram_handoff': 'NOT_PERFORMED', 'ai_worker': 'NOT_CONNECTED'}
    private_write(ROOT / '.private/installed.json', json.dumps(receipt, indent=2), 0o600)
    return receipt


def activate():
    if not (ROOT / '.private/installed.json').exists():
        raise RuntimeError('Verified installation receipt required')
    # Publishing starts only orchestration schedules. External integrations stay
    # separately disabled in .private/connections until an operator configures them.
    compose('stop', 'n8n')
    for ident in IDS:
        compose('run', '--rm', '--no-deps', 'n8n', 'publish:workflow', '--id=' + ident)
    compose('up', '-d', 'n8n')
    wait_ready()
    rows = exported()
    if any(not (rows.get(ident, {}).get('active') or rows.get(ident, {}).get('activeVersionId')) for ident in IDS):
        raise RuntimeError('Activation could not be verified')
    return {'state': 'SCHEDULES_ACTIVE', 'integrations': 'CONFIGURED_SEPARATELY', 'trading_enabled': False}


def backup(destination: Path):
    # Quiesce all writers first. The backup contains secrets: keep private/off-repo.
    destination = destination.resolve()
    if destination.exists():
        raise ValueError('Backup destination must not exist')
    destination.mkdir(mode=0o700, parents=True)
    compose('stop', 'n8n', 'bridge')
    try:
        sql = compose('exec', '-T', 'db', 'pg_dump', '-U', 'postgres', '-d', 'n8n', capture=True)
        private_write(destination / 'n8n.sql', sql, 0o600)
        shutil.copytree(ROOT / '.private', destination / 'private')
        for service, path in (('bridge','/state'), ('n8n','/home/node/.n8n')):
            container = compose('ps', '-aq', service, capture=True).strip()
            if not container or '\n' in container:
                raise RuntimeError('Backup requires exactly one instance of each service')
            run('docker', 'cp', container + ':' + path, str(destination / service))
        private_write(destination / 'BACKUP.json', json.dumps({'at': stamp_now(), 'state':'SNAPSHOT_CREATED_RESTORE_NOT_TESTED'}), 0o600)
    finally:
        compose('up', '-d', 'n8n', 'bridge')
    return {'state': 'LOCAL_BACKUP_CREATED', 'restore_tested': False}


def stamp_now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='preflight', choices=['preflight','prepare','apply','activate','status','backup'])
    parser.add_argument('--owner-email')
    parser.add_argument('--approved', action='store_true')
    parser.add_argument('--security-reviewed-on', type=date.fromisoformat, default=REVIEWED_ON)
    parser.add_argument('--backup-dir', type=Path)
    args = parser.parse_args()
    if args.action == 'preflight':
        print(json.dumps({'target':'fresh Linux server with Docker Compose v2', 'n8n':N8N_VERSION,
                          'reviewed_on':str(REVIEWED_ON), 'docker_available':bool(shutil.which('docker')),
                          'network_bound':'127.0.0.1:5678 only', 'state':'PREPARED_NOT_DEPLOYED'}, indent=2))
        return
    if args.action == 'status':
        print(compose('ps', '--format', 'json', capture=True))
        return
    if not args.approved:
        parser.error('Explicit --approved is required; preparation does not grant deployment authority')
    result = (prepare(args.owner_email) if args.action == 'prepare' else
              apply(args.security_reviewed_on) if args.action == 'apply' else
              activate() if args.action == 'activate' else
              backup(args.backup_dir) if args.backup_dir else None)
    if result is None:
        parser.error('--backup-dir is required')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('BLOCKED: ' + str(exc))
        raise SystemExit(1)
