from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from split_import.api import create_router
from split_import.models import SplitStore
from split_import.service import SplitImportService


STORE_CODE = 'wuling_after_sales'
STORE_NAME = '五菱售后'
SOURCE_FILENAME = f'{STORE_NAME}-模板.xlsx'


def _rows(count: int, offset: int = 0) -> list[dict[str, str]]:
    return [
        {
            '客户姓氏': f'客户{offset + index}',
            '被叫号码': f'138{offset + index:08d}',
            '客户真实手机号': f'139{offset + index:08d}',
            '意向车型': '测试车型',
            '来源平台': '测试平台',
            '变量': f'批次变量{offset + index}',
        }
        for index in range(count)
    ]


def _write_source(split_root: Path, count: int, offset: int = 0) -> Path:
    split_root.mkdir(parents=True, exist_ok=True)
    source_path = split_root / SOURCE_FILENAME
    pd.DataFrame(_rows(count, offset)).to_excel(source_path, index=False)
    return source_path


def _service(split_root: Path) -> SplitImportService:
    service = SplitImportService(split_root)
    service.upsert_store(
        SplitStore(
            store_code=STORE_CODE,
            store_name=STORE_NAME,
            file_prefix=STORE_NAME,
            script_name=f'split_excel_{STORE_NAME}-模板.py',
        )
    )
    return service


def test_existing_outputs_require_an_explicit_mode_without_deleting_files(tmp_path: Path):
    split_root = tmp_path / 'split'
    _write_source(split_root, 50)
    service = _service(split_root)

    first_job = service.preview_split(STORE_CODE, SOURCE_FILENAME)
    existing_files = {
        Path(output.path).name: Path(output.path).read_bytes()
        for output in first_job.outputs
    }

    with pytest.raises(Exception) as raised:
        service.preview_split(STORE_CODE, SOURCE_FILENAME)

    assert getattr(raised.value, 'code', '') == 'SPLIT_OUTPUT_CONFLICT'
    assert getattr(raised.value, 'existing_files', []) == [
        f'{STORE_NAME}-测试.xlsx',
        f'{STORE_NAME}-2.xlsx',
    ]
    for filename, content in existing_files.items():
        assert (Path(first_job.output_dir) / filename).read_bytes() == content


def test_append_mode_preserves_existing_files_and_continues_batch_numbers(tmp_path: Path):
    split_root = tmp_path / 'split'
    _write_source(split_root, 50)
    service = _service(split_root)
    first_job = service.preview_split(STORE_CODE, SOURCE_FILENAME)
    original_files = {
        Path(output.path).name: Path(output.path).read_bytes()
        for output in first_job.outputs
    }

    _write_source(split_root, 80, offset=1000)
    appended_job = service.preview_split(
        STORE_CODE,
        SOURCE_FILENAME,
        output_mode='append',
    )

    assert [output.filename for output in appended_job.outputs] == [
        f'{STORE_NAME}-3.xlsx',
        f'{STORE_NAME}-4.xlsx',
    ]
    assert [output.batch_key for output in appended_job.outputs] == [
        'formal3',
        'formal4',
    ]
    assert [output.row_count for output in appended_job.outputs] == [45, 35]
    assert appended_job.total_rows == 80
    assert appended_job.valid_rows == 80
    assert [output.filename for output in appended_job.all_outputs] == [
        f'{STORE_NAME}-测试.xlsx',
        f'{STORE_NAME}-2.xlsx',
        f'{STORE_NAME}-3.xlsx',
        f'{STORE_NAME}-4.xlsx',
    ]
    assert sum(output.row_count for output in appended_job.all_outputs) == 130
    for filename, content in original_files.items():
        assert (Path(first_job.output_dir) / filename).read_bytes() == content


def test_overwrite_mode_clears_old_batches_and_resets_default_names(tmp_path: Path):
    split_root = tmp_path / 'split'
    _write_source(split_root, 100)
    service = _service(split_root)
    first_job = service.preview_split(STORE_CODE, SOURCE_FILENAME)
    assert len(first_job.outputs) == 4

    _write_source(split_root, 1, offset=2000)
    overwritten_job = service.preview_split(
        STORE_CODE,
        SOURCE_FILENAME,
        output_mode='overwrite',
    )

    assert [output.filename for output in overwritten_job.outputs] == [
        f'{STORE_NAME}-测试.xlsx',
    ]
    assert overwritten_job.outputs[0].row_count == 1
    assert sorted(path.name for path in Path(overwritten_job.output_dir).glob('*.xlsx')) == [
        f'{STORE_NAME}-测试.xlsx',
    ]


def test_preview_api_returns_structured_conflict_with_available_modes(tmp_path: Path):
    split_root = tmp_path / 'split'
    _write_source(split_root, 6)
    service = _service(split_root)
    service.preview_split(STORE_CODE, SOURCE_FILENAME)
    app = FastAPI()
    app.include_router(create_router(service))
    client = TestClient(app)

    response = client.post(
        '/api/leads/split/preview',
        json={'store_code': STORE_CODE, 'filename': SOURCE_FILENAME},
    )

    assert response.status_code == 409
    error = response.json()['error']
    assert error['code'] == 'SPLIT_OUTPUT_CONFLICT'
    assert error['existing_files'] == [
        f'{STORE_NAME}-测试.xlsx',
        f'{STORE_NAME}-2.xlsx',
    ]
    assert error['available_modes'] == ['overwrite', 'append']
