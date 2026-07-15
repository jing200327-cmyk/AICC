import asyncio
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import openpyxl


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

from outcall.models import OutcallFile, OutcallJob
from outcall.repository import OutcallJobRepository
from outcall.service import OutcallService
from src.config import AppConfig, EnvironmentConfig, ExcelFile, Settings, TenantConfig
from src.tenant_processor import TenantStatus, process_tenant


def make_excel(path: Path, rows: int = 1) -> None:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.append(["客户姓氏", "被叫号码"])
    for index in range(rows):
        worksheet.append([f"客户{index}", f"1380000{index:04d}"])
    workbook.save(path)


def test_repository_restores_jobs_and_pause_state(tmp_path):
    repository = OutcallJobRepository(tmp_path / "aicc.sqlite3")
    job = OutcallJob(
        job_id="outcall_restore_1",
        status="running",
        environment="prod",
        environment_name="生产环境",
        base_url="https://service.aidcc.cn",
        store_code="yinma",
        store_name="银马",
        mode="formal",
        split_job_id="recovered_260714_yinma",
        files=[OutcallFile("formal4", "4", "银马-4.xlsx", "D:/银马-4.xlsx", 45)],
        resume_existing=True,
        current_batch="4",
        queued_batches=["5"],
        created_at="2026-07-14T11:00:00",
        updated_at="2026-07-14T11:01:00",
    )

    repository.save_job(job)
    repository.set_queue_paused("yinma", "prod", "20260714", True)

    restored = repository.load_jobs()
    assert len(restored) == 1
    assert restored[0].job_id == job.job_id
    assert restored[0].files[0].filename == "银马-4.xlsx"
    assert restored[0].resume_existing is True
    assert restored[0].queued_batches == ["5"]
    assert repository.is_queue_paused("yinma", "prod", "20260714") is True


def test_resume_mode_skips_completed_and_monitors_running_before_upload(monkeypatch, tmp_path):
    files = []
    for batch in ("2", "3", "4"):
        path = tmp_path / f"银马-{batch}.xlsx"
        make_excel(path)
        files.append(ExcelFile(path, "银马", batch, "银马"))

    tenant = TenantConfig(
        name="银马",
        prefixes=["银马"],
        environments={
            "prod": EnvironmentConfig("user", "password", "robot", "")
        },
        task_name_template="{tenant}{date}-{batch}",
    )
    config = AppConfig("prod", Settings(poll_interval_seconds=0), [tenant], "https://service.aidcc.cn")
    status = TenantStatus("银马")
    uploaded = []
    initiated = []

    async def fake_login(*args, **kwargs):
        return "token"

    async def fake_query(*args, **kwargs):
        task_name = args[-1]
        if task_name.endswith("-2"):
            return True, {"taskName": task_name, "state": 2, "actualCnt": 10}
        if task_name.endswith("-3"):
            return True, {"taskName": task_name, "state": 1, "actualCnt": 3}
        return True, None

    async def fake_wait_completion(*args, **kwargs):
        task_name = args[5]
        return True, {"taskName": task_name, "state": 2, "actualCnt": 8}

    async def fake_upload(*args, **kwargs):
        file_path = args[-1]
        uploaded.append(file_path.name)
        return "fid-4"

    async def fake_initiate(*args, **kwargs):
        initiated.append(args[-1])
        return {"code": 200, "data": {"id": "task-4"}}

    async def fake_wait_created(*args, **kwargs):
        return {"id": "task-4", "state": 1}

    monkeypatch.setattr("src.tenant_processor.login", fake_login)
    monkeypatch.setattr("src.tenant_processor.query_task_by_name", fake_query)
    monkeypatch.setattr("src.tenant_processor.wait_for_task_completion", fake_wait_completion)
    monkeypatch.setattr("src.tenant_processor.upload_file", fake_upload)
    monkeypatch.setattr("src.tenant_processor.initiate_outcall", fake_initiate)
    monkeypatch.setattr("src.tenant_processor.wait_for_task_created", fake_wait_created)

    asyncio.run(process_tenant(config, tenant, files, status, resume_existing=True))

    assert uploaded == ["银马-4.xlsx"]
    assert len(initiated) == 1
    assert initiated[0].endswith("-4")
    assert status.state == "全部完成"
    assert status.skipped_batches == ["2", "3"]
    assert [item["batch"] for item in status.batch_results] == ["2", "3", "4"]


def test_resume_mode_aborts_when_platform_status_query_fails(monkeypatch, tmp_path):
    path = tmp_path / "银马-4.xlsx"
    make_excel(path)
    tenant = TenantConfig(
        name="银马",
        prefixes=["银马"],
        environments={
            "prod": EnvironmentConfig("user", "password", "robot", "")
        },
        task_name_template="{tenant}{date}-{batch}",
    )
    config = AppConfig("prod", Settings(), [tenant], "https://service.aidcc.cn")
    status = TenantStatus("银马")
    uploaded = []

    async def fake_login(*args, **kwargs):
        return "token"

    async def failed_query(*args, **kwargs):
        return False, None

    async def fake_upload(*args, **kwargs):
        uploaded.append(args[-1].name)
        return "fid"

    monkeypatch.setattr("src.tenant_processor.login", fake_login)
    monkeypatch.setattr("src.tenant_processor.query_task_by_name", failed_query)
    monkeypatch.setattr("src.tenant_processor.upload_file", fake_upload)

    asyncio.run(
        process_tenant(
            config,
            tenant,
            [ExcelFile(path, "银马", "4", "银马")],
            status,
            resume_existing=True,
        )
    )

    assert uploaded == []
    assert status.state == "平台状态查询失败"
    assert "防重复外呼" in status.message


def test_stop_pending_pauses_queue_without_claiming_platform_task_was_stopped(monkeypatch, tmp_path):
    class FakeSplitService:
        def get_store(self, store_code):
            return SimpleNamespace(store_code=store_code, store_name="天翔林肯")

    service = OutcallService(
        tmp_path / "config.yaml",
        tmp_path,
        FakeSplitService(),
        tmp_path / "aicc.sqlite3",
    )
    job = OutcallJob(
        job_id="outcall_running_1",
        status="running",
        environment="prod",
        environment_name="生产环境",
        base_url="https://service.aidcc.cn",
        store_code="tianxiang_lincoln",
        store_name="天翔林肯",
        mode="formal",
        split_job_id="split-1",
        files=[],
        created_at="2026-07-14T11:00:00",
        updated_at="2026-07-14T11:00:00",
    )
    service.jobs[job.job_id] = job
    service.repository.save_job(job)

    async def fake_queue_state(*args, **kwargs):
        return {
            "store_code": "tianxiang_lincoln",
            "store_name": "天翔林肯",
            "environment": "prod",
            "is_paused": True,
            "completed_batches": [{"task_name": "天翔林肯0714-2"}],
            "running_batches": [{"task_name": "天翔林肯0714-3"}],
            "pending_batches": [{"task_name": "天翔林肯0714-4"}],
        }

    monkeypatch.setattr(service, "get_queue_state", fake_queue_state)
    result = asyncio.run(
        service.stop_pending_batches("tianxiang_lincoln", "prod")
    )

    assert service.jobs[job.job_id].status == "terminated"
    assert service.repository.is_queue_paused(
        "tianxiang_lincoln", "prod", datetime.now().strftime("%Y%m%d")
    )
    assert result["stopped_batches"] == ["天翔林肯0714-4"]
    assert result["requires_manual_platform_stop"] is True
    assert "平台当前仍在外呼：天翔林肯0714-3" in result["message"]


def test_service_shutdown_keeps_running_job_recoverable(tmp_path):
    class FakeSplitService:
        pass

    service = OutcallService(
        tmp_path / "config.yaml",
        tmp_path,
        FakeSplitService(),
        tmp_path / "aicc.sqlite3",
    )
    job = OutcallJob(
        job_id="outcall_shutdown_1",
        status="running",
        environment="prod",
        environment_name="生产环境",
        base_url="https://service.aidcc.cn",
        store_code="yinma",
        store_name="银马",
        mode="formal",
        split_job_id="split-1",
        files=[],
        created_at="2026-07-14T11:00:00",
        updated_at="2026-07-14T11:00:00",
    )
    status = TenantStatus("银马")
    service.jobs[job.job_id] = job
    service.statuses[job.job_id] = status
    service.repository.save_job(job)

    async def wait_until_cancelled(*args, **kwargs):
        await asyncio.Event().wait()

    async def cancel_for_server_shutdown():
        task = asyncio.create_task(
            service._run_job(
                job.job_id,
                None,
                None,
                [],
                status,
                wait_until_cancelled,
            )
        )
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(cancel_for_server_shutdown())

    assert job.status == "running"
    assert job.stop_requested is False
    assert job.state == "等待恢复"
    restored = service.repository.load_jobs()
    assert restored[0].status == "running"
    assert restored[0].state == "等待恢复"
