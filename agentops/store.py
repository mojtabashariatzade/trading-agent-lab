"""Single-controller durable state. No state is stored in the coding repo."""
import json
from pathlib import Path
import sqlite3
import time


class Store:
    def __init__(self, path):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, data TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS research_tasks(id TEXT PRIMARY KEY, data TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS launches(id TEXT PRIMARY KEY, day TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS updates(id INTEGER PRIMARY KEY);
          CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, kind TEXT, data TEXT);
          CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, text TEXT, buttons TEXT, delivered INTEGER DEFAULT 0);
        """)
        self.db.commit()

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.db:
            self.db.execute("INSERT INTO kv VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    def task(self, task_id):
        row = self.db.execute("SELECT data FROM tasks WHERE id=?", (task_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def tasks(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT data FROM tasks ORDER BY id")]

    def save(self, task):
        with self.db:
            self.db.execute("INSERT INTO tasks VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (task["id"], json.dumps(task)))

    def research(self, research_id):
        row = self.db.execute("SELECT data FROM research_tasks WHERE id=?", (research_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def research_tasks(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT data FROM research_tasks ORDER BY id")]

    def save_research(self, task):
        with self.db:
            self.db.execute(
                "INSERT INTO research_tasks VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (task["id"], json.dumps(task)),
            )

    def audit(self, kind, data):
        with self.db:
            self.db.execute("INSERT INTO audit(at,kind,data) VALUES(?,?,?)", (time.time(), kind, json.dumps(data)))

    def reserve(self, launch_id, day, limit):
        with self.db:
            if self.db.execute("SELECT 1 FROM launches WHERE id=?", (launch_id,)).fetchone():
                return True
            count = self.db.execute("SELECT COUNT(*) FROM launches WHERE day=?", (day,)).fetchone()[0]
            if count >= limit:
                return False
            self.db.execute("INSERT INTO launches VALUES(?,?)", (launch_id, day))
        return True

    def launch_count(self, day):
        return self.db.execute("SELECT COUNT(*) FROM launches WHERE day=?", (day,)).fetchone()[0]

    def seen_update(self, update_id):
        return bool(self.db.execute("SELECT 1 FROM updates WHERE id=?", (update_id,)).fetchone())

    def consume_update(self, update_id):
        # Consume before side effects. Ambiguous mutations are reconciled from task state.
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO updates VALUES(?)", (update_id,))
        self.set("telegram_offset", max(self.get("telegram_offset", 0), update_id + 1))

    def notify(self, key, text, buttons=None):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO outbox(id,text,buttons) VALUES(?,?,?)", (key, text, json.dumps(buttons)))

    def outbox(self):
        return [(r[0], r[1], json.loads(r[2])) for r in self.db.execute("SELECT id,text,buttons FROM outbox WHERE delivered=0 ORDER BY rowid")]

    def delivered(self, key):
        with self.db:
            self.db.execute("UPDATE outbox SET delivered=1 WHERE id=?", (key,))
