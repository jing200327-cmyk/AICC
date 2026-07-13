from __future__ import annotations

import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .service import (
    EmptyFileError,
    FileTooLargeError,
    InvalidSheetNameError,
    InvalidStoreCodeError,
    LeadImportService,
    MAX_UPLOAD_SIZE,
    SheetSelectionRequiredError,
    UnsupportedFileTypeError,
)


def error_response(code: str, message: str, detail: Any = "", status_code: int = 400) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "detail": detail}}, status_code=status_code)


def job_to_dict(job):
    data = asdict(job)
    data["created_at"] = job.created_at.isoformat()
    data["updated_at"] = job.updated_at.isoformat()
    return data


def create_router(service: LeadImportService) -> APIRouter:
    router = APIRouter(prefix="/api/leads/import", tags=["lead-import"])

    @router.get("/stores")
    async def list_stores():
        return {"stores": [asdict(store) for store in service.registry.list_stores()]}

    @router.post("")
    async def import_leads(
        file: UploadFile = File(...),
        remark: str = Form(""),
        force_store_code: str | None = Form(None),
        sheet_name: str | None = Form(None),
    ):
        if not file.filename:
            return error_response("EMPTY_FILE", "Uploaded file is empty", status_code=400)

        suffix = Path(file.filename).suffix.lower()
        too_large = False
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
            upload_size = 0
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                upload_size += len(chunk)
                if upload_size > MAX_UPLOAD_SIZE:
                    too_large = True
                    break
                tmp.write(chunk)

        if too_large:
            tmp_path.unlink(missing_ok=True)
            return error_response("FILE_TOO_LARGE", "Uploaded file is too large", status_code=413)
        if upload_size == 0:
            tmp_path.unlink(missing_ok=True)
            return error_response("EMPTY_FILE", "Uploaded file is empty", status_code=400)

        try:
            job = service.create_job_from_path(
                tmp_path,
                file.filename,
                remark=remark,
                force_store_code=force_store_code,
                sheet_name=sheet_name,
            )
            return {"job_id": job.job_id, "status": job.status, "message": _message_for_status(job.status)}
        except UnsupportedFileTypeError as exc:
            return error_response(exc.code, exc.message, status_code=400)
        except EmptyFileError as exc:
            return error_response(exc.code, exc.message, status_code=400)
        except FileTooLargeError as exc:
            return error_response(exc.code, exc.message, status_code=413)
        except InvalidStoreCodeError as exc:
            return error_response(exc.code, exc.message, status_code=422)
        except SheetSelectionRequiredError as exc:
            return error_response(exc.code, exc.message, {"sheet_names": exc.sheet_names}, status_code=409)
        except InvalidSheetNameError as exc:
            return error_response(exc.code, exc.message, status_code=422)
        finally:
            tmp_path.unlink(missing_ok=True)

    @router.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = service.get_job(job_id)
        if not job:
            return error_response("JOB_NOT_FOUND", "Job not found", "job_id does not exist", 404)
        return job_to_dict(job)

    @router.get("/jobs/{job_id}/download")
    async def download(job_id: str):
        job = service.get_job(job_id)
        if not job:
            return error_response("JOB_NOT_FOUND", "Job not found", "job_id does not exist", 404)
        if job.status != "completed":
            return error_response("JOB_NOT_COMPLETED", "Job is not completed", status_code=409)
        if not job.output.txt_file_path or not Path(job.output.txt_file_path).exists():
            return error_response("DOWNLOAD_FILE_NOT_FOUND", "Download file not found", status_code=404)
        return FileResponse(job.output.txt_file_path, media_type="text/plain; charset=utf-8", filename=Path(job.output.txt_file_path).name)

    return router


def _message_for_status(status: str) -> str:
    return {
        "completed": "Lead import completed",
        "failed": "Lead import failed",
        "need_confirmation": "Store detection confidence is too low; pass force_store_code to retry",
        "processing": "Lead import is processing",
        "pending": "Lead import is pending",
    }.get(status, status)
