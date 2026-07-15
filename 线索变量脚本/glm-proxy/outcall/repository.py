from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from threading import RLock

from .models import OutcallFile, OutcallJob


class OutcallJobRepository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS outcall_jobs (
                    job_id TEXT PRIMARY KEY,
                    store_code TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stop_requested INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_outcall_jobs_status
                    ON outcall_jobs(status, updated_at);
                CREATE TABLE IF NOT EXISTS outcall_queue_controls (
                    store_code TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    run_date TEXT NOT NULL,
                    is_paused INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (store_code, environment, run_date)
                );
                """
            )

    def save_job(self, job: OutcallJob) -> None:
        payload = json.dumps(asdict(job), ensure_ascii=False, default=str)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO outcall_jobs (
                    job_id, store_code, environment, status, stop_requested,
                    payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    store_code = excluded.store_code,
                    environment = excluded.environment,
                    status = excluded.status,
                    stop_requested = excluded.stop_requested,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    job.job_id,
                    job.store_code,
                    job.environment,
                    job.status,
                    int(job.stop_requested),
                    payload,
                    job.created_at,
                    job.updated_at,
                ),
            )

    def load_jobs(self) -> list[OutcallJob]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM outcall_jobs ORDER BY updated_at"
            ).fetchall()
        jobs = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            payload["files"] = [OutcallFile(**item) for item in payload.get("files", [])]
            jobs.append(OutcallJob(**payload))
        return jobs

    def set_queue_paused(
        self,
        store_code: str,
        environment: str,
        run_date: str,
        is_paused: bool,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO outcall_queue_controls (
                    store_code, environment, run_date, is_paused, updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(store_code, environment, run_date) DO UPDATE SET
                    is_paused = excluded.is_paused,
                    updated_at = excluded.updated_at
                """,
                (store_code, environment, run_date, int(is_paused)),
            )

    def is_queue_paused(self, store_code: str, environment: str, run_date: str) -> bool:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT is_paused FROM outcall_queue_controls
                WHERE store_code = ? AND environment = ? AND run_date = ?
                """,
                (store_code, environment, run_date),
            ).fetchone()
        return bool(row and row["is_paused"])
