from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OutcallFile:
    batch_key: str
    batch_name: str
    filename: str
    path: str
    row_count: int


@dataclass
class OutcallJob:
    job_id: str
    status: str
    environment: str
    environment_name: str
    base_url: str
    store_code: str
    store_name: str
    mode: str
    split_job_id: str
    files: list[OutcallFile]
    resume_existing: bool = False
    stop_requested: bool = False
    current_batch: str = ''
    queued_batches: list[str] = field(default_factory=list)
    stopped_batches: list[str] = field(default_factory=list)
    state: str = '等待启动'
    message: str = ''
    progress: str = '0/0'
    task_id: str = ''
    task_state: str = ''
    batch_results: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ''
    updated_at: str = ''
    error: dict[str, str] | None = None
