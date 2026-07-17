import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import openpyxl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1]
OUTCALL_SOURCE = (
    APP_DIR.parents[1]
    / "建银-线索自动预分割与导入脚本"
    / "建银-线索自动预分割与导入脚本"
)
OUTCALL_SITE_PACKAGES = OUTCALL_SOURCE / ".venv" / "Lib" / "site-packages"
for import_path in (APP_DIR, OUTCALL_SOURCE, OUTCALL_SITE_PACKAGES):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from config_center.api import create_router as create_config_router
from config_center.service import ConfigCenterService, ConfigValidationError
from outcall.service import OutcallService
from split_import.models import SplitJob, SplitOutputFile, SplitSourceFile
from split_import.service import SplitImportService
from src.config import load_config


def write_base_config(path: Path) -> None:
    path.write_text(
        "environment: prod\n"
        "settings:\n"
        "  poll_interval_seconds: 0\n"
        "tenants:\n",
        encoding="utf-8",
    )


def make_config_service(
    tmp_path: Path,
    split_service: SplitImportService,
    config_path: Path,
) -> ConfigCenterService:
    service = object.__new__(ConfigCenterService)
    service.lead_service = SimpleNamespace()
    service.split_service = split_service
    service.outcall_config_path = config_path
    service.daily_project_root = tmp_path / "daily"
    service.lead_script_dir = tmp_path / "lead-scripts"
    service.split_root = split_service.split_root
    service.store_path = tmp_path / "config_store.json"
    service._apply_persisted_config()
    return service


def valid_payload() -> dict:
    return {
        "name": "新外呼门店",
        "prefixes": "新外呼门店\n新门店别名",
        "environments_test_username": "",
        "environments_test_password": "",
        "environments_test_robot_id": "",
        "environments_test_dealer_id": "",
        "environments_prod_username": "prod-user",
        "environments_prod_password": "prod-password",
        "environments_prod_robot_id": "prod-robot",
        "environments_prod_dealer_id": "",
    }


@pytest.mark.parametrize(
    "field",
    [
        "environments_prod_username",
        "environments_prod_password",
        "environments_prod_robot_id",
    ],
)
def test_outcall_tenant_requires_production_credentials_before_writing(tmp_path, field):
    config_path = tmp_path / "config.yaml"
    write_base_config(config_path)
    original_config = config_path.read_text(encoding="utf-8")
    split_service = SplitImportService(tmp_path / "split")
    service = make_config_service(tmp_path, split_service, config_path)
    payload = valid_payload()
    payload[field] = ""

    with pytest.raises(ConfigValidationError, match=field):
        service.save_outcall_tenant(payload)

    assert config_path.read_text(encoding="utf-8") == original_config
    assert not service.store_path.exists()
    assert all(store.store_name != payload["name"] for store in split_service.list_stores())


def test_outcall_tenant_registers_sidebar_store_and_returns_no_credentials(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_base_config(config_path)
    split_service = SplitImportService(tmp_path / "split")
    service = make_config_service(tmp_path, split_service, config_path)

    result = service.save_outcall_tenant(valid_payload())

    assert result["tenant"] == {
        "name": "新外呼门店",
        "prefixes": ["新外呼门店", "新门店别名"],
        "has_test_environment": False,
        "prod_configured": True,
        "task_name_template": "{tenant}{date}-{batch}",
    }
    assert result["store"]["store_name"] == "新外呼门店"
    assert result["store"]["file_prefix"] == "新外呼门店"
    serialized_result = json.dumps(result, ensure_ascii=False)
    assert "prod-user" not in serialized_result
    assert "prod-password" not in serialized_result
    assert "prod-robot" not in serialized_result

    loaded = load_config(str(config_path))
    tenant = next(item for item in loaded.tenants if item.name == "新外呼门店")
    assert tenant.get_env_config("prod").username == "prod-user"
    assert tenant.get_env_config("prod").robot_id == "prod-robot"
    assert tenant.get_env_config("test").username == ""

    restarted_split_service = SplitImportService(tmp_path / "split")
    make_config_service(tmp_path, restarted_split_service, config_path)
    restarted_store = restarted_split_service.get_store(result["store"]["store_code"])
    assert restarted_store.store_name == "新外呼门店"


def test_outcall_tenant_api_returns_structured_validation_error(tmp_path):
    config_path = tmp_path / "config.yaml"
    write_base_config(config_path)
    service = make_config_service(
        tmp_path,
        SplitImportService(tmp_path / "split"),
        config_path,
    )
    app = FastAPI()
    app.include_router(create_config_router(service))
    client = TestClient(app)
    payload = valid_payload()
    payload["environments_prod_robot_id"] = ""

    response = client.post("/api/config-center/outcall-tenants", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CONFIG_VALIDATION_ERROR"
    assert "environments_prod_robot_id" in response.json()["error"]["detail"]


def make_excel(path: Path) -> None:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.append(["客户姓氏", "被叫号码"])
    worksheet.append(["测试客户", "138****0000"])
    workbook.save(path)
    workbook.close()


def test_configured_tenant_enters_outcall_queue_and_reports_platform_status(
    tmp_path,
    monkeypatch,
):
    config_path = tmp_path / "config.yaml"
    write_base_config(config_path)
    split_service = SplitImportService(tmp_path / "split")
    config_service = make_config_service(tmp_path, split_service, config_path)
    configured = config_service.save_outcall_tenant(valid_payload())
    store = split_service.get_store(configured["store"]["store_code"])

    day_dir = (
        split_service.split_root
        / datetime.now().strftime("%y%m%d")
        / store.store_name
    )
    day_dir.mkdir(parents=True)
    output_path = day_dir / f"{store.file_prefix}-2.xlsx"
    make_excel(output_path)
    split_job = SplitJob(
        job_id="split-new-store",
        status="completed",
        store_code=store.store_code,
        store_name=store.store_name,
        source_file=SplitSourceFile("template.xlsx", "", 0, ""),
        output_dir=str(day_dir),
        script_name=store.script_name,
        outputs=[
            SplitOutputFile(
                batch_key="formal2",
                batch_name="正式批次 2",
                filename=output_path.name,
                path=str(output_path),
                row_count=1,
                columns=[],
                preview_rows=[],
            )
        ],
        total_rows=1,
        valid_rows=1,
        invalid_rows=0,
        created_at=datetime.now().isoformat(),
    )
    split_service.jobs[split_job.job_id] = split_job
    outcall_service = OutcallService(
        config_path,
        OUTCALL_SOURCE,
        split_service,
        tmp_path / "aicc.sqlite3",
    )
    uploaded_files = []
    initiated_tasks = []

    async def fake_tenant_login(*args, **kwargs):
        return "fake-token"

    async def fake_upload(*args, **kwargs):
        uploaded_files.append(args[-1].name)
        return "fake-file-id"

    async def fake_initiate(*args, **kwargs):
        initiated_tasks.append(args[-1])
        return {"code": 200, "data": {"id": "platform-task-id"}}

    async def fake_wait_created(*args, **kwargs):
        return {"id": "platform-task-id", "state": 1}

    async def fake_wait_completed(*args, **kwargs):
        return True, {"id": "platform-task-id", "state": 2, "actualCnt": 1}

    monkeypatch.setattr("src.tenant_processor.login", fake_tenant_login)
    monkeypatch.setattr("src.tenant_processor.upload_file", fake_upload)
    monkeypatch.setattr("src.tenant_processor.initiate_outcall", fake_initiate)
    monkeypatch.setattr("src.tenant_processor.wait_for_task_created", fake_wait_created)
    monkeypatch.setattr("src.tenant_processor.wait_for_task_completion", fake_wait_completed)

    async def run_job_and_query_status():
        job = outcall_service.start_job(
            store.store_code,
            "prod",
            "formal",
            split_job.job_id,
        )
        await outcall_service.tasks[job.job_id]

        task_name = initiated_tasks[0]

        async def fake_status_login(*args, **kwargs):
            return "fake-token"

        async def fake_get_task_status(*args, **kwargs):
            return {
                "data": {
                    "records": [
                        {
                            "id": "platform-task-id",
                            "taskName": task_name,
                            "state": 2,
                            "actualCnt": 1,
                            "expectCnt": 1,
                            "createUserName": "prod-user",
                        }
                    ]
                }
            }

        monkeypatch.setattr("src.api.login", fake_status_login)
        monkeypatch.setattr("src.api.get_task_status", fake_get_task_status)
        queue_state = await outcall_service.get_queue_state(store.store_code, "prod")
        return outcall_service.get_job(job.job_id), queue_state

    job, queue_state = asyncio.run(run_job_and_query_status())

    assert uploaded_files == [output_path.name]
    assert initiated_tasks == [
        f"新外呼门店{datetime.now().strftime('%m%d')}-2"
    ]
    assert job.status == "completed"
    assert [item["task_name"] for item in queue_state["completed_batches"]] == initiated_tasks
    assert queue_state["running_batches"] == []
    assert queue_state["pending_batches"] == []
