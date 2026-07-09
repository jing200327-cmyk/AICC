from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .service import InvalidTaskDateError, InvalidTaskTypeError, TaskRecordError, TaskRecordService


def error_response(code: str, message: str, detail: str = '', status_code: int = 400) -> JSONResponse:
    return JSONResponse({'error': {'code': code, 'message': message, 'detail': detail}}, status_code=status_code)


def create_router(service: TaskRecordService) -> APIRouter:
    router = APIRouter(prefix='/api/task-records', tags=['task-records'])

    @router.get('')
    async def list_records(task_type: str = 'all', date: str = '', days: int = 7):
        try:
            return service.list_records(
                task_type=str(task_type or 'all').strip() or 'all',
                task_date=str(date or '').strip(),
                days=max(1, min(int(days or 7), 31)),
            )
        except (InvalidTaskTypeError, InvalidTaskDateError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except TaskRecordError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)

    return router
