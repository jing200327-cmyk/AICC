from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class StoreScript:
    store_code: str
    store_name: str
    city: str
    brand: str
    keywords: list[str]
    script_path: str
    folder_name: str
    call_mode: str = "registry_wrapper"


@dataclass
class DetectedStore:
    store_code: str
    store_name: str
    confidence: float
    matched_by: list[str]


@dataclass
class DetectionResult:
    detected_store: Optional[DetectedStore]
    candidate_stores: list[DetectedStore]


@dataclass
class InputFileInfo:
    filename: str
    size: int
    saved_path: Optional[str] = None


@dataclass
class OutputInfo:
    txt_file_path: Optional[str] = None
    download_url: Optional[str] = None
    txt_preview: str = ""


@dataclass
class LeadImportSummary:
    total_count: int = 0
    valid_count: int = 0
    error_count: int = 0
    repeat_count: int = 0


@dataclass
class JobError:
    code: str
    message: str
    detail: str = ""


@dataclass
class LeadImportJob:
    job_id: str
    status: str
    detected_store: Optional[DetectedStore]
    candidate_stores: list[DetectedStore]
    input_file: InputFileInfo
    output: OutputInfo = field(default_factory=OutputInfo)
    summary: LeadImportSummary = field(default_factory=LeadImportSummary)
    logs: list[str] = field(default_factory=list)
    error: Optional[JobError] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        self.updated_at = datetime.now()
