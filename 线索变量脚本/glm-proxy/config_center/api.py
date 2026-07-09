from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from .service import ConfigCenterError, ConfigCenterService


def error_response(code: str, message: str, detail: str = '', status_code: int = 400) -> JSONResponse:
    return JSONResponse({'error': {'code': code, 'message': message, 'detail': detail}}, status_code=status_code)


def create_router(service: ConfigCenterService) -> APIRouter:
    router = APIRouter(prefix='/api/config-center', tags=['config-center'])

    @router.get('/summary')
    async def summary():
        return service.summary()

    @router.post('/lead-scripts')
    async def save_lead_script(
        action_type: str = Form(...),
        store_name: str = Form(...),
        file: UploadFile = File(...),
    ):
        try:
            content = await file.read()
            return service.save_lead_script(action_type, store_name, file.filename or '', content)
        except ConfigCenterError as exc:
            return error_response(exc.code, exc.message, exc.detail, exc.status_code)

    @router.post('/split-stores')
    async def save_split_store(
        store_name: str = Form(...),
        file: UploadFile = File(...),
    ):
        try:
            content = await file.read()
            return service.save_split_store(store_name, file.filename or '', content)
        except ConfigCenterError as exc:
            return error_response(exc.code, exc.message, exc.detail, exc.status_code)

    @router.post('/outcall-tenants')
    async def save_outcall_tenant(payload: dict):
        try:
            return service.save_outcall_tenant(payload)
        except ConfigCenterError as exc:
            return error_response(exc.code, exc.message, exc.detail, exc.status_code)

    @router.post('/daily-accounts')
    async def save_daily_account(payload: dict):
        try:
            return service.save_daily_account(payload)
        except ConfigCenterError as exc:
            return error_response(exc.code, exc.message, exc.detail, exc.status_code)

    return router