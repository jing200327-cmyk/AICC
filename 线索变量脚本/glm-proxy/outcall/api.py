from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .service import (
    DuplicateOutcallFileError,
    InvalidOutcallEnvironmentError,
    InvalidOutcallModeError,
    OutcallError,
    OutcallFileNotFoundError,
    OutcallService,
    OutcallTenantNotFoundError,
    SplitJobNotFoundError,
    SplitJobNotReadyError,
    job_to_dict,
)


def error_response(code: str, message: str, detail: str = '', status_code: int = 400) -> JSONResponse:
    return JSONResponse({'error': {'code': code, 'message': message, 'detail': detail}}, status_code=status_code)


def create_router(service: OutcallService) -> APIRouter:
    router = APIRouter(prefix='/api/leads/outcall', tags=['lead-outcall'])

    @router.post('/jobs')
    async def start_job(payload: dict):
        store_code = str(payload.get('store_code') or '')
        environment = str(payload.get('environment') or '')
        mode = str(payload.get('mode') or '')
        split_job_id = str(payload.get('split_job_id') or '')
        if not store_code:
            return error_response('MISSING_STORE_CODE', 'store_code is required', status_code=422)
        if not environment:
            return error_response('MISSING_ENVIRONMENT', 'environment is required', status_code=422)
        if not mode:
            return error_response('MISSING_MODE', 'mode is required', status_code=422)
        if not split_job_id:
            return error_response('MISSING_SPLIT_JOB_ID', 'split_job_id is required', status_code=422)
        try:
            job = service.start_job(store_code, environment, mode, split_job_id)
            return JSONResponse(job_to_dict(job), status_code=202)
        except (InvalidOutcallEnvironmentError, InvalidOutcallModeError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except SplitJobNotFoundError as exc:
            return error_response(exc.code, exc.message, exc.detail, 404)
        except DuplicateOutcallFileError as exc:
            return error_response(exc.code, exc.detail or exc.message, exc.detail, 409)
        except (SplitJobNotReadyError, OutcallTenantNotFoundError, OutcallFileNotFoundError) as exc:
            return error_response(exc.code, exc.message, exc.detail, 422)
        except OutcallError as exc:
            return error_response(exc.code, exc.message, exc.detail, 400)

    @router.get('/jobs/{job_id}')
    async def get_job(job_id: str):
        job = service.get_job(job_id)
        if not job:
            return error_response('OUTCALL_JOB_NOT_FOUND', 'Outcall job does not exist', job_id, 404)
        return job_to_dict(job)

    @router.post('/jobs/{job_id}/terminate')
    async def terminate_job(job_id: str):
        job = service.terminate_job(job_id)
        if not job:
            return error_response('OUTCALL_JOB_NOT_FOUND', 'Outcall job does not exist', job_id, 404)
        return job_to_dict(job)

    return router