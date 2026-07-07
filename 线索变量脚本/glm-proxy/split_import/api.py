from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from .service import InvalidSplitStoreError, SplitFileNotFoundError, SplitImportError, SplitImportService, job_to_dict


def error_response(code: str, message: str, detail: str = '', status_code: int = 400) -> JSONResponse:
    return JSONResponse({'error': {'code': code, 'message': message, 'detail': detail}}, status_code=status_code)


def create_router(service: SplitImportService) -> APIRouter:
    router = APIRouter(prefix='/api/leads/split', tags=['lead-split'])

    @router.get('/stores')
    async def list_stores():
        return {'stores': [asdict(store) for store in service.list_stores()]}

    @router.get('/files')
    async def list_files(store_code: str = Query(...)):
        try:
            return {'files': [asdict(file) for file in service.list_files(store_code)]}
        except InvalidSplitStoreError as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)

    @router.post('/preview')
    async def preview_split(payload: dict):
        store_code = str(payload.get('store_code') or '')
        filename = str(payload.get('filename') or '')
        if not store_code:
            return error_response('MISSING_STORE_CODE', 'store_code is required', status_code=422)
        if not filename:
            return error_response('MISSING_FILENAME', 'filename is required', status_code=422)
        try:
            job = service.preview_split(store_code, filename)
            status_code = 200 if job.status == 'completed' else 422
            return JSONResponse(job_to_dict(job), status_code=status_code)
        except InvalidSplitStoreError as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except SplitFileNotFoundError as exc:
            return error_response(exc.code, exc.message, exc.detail, 404)
        except SplitImportError as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)

    return router
