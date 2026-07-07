from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SplitStore:
    store_code: str
    store_name: str
    file_prefix: str
    script_name: str


@dataclass
class SplitSourceFile:
    filename: str
    path: str
    size: int
    updated_at: str


@dataclass
class SplitPreviewRow:
    values: dict[str, Any]


@dataclass
class SplitOutputFile:
    batch_key: str
    batch_name: str
    filename: str
    path: str
    row_count: int
    columns: list[str]
    preview_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SplitJob:
    job_id: str
    status: str
    store_code: str
    store_name: str
    source_file: SplitSourceFile
    output_dir: str
    script_name: str
    outputs: list[SplitOutputFile]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    created_at: str
    error: dict[str, str] | None = None
