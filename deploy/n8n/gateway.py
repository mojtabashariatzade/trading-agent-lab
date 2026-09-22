"""Private n8n control bridge. No shell execution, broker or public-message writes.

Network calls are to fixed GitHub/Telegram endpoints only. Workers are separate
processes that must explicitly claim a private job; this module is NOT an AI.
"""
from __future__ import annotations
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib import request, error

REPO = 'mojtabashariatzade/trading-agent-lab'
MAX_BODY = 65536
MAX_RESPONSE = 4 * 1024 * 1024
SECRET = re.compile(r'(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|\d{6,}:[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{16,}|-----BEGIN .*PRIVATE KEY-----|(?:password|api[_-]?key|token)\s*[=:]\s*\S+)', re.I)
ROUTES = {'/v1/sync', '/v1/telegram/poll', '/v1/digest', '/v1/outbox', '/v1/status', '/v1/jobs/claim', '/v1/jobs/result'}


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_text(text: str) -> str:
    return SECRET.sub('[REDACTED]', str(text))[:3500]


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Redirect refused')


def remote_json(url: str, payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = request.Request(url, data=data, headers={'Content-Type': 'application/json', 'User-Agent': 'trading-lab-n8n/1', **(headers or {})})
    try:
        with request.build_opener(NoRedirect).open(req, timeout=20) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise RuntimeError('Response limit exceeded')
        return json.loads(raw)
    except error.HTTPError as exc:
        # Do not include the URL: Telegram tokens occur in the URL path.
        raise RuntimeError('Remote HTTP ' + str(exc.code)) from None
    except (error.URLError, TimeoutError):
        raise RuntimeError('Remote connection failed') from None


class Bridge:
    def __init__(self, state: Path, config: dict, transport=remote_json):
        self.state = Path(state)
        self.state.mkdir(parents=True, exist_ok=True)
        self.config, self.transport = config, transport
        self.poll_lock = threading.Lock()
        self.sync_lock = threading.Lock()
        self.send_lock = threading.Lock()
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS inbox (id INTEGER PRIMARY KEY, body TEXT NOT NULL, at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, kind TEXT NOT NULL,
              body TEXT NOT NULL, status TEXT NOT NULL, lease TEXT, deadline REAL,
              executor TEXT, created_at TEXT NOT NULL, result TEXT);
            CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, body TEXT NOT NULL,
              status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
            ''')
            # A crash after a send may have happened: never blindly resend.
            db.execute("UPDATE outbox SET status='DELIVERY_UNCERTAIN' WHERE status='SENDING'")

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.state / 'bridge.sqlite3', timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, key, default=None):
        with self.db() as db:
            row = db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    @staticmethod
    def put(db, key, value):
        db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)', (key, json.dumps(value)))

    def queue_message(self, db, ident, body):
        db.execute('INSERT OR IGNORE INTO outbox VALUES (?,?,?,0,?)', (ident, safe_text(body), 'PENDING', stamp()))

    def github(self, path):
        if not path.startswith('/repos/' + REPO + '/'):
            raise ValueError('Repository not allowed')
        token = self.config.get('github_read_token', '')
        return self.transport('https://api.github.com' + path, headers={
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            **({'Authorization': 'Bearer ' + token} if token else {})})

    def telegram(self, method, payload):
        if method not in {'getMe', 'getWebhookInfo', 'getUpdates', 'sendMessage'}:
            raise ValueError('Telegram operation not allowed')
        token = self.config.get('telegram_bot_token', '')
        if not token:
            raise RuntimeError('Telegram not configured')
        result = self.transport('https://api.telegram.org/bot' + token + '/' + method, payload)
        if not result.get('ok'):
            raise RuntimeError('Telegram request failed')
        return result['result']

    def sync(self):
        if not self.config.get('github_sync_enabled', False):
            return {'state': 'DISABLED'}
        if not self.sync_lock.acquire(blocking=False):
            return {'state': 'BUSY'}
        try:
            main = self.github('/repos/' + REPO + '/branches/main')['commit']['sha']
            if not re.fullmatch('[0-9a-f]{40}', main):
                raise ValueError('Invalid main revision')
            old = self.get('snapshot', {})
            plan, execution = old.get('plan'), old.get('execution')
            if main != old.get('sha') or plan is None or execution is None:
                docs = []
                for name in ('delivery_plan', 'delivery_state'):
                    obj = self.github('/repos/' + REPO + '/contents/planning/' + name + '.json?ref=' + main)
                    docs.append(json.loads(base64.b64decode(obj['content'], validate=False)))
                plan, execution = docs
            # Paginate; never claim a partial issue list is complete.
            issues, complete = [], False
            for page in range(1, 11):
                batch = self.github('/repos/' + REPO + '/issues?state=open&per_page=100&page=' + str(page))
                if not isinstance(batch, list):
                    raise ValueError('Invalid issue response')
                issues += [{'number': i['number'], 'title': safe_text(i['title']),
                            'kind': 'PR' if 'pull_request' in i else 'Issue'} for i in batch]
                if len(batch) < 100:
                    complete = True
                    break
            snapshot = {'sha': main, 'observed_at': stamp(), 'issues': issues,
                        'issues_complete': complete, 'plan': plan, 'execution': execution}
            fingerprint = hashlib.sha256(json.dumps([main, issues], sort_keys=True).encode()).hexdigest()
            with self.db() as db:
                self.put(db, 'snapshot', snapshot)
                if self.get('last_change') != fingerprint:
                    # Include a monotonically unique event, so A->B->A is not suppressed.
                    self.queue_message(db, 'repo:' + secrets.token_hex(8),
                                       'Raha | GitHub updated: main@' + main[:8] + '\n' + str(len(issues)) + ' open items. Merged is not deployed.')
                    self.put(db, 'last_change', fingerprint)
            return {'state': 'SNAPSHOT_UPDATED', 'sha': main, 'issues_complete': complete}
        finally:
            self.sync_lock.release()

    def status(self):
        snap = self.get('snapshot', {})
        with self.db() as db:
            counts = dict(db.execute('SELECT status, count(*) FROM jobs GROUP BY status').fetchall())
            uncertain = db.execute("SELECT count(*) FROM outbox WHERE status='DELIVERY_UNCERTAIN'").fetchone()[0]
        age = None
        if snap:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(snap['observed_at'])).total_seconds()
        return {'service': 'n8n-control-bridge', 'observed_at': stamp(), 'sha': snap.get('sha'),
                'snapshot_observed_at': snap.get('observed_at'), 'stale': age is None or age > 900,
                'paused': self.get('paused', True), 'jobs': counts, 'delivery_uncertain': uncertain,
                'ai_executor': 'EXTERNAL_WORKER_REQUIRED', 'trading_enabled': False,
                'github_read_only': True}

    def status_text(self):
        s = self.status()
        return ('Raha | main@' + (s['sha'] or 'UNKNOWN')[:8] + '\n'
                + ('STALE' if s['stale'] else 'CURRENT SNAPSHOT') + ' | '
                + ('PAUSED' if s['paused'] else 'REQUEST QUEUE ENABLED')
                + '\nObserved: ' + str(s['snapshot_observed_at'])
                + '\nAI executor: separate connection required. No trading enabled.'
                + '\nJobs: ' + json.dumps(s['jobs']))

    def poll(self):
        if not self.config.get('telegram_polling_enabled', False):
            return {'state': 'DISABLED'}
        receipt = self.config.get('telegram_handoff', {})
        if not receipt.get('old_consumer_stopped') or not receipt.get('verified_by') or not receipt.get('verified_at'):
            raise RuntimeError('Exclusive Telegram handoff receipt required')
        if not self.config.get('telegram_owner_id') or not self.config.get('telegram_chat_id'):
            raise RuntimeError('Owner and private chat are required')
        if not self.poll_lock.acquire(blocking=False):
            return {'state': 'BUSY'}
        try:
            me = self.telegram('getMe', {})
            if me['id'] != receipt.get('bot_id'):
                raise RuntimeError('Handoff belongs to a different bot')
            if self.telegram('getWebhookInfo', {}).get('url'):
                raise RuntimeError('Webhook exists: do not delete or steal it automatically')
            offset = self.get('telegram_offset', 0)
            updates = self.telegram('getUpdates', {'offset': offset, 'limit': 50, 'timeout': 0,
                                                  'allowed_updates': ['message']})
            for update in updates:
                self.ingest(update)
            return {'state': 'POLL_COMPLETE', 'count': len(updates)}
        finally:
            self.poll_lock.release()

    def ingest(self, update):
        ident = int(update['update_id'])
        msg = update.get('message', {})
        author, chat = msg.get('from', {}), msg.get('chat', {})
        permitted = (not author.get('is_bot') and author.get('id') == self.config.get('telegram_owner_id')
                     and chat.get('id') == self.config.get('telegram_chat_id') and chat.get('type') == 'private')
        text = str(msg.get('text') or '').strip()[:12000]
        sent = msg.get('date')
        timely = isinstance(sent, int) and 0 <= time.time() - sent <= 600
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute("SELECT value FROM kv WHERE key='telegram_offset'").fetchone()
            next_offset = max(json.loads(current[0]) if current else 0, ident + 1)
            if permitted and timely and text:
                body = '[SENSITIVE MESSAGE REJECTED]' if SECRET.search(text) else text
                inserted = db.execute('INSERT OR IGNORE INTO inbox VALUES (?,?,?)', (ident, body, stamp())).rowcount
                if inserted:
                    reply = self.handle_text(db, ident, body)
                    self.queue_message(db, 'reply:' + str(ident), reply)
            self.put(db, 'telegram_offset', next_offset)

    def handle_text(self, db, ident, text):
        if text == '[SENSITIVE MESSAGE REJECTED]':
            return 'Secret-like content was not queued. Use the server secret store, not this chat.'
        if text in {'/start', '/help'}:
            return '/status /update /today /pause /resume\nOther text is stored privately for an external assistant. It is not executed as a command.'
        if text in {'/status', '/update', '/team'}:
            return self.status_text()
        if text == '/today':
            return self.today_text()
        if text in {'/pause', '/stop', '/resume'}:
            self.put(db, 'paused', text != '/resume')
            return ('Request handoff paused; monitoring remains available.' if text != '/resume'
                    else 'Private request handoff enabled. No broker, model purchase or trading activated.')
        if text.startswith('/'):
            return 'Unknown command. Use /help. Commands cannot approve trades or deploy code.'
        job = {'request': text, 'origin': 'owner_telegram', 'update_id': ident,
               'scope': 'PROJECT_REQUEST_NOT_EXECUTION_AUTHORITY'}
        db.execute('INSERT OR IGNORE INTO jobs(id,kind,body,status,created_at) VALUES (?,?,?,?,?)',
                   ('telegram:' + str(ident), 'owner_request', json.dumps(job), 'QUEUED', stamp()))
        return 'Request saved privately. It needs an actual connected AI worker; receipt is not evidence work has started.'

    def today_text(self):
        snap = self.get('snapshot', {})
        if not snap:
            return 'No verified GitHub snapshot yet.'
        day = datetime.now(timezone.utc).date().isoformat()
        row = next((r for r in snap['plan'].get('days', []) if r['date'] == day), None)
        if not row:
            return 'No nominal row for this date. Preserve overdue dates and request replanning.'
        tasks = {t['id']: t for t in snap['plan']['tasks']}
        lines = ['Nominal plan, not claimed execution | ' + day + '\nmain@' + snap['sha'][:8]]
        for lane in ('product', 'research'):
            task = tasks[row[lane]]
            lines.append(task['id'] + ' [' + task['priority'] + '] ' + task['title'])
        lines.append('Revalidate dependency evidence before starting. /status shows snapshot freshness.')
        return '\n'.join(lines)

    def digest(self):
        day = datetime.now(timezone.utc).date().isoformat()
        with self.db() as db:
            self.queue_message(db, 'daily:' + day, self.status_text() + '\n\n' + self.today_text())
        return {'state': 'DIGEST_QUEUED', 'date': day}

    def deliver(self):
        if not self.config.get('telegram_sending_enabled', False):
            return {'state': 'DISABLED'}
        if not self.config.get('telegram_chat_id'):
            raise RuntimeError('Private destination not configured')
        if not self.send_lock.acquire(blocking=False):
            return {'state': 'BUSY'}
        try:
            with self.db() as db:
                row = db.execute("SELECT * FROM outbox WHERE status='PENDING' ORDER BY created_at,id LIMIT 1").fetchone()
                if not row:
                    return {'state': 'EMPTY'}
                db.execute("UPDATE outbox SET status='SENDING', attempts=attempts+1 WHERE id=?", (row['id'],))
            try:
                self.telegram('sendMessage', {'chat_id': self.config['telegram_chat_id'], 'text': safe_text(row['body']), 'disable_web_page_preview': True})
            except Exception:
                with self.db() as db:
                    db.execute("UPDATE outbox SET status='DELIVERY_UNCERTAIN' WHERE id=?", (row['id'],))
                raise
            with self.db() as db:
                db.execute("UPDATE outbox SET status='SENT' WHERE id=?", (row['id'],))
            return {'state': 'SENT', 'event_id': row['id']}
        finally:
            self.send_lock.release()

    def claim(self, payload):
        # No automatic invocation of a paid model or arbitrary shell.
        if not self.config.get('worker_handoff_enabled', False) or self.get('paused', True):
            return {'state': 'BLOCKED', 'reason': 'HANDOFF_DISABLED_OR_PAUSED'}
        executor = payload.get('executor', '')
        if not re.fullmatch('[A-Za-z0-9_.-]{1,80}', executor):
            raise ValueError('Named executor required')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE jobs SET status='REVIEW_REQUIRED' WHERE status='WORKING' AND deadline<?", (time.time(),))
            if db.execute("SELECT 1 FROM jobs WHERE status IN ('WORKING','REVIEW_REQUIRED','RESULT_SUBMITTED')").fetchone():
                return {'state': 'BLOCKED', 'reason': 'WIP_OR_UNRESOLVED_RECEIPT'}
            job = db.execute("SELECT * FROM jobs WHERE status='QUEUED' ORDER BY created_at LIMIT 1").fetchone()
            if not job:
                return {'state': 'EMPTY'}
            lease = secrets.token_urlsafe(32)
            db.execute("UPDATE jobs SET status='WORKING',lease=?,deadline=?,executor=? WHERE id=?", (lease, time.time()+900, executor, job['id']))
            return {'state': 'CLAIMED', 'job_id': job['id'], 'lease': lease,
                    'body': json.loads(job['body']), 'deadline_seconds': 900}

    def result(self, payload):
        ident, lease = payload.get('job_id'), payload.get('lease', '')
        ref, summary = payload.get('evidence_url', ''), payload.get('summary', '')
        if not re.fullmatch(r'https://github\.com/mojtabashariatzade/trading-agent-lab/(pull/[0-9]+|issues/[0-9]+|commit/[0-9a-f]{40})', ref):
            raise ValueError('Repository-scoped evidence URL required')
        if not isinstance(summary, str) or not summary.strip() or SECRET.search(summary):
            raise ValueError('Safe summary required')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            job = db.execute('SELECT * FROM jobs WHERE id=?', (ident,)).fetchone()
            if not job or job['status'] != 'WORKING' or job['deadline'] < time.time() or not hmac.compare_digest(job['lease'], str(lease)):
                raise ValueError('Invalid or expired lease; reconcile before retrying')
            db.execute("UPDATE jobs SET status='RESULT_SUBMITTED',result=? WHERE id=?", (json.dumps({'summary': summary[:3000], 'evidence_url': ref}), ident))
            self.queue_message(db, 'job:' + ident, 'Worker receipt (not independently verified):\n' + summary + '\n' + ref)
        return {'state': 'RESULT_SUBMITTED', 'verification': 'REVIEW_REQUIRED_NOT_DONE'}


def make_handler(bridge, control_key: str, worker_key: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log URLs, payloads, tokens or private messages.
        def answer(self, code, body):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def do_GET(self):
            self.answer(200 if self.path == '/healthz' else 404, {'state': 'ALIVE' if self.path == '/healthz' else 'NOT_FOUND'})
        def do_POST(self):
            if self.path not in ROUTES:
                return self.answer(404, {'error': 'NOT_FOUND'})
            key = worker_key if self.path.startswith('/v1/jobs/') else control_key
            if not key or not hmac.compare_digest(self.headers.get('X-Control-Key', ''), key):
                return self.answer(401, {'error': 'UNAUTHORIZED'})
            try:
                length = int(self.headers.get('Content-Length', '-1'))
                if length < 0 or length > MAX_BODY:
                    return self.answer(413, {'error': 'INVALID_BODY_SIZE'})
                payload = json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(payload, dict):
                    raise ValueError('Object required')
                actions = {'/v1/sync': bridge.sync, '/v1/telegram/poll': bridge.poll,
                           '/v1/digest': bridge.digest, '/v1/outbox': bridge.deliver, '/v1/status': bridge.status}
                result = (bridge.claim(payload) if self.path.endswith('/claim') else
                          bridge.result(payload) if self.path.endswith('/result') else actions[self.path]())
                self.answer(200, result)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                self.answer(400, {'error': 'INVALID_INPUT'})
            except Exception:
                self.answer(503, {'error': 'DEPENDENCY_FAILED', 'action': self.path})
    return Handler


if __name__ == '__main__':
    config = json.loads(Path('/run/secrets/connections').read_text())
    bridge = Bridge(Path('/state'), config)
    handler = make_handler(bridge, Path('/run/secrets/control_key').read_text().strip(),
                           Path('/run/secrets/worker_key').read_text().strip())
    ThreadingHTTPServer(('0.0.0.0', 8080), handler).serve_forever()
