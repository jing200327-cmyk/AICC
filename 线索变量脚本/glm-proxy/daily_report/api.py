from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .service import (
    DailyReportError,
    DailyReportService,
    InvalidReportDateError,
    InvalidReportStoreError,
    job_to_dict,
)


def error_response(code: str, message: str, detail: str = '', status_code: int = 400) -> JSONResponse:
    return JSONResponse({'error': {'code': code, 'message': message, 'detail': detail}}, status_code=status_code)


def create_router(service: DailyReportService) -> APIRouter:
    router = APIRouter(prefix='/api/daily-report', tags=['daily-report'])

    @router.get('/stores')
    async def list_stores():
        return {'stores': service.list_stores()}

    @router.get('/raw-files')
    async def raw_files(report_date: str = '', store: str = 'all'):
        try:
            return service.get_raw_files_status(
                report_date=str(report_date or '').strip() or None,
                store=str(store or 'all').strip() or 'all',
            )
        except (InvalidReportDateError, InvalidReportStoreError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except DailyReportError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)

    @router.post('/jobs')
    async def start_job(payload: dict):
        try:
            job = service.start_job(
                report_date=str(payload.get('report_date') or '').strip() or None,
                store=str(payload.get('store') or 'all').strip() or 'all',
                refresh_clue=bool(payload.get('refresh_clue')),
            )
            return JSONResponse(job_to_dict(job), status_code=202)
        except (InvalidReportDateError, InvalidReportStoreError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except DailyReportError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)

    @router.get('/jobs/{job_id}')
    async def get_job(job_id: str):
        job = service.get_job(job_id)
        if not job:
            return error_response('DAILY_REPORT_JOB_NOT_FOUND', 'Daily report job does not exist', job_id, 404)
        return job_to_dict(job)

    return router