import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "glm-proxy"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from lead_import.detector import StoreDetector
from lead_import.registry import StoreScriptRegistry
from lead_import.service import LeadImportService, UnsupportedFileTypeError
from server import app, lead_import_service


@pytest.fixture(autouse=True)
def isolate_app_service_storage(tmp_path):
    old_input_root = lead_import_service.input_root
    old_output_root = lead_import_service.output_root
    old_jobs = lead_import_service.jobs
    lead_import_service.input_root = tmp_path / "app-inputs"
    lead_import_service.output_root = tmp_path / "app-outputs"
    lead_import_service.jobs = {}
    try:
        yield
    finally:
        lead_import_service.input_root = old_input_root
        lead_import_service.output_root = old_output_root
        lead_import_service.jobs = old_jobs


def make_excel(path: Path, sheet_name: str = "武汉银马线索") -> None:
    df = pd.DataFrame(
        [
            {
                "车牌号": "鄂A12345",
                "车型": "昂克赛拉",
                "进厂日期": "2026-01-05",
                "进厂行驶里程": 12345,
                "门店": "武汉银马店",
            }
        ]
    )
    df.to_excel(path, index=False, sheet_name=sheet_name)


def test_registry_loads_registered_stores():
    registry = StoreScriptRegistry.default()

    stores = registry.list_stores()

    assert "wuhan_yinma" in [store.store_code for store in stores]
    assert registry.get("wuhan_yinma").store_name == "武汉银马店"
    assert registry.get("junma_last_month").script_path.endswith("骏马众城-上月保养.py")


def test_detector_identifies_store_from_filename_and_content(tmp_path):
    excel_path = tmp_path / "武汉银马-线索.xlsx"
    make_excel(excel_path)
    detector = StoreDetector(StoreScriptRegistry.default())

    result = detector.detect(excel_path)

    assert result.detected_store.store_code == "wuhan_yinma"
    assert result.detected_store.confidence >= 0.75
    assert "filename" in result.detected_store.matched_by


def test_rejects_unsupported_file_type(tmp_path):
    bad_file = tmp_path / "leads.exe"
    bad_file.write_bytes(b"not allowed")
    service = LeadImportService(
        registry=StoreScriptRegistry.default(),
        output_root=tmp_path / "outputs",
        input_root=tmp_path / "inputs",
    )

    with pytest.raises(UnsupportedFileTypeError):
        service.create_job_from_path(bad_file, "leads.exe")


def test_successful_job_generates_txt(tmp_path):
    excel_path = tmp_path / "武汉银马-线索.xlsx"
    make_excel(excel_path)
    service = LeadImportService(
        registry=StoreScriptRegistry.default(),
        output_root=tmp_path / "outputs",
        input_root=tmp_path / "inputs",
    )

    job = service.create_job_from_path(excel_path, "武汉银马-线索.xlsx")

    assert job.status == "completed"
    assert job.summary.total_count == 1
    assert job.summary.valid_count == 1
    assert job.input_file.saved_path is not None
    assert job.output.txt_preview
    assert job.output.txt_file_path is not None
    lines = Path(job.output.txt_file_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["assigned_store"] == "武汉银马店"
    assert record["last_maintain_time"] == "2026-01-05"


def test_script_failure_is_structured(tmp_path):
    excel_path = tmp_path / "武汉银马-空表.xlsx"
    pd.DataFrame().to_excel(excel_path, index=False)
    service = LeadImportService(
        registry=StoreScriptRegistry.default(),
        output_root=tmp_path / "outputs",
        input_root=tmp_path / "inputs",
    )

    job = service.create_job_from_path(excel_path, "武汉银马-空表.xlsx", force_store_code="wuhan_yinma")

    assert job.status == "failed"
    assert job.error.code == "SCRIPT_EXECUTION_FAILED"


def test_detection_failure_returns_need_confirmation(tmp_path):
    excel_path = tmp_path / "未知门店.xlsx"
    pd.DataFrame([{"车牌号": "鄂A12345", "车型": "车型A"}]).to_excel(excel_path, index=False)
    service = LeadImportService(
        registry=StoreScriptRegistry.default(),
        output_root=tmp_path / "outputs",
        input_root=tmp_path / "inputs",
    )

    job = service.create_job_from_path(excel_path, "未知门店.xlsx")

    assert job.status == "need_confirmation"
    assert job.error.code == "STORE_DETECTION_LOW_CONFIDENCE"


def test_download_endpoint_returns_generated_txt(tmp_path):
    excel_path = tmp_path / "武汉银马-线索.xlsx"
    make_excel(excel_path)
    job = lead_import_service.create_job_from_path(excel_path, "武汉银马-线索.xlsx")
    client = TestClient(app)

    response = client.get(f"/api/leads/import/jobs/{job.job_id}/download")

    assert response.status_code == 200
    assert "武汉银马店" in response.text


def test_upload_endpoint_creates_completed_job(tmp_path):
    excel_path = tmp_path / "武汉银马-线索.xlsx"
    make_excel(excel_path)
    client = TestClient(app)

    with excel_path.open("rb") as handle:
        response = client.post(
            "/api/leads/import",
            files={"file": ("武汉银马-线索.xlsx", handle, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"remark": "test upload"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"

    job_response = client.get(f"/api/leads/import/jobs/{body['job_id']}")
    assert job_response.status_code == 200
    detail = job_response.json()
    assert detail["detected_store"]["store_code"] == "wuhan_yinma"
    assert detail["input_file"]["saved_path"]
    assert detail["output"]["txt_preview"]


def test_rejects_large_upload(tmp_path):
    large_file = tmp_path / "large.xlsx"
    large_file.write_bytes(b"0" * (21 * 1024 * 1024))
    service = LeadImportService(
        registry=StoreScriptRegistry.default(),
        output_root=tmp_path / "outputs",
        input_root=tmp_path / "inputs",
    )

    with pytest.raises(Exception) as exc_info:
        service.create_job_from_path(large_file, "large.xlsx")

    assert getattr(exc_info.value, "code", "") == "FILE_TOO_LARGE"
