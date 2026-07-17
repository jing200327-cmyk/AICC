from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RobotQuotaJob:
    job_id: str
    report_date: str
    status: str
    created_at: str
    updated_at: str
    completed_at: str = ''
    source_mode: str = ''
    workbook_path: str = ''
    robots: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None
