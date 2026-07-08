from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DailyReportFile:
    filename: str
    path: str
    kind: str
    size: int


@dataclass
class DailyReportPreview:
    name: str
    filename: str
    path: str
    content: str


@dataclass
class DailyReportJob:
    job_id: str
    status: str
    report_date: str
    store: str
    store_name: str
    command: list[str]
    cwd: str
    created_at: str
    updated_at: str
    refresh_clue: bool = False
    completed_at: str = ''
    returncode: int | None = None
    log: str = ''
    reports: list[DailyReportPreview] = field(default_factory=list)
    outputs: list[DailyReportFile] = field(default_factory=list)
    error: dict[str, Any] | None = None