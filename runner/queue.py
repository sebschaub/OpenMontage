import json, sqlite3
from datetime import datetime, timezone

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class JobQueue:
    def __init__(self, db_path: str):
        self.db_path = db_path
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY, pipeline TEXT, article_id INTEGER,
                spec_json TEXT, status TEXT, attempts INTEGER DEFAULT 0,
                cost_usd REAL, url TEXT, error TEXT,
                created_at TEXT, updated_at TEXT)""")

    def enqueue(self, job_id, pipeline, article_id, spec):
        with self._conn() as c:
            c.execute("INSERT INTO jobs(id,pipeline,article_id,spec_json,status,created_at,updated_at)"
                      " VALUES(?,?,?,?, 'pending', ?, ?)",
                      (job_id, pipeline, article_id, json.dumps(spec), _now(), _now()))

    def claim_next(self):
        with self._conn() as c:
            row = c.execute("SELECT * FROM jobs WHERE status='pending' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            c.execute("UPDATE jobs SET status='running', attempts=attempts+1, updated_at=? WHERE id=?",
                      (_now(), row["id"]))
            return self._row(c.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone())

    def mark_done(self, job_id, cost_usd, url):
        self._update(job_id, status="done", cost_usd=cost_usd, url=url)

    def mark_failed(self, job_id, error):
        self._update(job_id, status="failed", error=error)

    def _update(self, job_id, **fields):
        sets = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?"
        with self._conn() as c:
            c.execute(f"UPDATE jobs SET {sets} WHERE id=?",
                      (*fields.values(), _now(), job_id))

    def get(self, job_id):
        with self._conn() as c:
            r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return self._row(r) if r else None

    def recover_orphans(self, max_attempts):
        with self._conn() as c:
            for r in c.execute("SELECT id, attempts FROM jobs WHERE status='running'").fetchall():
                new = "pending" if r["attempts"] < max_attempts else "failed"
                err = None if new == "pending" else "exceeded max attempts after restart"
                c.execute("UPDATE jobs SET status=?, error=?, updated_at=? WHERE id=?",
                          (new, err, _now(), r["id"]))

    def depth(self):
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM jobs WHERE status='pending'").fetchone()[0]

    def running_count(self):
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0]

    @staticmethod
    def _row(r):
        d = dict(r); d["spec"] = json.loads(d.pop("spec_json") or "{}"); return d
