from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path

from .detector import StoreDetector
from .models import DetectedStore, InputFileInfo, JobError, LeadImportJob, LeadImportSummary, OutputInfo
from .processor import LeadProcessingError, generate_txt
from .registry import StoreScriptRegistry


class LeadImportError(Exception):
    code = "LEAD_IMPORT_ERROR"
    message = "Lead import failed"


class UnsupportedFileTypeError(LeadImportError):
    code = "UNSUPPORTED_FILE_TYPE"
    message = "Unsupported file type"


class EmptyFileError(LeadImportError):
    code = "EMPTY_FILE"
    message = "Uploaded file is empty"


class InvalidStoreCodeError(LeadImportError):
    code = "INVALID_STORE_CODE"
    message = "force_store_code is not registered"


class FileTooLargeError(LeadImportError):
    code = "FILE_TOO_LARGE"
    message = "Uploaded file is too large"


ALLOWED_SUFFIXES = {".xlsx", ".xls", ".csv"}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024


class LeadImportService:
    def __init__(self, registry: StoreScriptRegistry, output_root: Path, input_root: Path):
        self.registry = registry
        self.detector = StoreDetector(registry)
        self.output_root = Path(output_root)
        self.input_root = Path(input_root)
        self.jobs: dict[str, LeadImportJob] = {}

    def create_job_from_path(self, source_path: Path, filename: str, remark: str = "", force_store_code: str | None = None) -> LeadImportJob:
        source_path = Path(source_path)
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise UnsupportedFileTypeError()
        if not source_path.exists():
            raise EmptyFileError()
        file_size = source_path.stat().st_size
        if file_size == 0:
            raise EmptyFileError()
        if file_size > MAX_UPLOAD_SIZE:
            raise FileTooLargeError()
        if force_store_code and not self.registry.has(force_store_code):
            raise InvalidStoreCodeError()

        job_id = f"job_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:12]}"
        job = LeadImportJob(
            job_id=job_id,
            status="processing",
            detected_store=None,
            candidate_stores=[],
            input_file=InputFileInfo(filename=safe_name, size=file_size),
            logs=["Upload received"],
        )
        if remark:
            job.logs.append(f"Remark: {remark}")
        self.jobs[job_id] = job

        detection = self.detector.detect(source_path, safe_name)
        job.candidate_stores = detection.candidate_stores

        if force_store_code:
            store = self.registry.get(force_store_code)
            job.detected_store = DetectedStore(store.store_code, store.store_name, 1.0, ["force_store_code"])
        elif detection.detected_store:
            store = self.registry.get(detection.detected_store.store_code)
            job.detected_store = detection.detected_store
        else:
            job.status = "need_confirmation"
            job.error = JobError(
                "STORE_DETECTION_LOW_CONFIDENCE",
                "Store detection confidence is too low; pass force_store_code to retry",
            )
            job.logs.append("Store detection needs confirmation")
            job.touch()
            return job

        job.logs.append(f"Selected script: {store.script_path}")
        store_dir = self.input_root / store.folder_name
        store_dir.mkdir(parents=True, exist_ok=True)
        saved_input_path = store_dir / f"{job_id}_{safe_name}"
        shutil.copyfile(source_path, saved_input_path)
        job.input_file.saved_path = str(saved_input_path)
        job.logs.append(f"Saved to store folder: {saved_input_path}")

        try:
            output_path = store_dir / f"{job_id}_{Path(safe_name).stem}.txt"
            count = generate_txt(saved_input_path, output_path, store)
            if count <= 0 or not output_path.exists():
                raise LeadProcessingError("TXT was not generated")
            txt_content = output_path.read_text(encoding="utf-8")
            job.summary = LeadImportSummary(
                total_count=count,
                valid_count=count,
                error_count=0,
                repeat_count=0,
            )
            job.status = "completed"
            job.output = OutputInfo(
                txt_file_path=str(output_path),
                download_url=f"/api/leads/import/jobs/{job_id}/download",
                txt_preview=txt_content,
            )
            job.logs.append(f"TXT generated: {count} records")
        except LeadProcessingError as exc:
            job.status = "failed"
            job.error = JobError("SCRIPT_EXECUTION_FAILED", "Store script execution failed", str(exc))
            job.logs.append("Script execution failed")
        except OSError as exc:
            job.status = "failed"
            job.error = JobError("OUTPUT_WRITE_FAILED", "Output directory is not writable", str(exc))
            job.logs.append("Output write failed")
        finally:
            job.touch()
        return job

    def get_job(self, job_id: str) -> LeadImportJob | None:
        return self.jobs.get(job_id)

