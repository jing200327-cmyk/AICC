from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from .service import (
    InvalidRobotQuotaDateError,
    RobotQuotaError,
    RobotQuotaOutputNotFoundError,
    RobotQuotaService,
    job_to_dict,
)


def error_response(error: RobotQuotaError, status_code: int) -> JSONResponse:
    return JSONResponse(
        {'error': {'code': error.code, 'message': error.message, 'detail': error.detail}},
        status_code=status_code,
    )


def create_router(service: RobotQuotaService) -> APIRouter:
    router = APIRouter(prefix='/api/robot-quota', tags=['robot-quota'])

    @router.get('/preview')
    async def preview(report_date: str = ''):
        try:
            return service.get_preview(report_date or None)
        except InvalidRobotQuotaDateError as exc:
            return error_response(exc, 422)
        except RobotQuotaOutputNotFoundError as exc:
            return error_response(exc, 404)
        except RobotQuotaError as exc:
            return error_response(exc, 400)

    @router.post('/jobs')
    async def start_job(payload: dict):
        try:
            job = service.start_job(str(payload.get('report_date') or '').strip() or None)
            return JSONResponse(job_to_dict(job), status_code=202)
        except InvalidRobotQuotaDateError as exc:
            return error_response(exc, 422)
        except RobotQuotaError as exc:
            return error_response(exc, 400)

    @router.get('/jobs/{job_id}')
    async def get_job(job_id: str):
        job = service.get_job(job_id)
        if not job:
            return error_response(
                RobotQuotaOutputNotFoundError(f'Robot quota job does not exist: {job_id}'),
                404,
            )
        return job_to_dict(job)

    @router.get('/workbook')
    async def workbook(report_date: str = ''):
        try:
            path = service.workbook_path(report_date or None)
            return FileResponse(path, filename=path.name)
        except InvalidRobotQuotaDateError as exc:
            return error_response(exc, 422)
        except RobotQuotaOutputNotFoundError as exc:
            return error_response(exc, 404)

    @router.post('/reports/daily')
    async def daily_report(payload: dict):
        try:
            return await asyncio.to_thread(
                service.generate_daily_report_image,
                str(payload.get('report_date') or '').strip() or None,
            )
        except InvalidRobotQuotaDateError as exc:
            return error_response(exc, 422)
        except RobotQuotaOutputNotFoundError as exc:
            return error_response(exc, 404)
        except RobotQuotaError as exc:
            return error_response(exc, 400)

    @router.get('/reports/daily/image')
    async def daily_report_image(report_date: str = ''):
        try:
            path = service.daily_image_path(report_date or None)
            return FileResponse(path, media_type='image/png')
        except InvalidRobotQuotaDateError as exc:
            return error_response(exc, 422)
        except RobotQuotaOutputNotFoundError as exc:
            return error_response(exc, 404)

    @router.post('/reports/weekly')
    async def weekly_report(payload: dict):
        try:
            return await asyncio.to_thread(
                service.generate_weekly_report_image,
                str(payload.get('period_start') or '').strip(),
                str(payload.get('period_end') or '').strip(),
            )
        except InvalidRobotQuotaDateError as exc:
            return error_response(exc, 422)
        except RobotQuotaOutputNotFoundError as exc:
            return error_response(exc, 404)
        except RobotQuotaError as exc:
            return error_response(exc, 400)

    @router.get('/reports/weekly/image')
    async def weekly_report_image(period_start: str = '', period_end: str = ''):
        try:
            path = service.weekly_image_path(period_start, period_end)
            return FileResponse(path, media_type='image/png')
        except InvalidRobotQuotaDateError as exc:
            return error_response(exc, 422)
        except RobotQuotaOutputNotFoundError as exc:
            return error_response(exc, 404)

    return router
