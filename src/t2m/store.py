"""Jobs in SQLite, files in `jobs/{id}/`."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .text import slugify

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  template TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  approved_by TEXT,
  approved_at TEXT,
  explore_post_id INTEGER
);
CREATE TABLE IF NOT EXISTS ai_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT,
  step TEXT NOT NULL,
  mode TEXT NOT NULL,
  model TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cost_usd REAL,
  ok INTEGER NOT NULL,
  error TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  step TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);
"""

# brief -> script -> rendered -> approved -> published
STATUSES = ("brief", "script", "rendered", "approved", "published")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")  # same form as SQLite datetime('now')


@dataclass
class Job:
    id: str
    template: str
    title: str
    status: str
    dir: Path
    approved_by: str | None = None
    explore_post_id: int | None = None

    @property
    def brief_path(self) -> Path:
        return self.dir / "brief.toml"

    @property
    def script_path(self) -> Path:
        return self.dir / "script.json"

    @property
    def final_path(self) -> Path:
        return self.dir / "final.mp4"

    @property
    def poster_path(self) -> Path:
        return self.dir / "poster.jpg"


class Store:
    def __init__(self, db_path: Path, jobs_dir: Path):
        self.jobs_dir = jobs_dir.resolve()
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def _job(self, row: sqlite3.Row) -> Job:
        return Job(row["id"], row["template"], row["title"], row["status"], self.jobs_dir / row["id"],
                   row["approved_by"], row["explore_post_id"])

    def create(self, template: str, title: str, brief_text: str, day: str | None = None) -> Job:
        base = f"{day or datetime.now().strftime('%Y%m%d')}-{slugify(title)[:40].strip('-')}"
        job_id, n = base, 2
        while self.db.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone():
            job_id, n = f"{base}-{n}", n + 1
        now = _now()
        self.db.execute("INSERT INTO jobs (id, template, title, status, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                        (job_id, template, title, "brief", now, now))
        self.db.commit()
        job = self.get(job_id)
        job.dir.mkdir(parents=True, exist_ok=True)
        job.brief_path.write_text(brief_text, encoding="utf-8")
        self.log(job_id, "new", title)
        return job

    def get(self, job_id: str) -> Job:
        row = self.db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise KeyError(f"Không có job '{job_id}'")
        return self._job(row)

    def all(self) -> list[Job]:
        return [self._job(r) for r in self.db.execute("SELECT * FROM jobs ORDER BY created_at DESC")]

    def set_status(self, job_id: str, status: str, **fields) -> None:
        assert status in STATUSES, status
        sets = ", ".join(["status = ?", "updated_at = ?"] + [f"{k} = ?" for k in fields])
        self.db.execute(f"UPDATE jobs SET {sets} WHERE id = ?", (status, _now(), *fields.values(), job_id))
        self.db.commit()
        self.log(job_id, status, json.dumps(fields, ensure_ascii=False) if fields else None)

    def log(self, job_id: str, step: str, detail: str | None = None) -> None:
        self.db.execute("INSERT INTO job_log (job_id, step, detail, created_at) VALUES (?,?,?,?)", (job_id, step, detail, _now()))
        self.db.commit()

    def record_ai(self, job_id: str | None, step: str, mode: str, model: str | None, input_tokens: int | None,
                  output_tokens: int | None, cost_usd: float | None, ok: bool, error: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO ai_usage (job_id, step, mode, model, input_tokens, output_tokens, cost_usd, ok, error, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (job_id, step, mode, model, input_tokens, output_tokens, cost_usd, int(ok), (error or "")[:300] or None, _now()))
        self.db.commit()

    def ai_totals(self, days: int = 30) -> list[sqlite3.Row]:
        return list(self.db.execute(
            "SELECT mode, model, COUNT(*) calls, SUM(input_tokens) input, SUM(output_tokens) output, SUM(cost_usd) cost,"
            " SUM(1 - ok) failed FROM ai_usage WHERE created_at >= datetime('now', ?) GROUP BY mode, model",
            (f"-{days} days",)))
