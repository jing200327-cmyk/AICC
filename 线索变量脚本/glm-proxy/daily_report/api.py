from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from .service import (
    DailyReportError,
    DailyReportService,
    InvalidReportDateError,
    InvalidReportStoreError,
    InvalidReportGroupError,
    job_to_dict,
)


def error_response(code: str, message: str, detail: str = '', status_code: int = 400) -> JSONResponse:
    return JSONResponse({'error': {'code': code, 'message': message, 'detail': detail}}, status_code=status_code)


def create_router(service: DailyReportService) -> APIRouter:
    router = APIRouter(prefix='/api/daily-report', tags=['daily-report'])

    @router.get('/stores')
    async def list_stores():
        return {'stores': service.list_stores()}

    @router.get('/preview')
    async def preview(report_date: str = '', store: str = 'all'):
        try:
            return service.get_preview(
                report_date=str(report_date or '').strip() or None,
                store=str(store or 'all').strip() or 'all',
            )
        except (InvalidReportDateError, InvalidReportStoreError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except DailyReportError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)

    @router.get('/summary-image')
    async def summary_image(report_date: str = '', group: str = ''):
        try:
            image_bytes, filename = service.get_summary_image(
                report_date=str(report_date or '').strip() or None,
                group=str(group or '').strip(),
            )
            return Response(
                content=image_bytes,
                media_type='image/png',
                headers={'Content-Disposition': 'inline; filename="summary.png"'},
            )
        except (InvalidReportDateError, InvalidReportStoreError, InvalidReportGroupError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except DailyReportError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)

    @router.get('/monthly-summary/stores')
    async def monthly_summary_stores():
        return {'stores': service.list_monthly_summary_stores()}

    @router.get('/monthly-summary/months')
    async def monthly_summary_months():
        return {'months': service.list_monthly_summary_months()}

    @router.post('/monthly-summary/status')
    async def monthly_summary_status(payload: dict):
        try:
            groups = payload.get('groups') or []
            if isinstance(groups, str):
                groups = [groups]
            return service.get_monthly_summary_status(
                groups=[str(item).strip() for item in groups if str(item).strip()],
                report_date=str(payload.get('report_date') or '').strip() or None,
                target_month=str(payload.get('target_month') or '').strip() or None,
            )
        except (InvalidReportDateError, InvalidReportStoreError, InvalidReportGroupError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except DailyReportError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)
    @router.post('/monthly-summary')
    async def monthly_summary(payload: dict):
        try:
            groups = payload.get('groups') or []
            if isinstance(groups, str):
                groups = [groups]
            return await asyncio.to_thread(
                service.generate_monthly_summaries,
                groups=[str(item).strip() for item in groups if str(item).strip()],
                report_date=str(payload.get('report_date') or '').strip() or None,
                force_overwrite=bool(payload.get('force_overwrite') or False),
                target_month=str(payload.get('target_month') or '').strip() or None,
            )
        except (InvalidReportDateError, InvalidReportStoreError, InvalidReportGroupError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except DailyReportError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)

    @router.get('/monthly-summary-image')
    async def monthly_summary_image(period: str = '', group: str = '', output_folder: str = ''):
        try:
            image_bytes, filename = service.get_monthly_summary_image(
                period=str(period or '').strip(),
                group=str(group or '').strip(),
                output_folder=str(output_folder or '').strip(),
            )
            return Response(
                content=image_bytes,
                media_type='image/png',
                headers={'Content-Disposition': 'inline; filename="monthly_summary.png"'},
            )
        except (InvalidReportDateError, InvalidReportStoreError, InvalidReportGroupError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except DailyReportError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)
    @router.get('/all-store-summary/status')
    async def all_store_summary_status(report_date: str = ''):
        try:
            return service.get_all_store_summary_status(
                report_date=str(report_date or '').strip() or None,
            )
        except (InvalidReportDateError, InvalidReportStoreError, InvalidReportGroupError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except DailyReportError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)

    @router.post('/all-store-summary')
    async def all_store_summary(payload: dict):
        try:
            return service.generate_all_store_summary(
                report_date=str(payload.get('report_date') or '').strip() or None,
                force_overwrite=bool(payload.get('force_overwrite') or False),
            )
        except AllStoreSummaryExistsError as exc:
            return error_response(exc.code, exc.message, exc.detail, 409)
        except (InvalidReportDateError, InvalidReportStoreError, InvalidReportGroupError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except DailyReportError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)

    @router.get('/all-store-summary-image')
    async def all_store_summary_image(report_date: str = ''):
        try:
            image_bytes, filename = service.get_all_store_summary_image(
                report_date=str(report_date or '').strip() or None,
            )
            return Response(
                content=image_bytes,
                media_type='image/png',
                headers={'Content-Disposition': 'inline; filename="all_store_summary.png"'},
            )
        except (InvalidReportDateError, InvalidReportStoreError, InvalidReportGroupError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except DailyReportError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)

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
