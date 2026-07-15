import ast
import pprint
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from config_center.service import (
    ConfigCenterService,
    ConfigValidationError,
    DailyAccountReconfigureRequired,
)
from config_center.api import create_router
from daily_report.service import DailyReportService


def write_recorder(project_root: Path, accounts: list[dict]) -> Path:
    tools_dir = project_root / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    path = tools_dir / "recorder.py"
    path.write_text(
        "ACCOUNTS = " + pprint.pformat(accounts, width=120, sort_dicts=False) + "\n",
        encoding="utf-8",
    )
    return path


def read_accounts(path: Path) -> list[dict]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "ACCOUNTS" for target in node.targets)
    )
    return ast.literal_eval(assignment.value)


def config_service(project_root: Path) -> ConfigCenterService:
    service = object.__new__(ConfigCenterService)
    service.daily_project_root = project_root
    return service


def write_daily_outputs(project_root: Path, report_date: str, name: str) -> None:
    report_dir = project_root / "data" / report_date / "每日报告"
    summary_dir = project_root / "data" / report_date / "汇总表"
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"{name}_每日报告_{report_date}.txt").write_text(
        f"{name} 日报内容",
        encoding="utf-8",
    )
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["业务场景", "单位", name])
    sheet.append(["累计线索量", "条", 12])
    workbook.save(summary_dir / f"{name}_日度月度汇总表_{report_date}.xlsx")
    workbook.close()


def test_new_daily_account_is_available_in_all_daily_report_entry_points(tmp_path):
    recorder_path = write_recorder(
        tmp_path,
        [{"name": "骏宜", "username": "old", "password": "secret"}],
    )
    service = config_service(tmp_path)

    result = service.save_daily_account(
        {
            "name": "长沙售后",
            "username": "changsha-after-sales",
            "password": "new-secret",
            "has_multiple_robots": False,
        }
    )

    assert result["reconfigured"] is False
    assert result["account"] == {
        "name": "长沙售后",
        "has_multiple_robots": False,
        "robot_count": 1,
    }
    assert "password" not in result["account"]
    assert [item["name"] for item in read_accounts(recorder_path)] == ["骏宜", "长沙售后"]

    daily_service = DailyReportService(tmp_path)
    assert {item["name"] for item in daily_service.list_stores()} >= {"所有", "长沙售后"}

    monthly_options = daily_service.list_monthly_summary_stores()
    custom_option = next(item for item in monthly_options if item["name"] == "长沙售后")
    assert custom_option["summary"] == "长沙售后"

    write_daily_outputs(tmp_path, "260714", "长沙售后")
    preview = daily_service.get_preview("260714", "长沙售后")
    assert len(preview["groups"]) == 1
    assert preview["groups"][0]["title"] == "长沙售后"
    assert preview["groups"][0]["reports"][0].get("missing", False) is False
    assert preview["groups"][0]["summary"].get("missing", False) is False

    all_store_sources = daily_service._all_store_summary_source_files("260714")
    assert any(path.name.startswith("长沙售后_") for path in all_store_sources)


def test_multi_robot_account_registers_each_robot_as_a_report_group(tmp_path):
    write_recorder(tmp_path, [])
    service = config_service(tmp_path)
    service.save_daily_account(
        {
            "name": "新门店",
            "username": "new-store",
            "password": "secret",
            "has_multiple_robots": True,
            "required_group_values": "机器人甲\n机器人乙",
            "group_display_names": "机器人甲: 新门店-新车\n机器人乙: 新门店-售后",
            "group_summary_names": "机器人甲: 新门店新车\n机器人乙: 新门店售后",
        }
    )

    daily_service = DailyReportService(tmp_path)
    preview_groups = [
        group for group in daily_service._preview_groups()
        if group["stores"] == ["新门店"]
    ]
    assert [group["title"] for group in preview_groups] == ["新门店-新车", "新门店-售后"]
    assert [group["reports"] for group in preview_groups] == [["新门店-新车"], ["新门店-售后"]]
    assert [group["summary"] for group in preview_groups] == ["新门店新车", "新门店售后"]
    assert {item["name"] for item in daily_service.list_monthly_summary_stores()} == {
        "新门店-新车",
        "新门店-售后",
    }


def test_daily_account_persists_optional_mtd_start_date(tmp_path):
    recorder_path = write_recorder(tmp_path, [])
    service = config_service(tmp_path)

    result = service.save_daily_account(
        {
            "name": "南宁",
            "username": "nanning-account",
            "password": "secret",
            "has_multiple_robots": False,
            "mtd_start_date": "250613",
        }
    )

    assert read_accounts(recorder_path) == [
        {
            "name": "南宁",
            "username": "nanning-account",
            "password": "secret",
            "mtd_start_date": "250613",
        }
    ]
    assert result["account"]["mtd_start_date"] == "250613"


@pytest.mark.parametrize("value", ["20250613", "250231", "25-06-13", "invalid"])
def test_daily_account_rejects_invalid_mtd_start_date(tmp_path, value):
    write_recorder(tmp_path, [])
    service = config_service(tmp_path)

    with pytest.raises(ConfigValidationError, match="mtd_start_date"):
        service.save_daily_account(
            {
                "name": "南宁",
                "username": "nanning-account",
                "password": "secret",
                "has_multiple_robots": False,
                "mtd_start_date": value,
            }
        )


def test_daily_account_reconfiguration_can_update_and_clear_mtd_start_date(tmp_path):
    recorder_path = write_recorder(
        tmp_path,
        [
            {
                "name": "南宁",
                "username": "old-account",
                "password": "old-secret",
                "mtd_start_date": "250601",
                "custom_setting": "preserved",
            }
        ],
    )
    service = config_service(tmp_path)
    base_payload = {
        "name": "南宁",
        "username": "new-account",
        "password": "new-secret",
        "has_multiple_robots": False,
        "force_reconfigure": True,
    }

    service.save_daily_account({**base_payload, "mtd_start_date": "250613"})
    assert read_accounts(recorder_path)[0]["mtd_start_date"] == "250613"

    service.save_daily_account({**base_payload, "mtd_start_date": ""})
    account = read_accounts(recorder_path)[0]
    assert "mtd_start_date" not in account
    assert account["custom_setting"] == "preserved"


def test_existing_daily_account_requires_confirmation_then_replaces_in_place(tmp_path):
    original = {"name": "长沙售后", "username": "account", "password": "secret"}
    recorder_path = write_recorder(tmp_path, [original])
    service = config_service(tmp_path)
    payload = {
        **original,
        "has_multiple_robots": False,
    }

    with pytest.raises(DailyAccountReconfigureRequired) as exc_info:
        service.save_daily_account(payload)

    assert exc_info.value.code == "DAILY_ACCOUNT_RECONFIGURE_REQUIRED"
    assert exc_info.value.identical is True
    assert read_accounts(recorder_path) == [original]

    result = service.save_daily_account({**payload, "force_reconfigure": True})

    assert result["reconfigured"] is True
    assert read_accounts(recorder_path) == [original]


def test_changed_daily_account_also_requires_confirmation_before_replacement(tmp_path):
    recorder_path = write_recorder(
        tmp_path,
        [{"name": "长沙售后", "username": "old", "password": "old-secret"}],
    )
    service = config_service(tmp_path)
    payload = {
        "name": "长沙售后",
        "username": "new",
        "password": "new-secret",
        "has_multiple_robots": False,
    }

    with pytest.raises(DailyAccountReconfigureRequired) as exc_info:
        service.save_daily_account(payload)

    assert exc_info.value.identical is False

    service.save_daily_account({**payload, "force_reconfigure": True})
    assert read_accounts(recorder_path) == [
        {"name": "长沙售后", "username": "new", "password": "new-secret"}
    ]


def test_daily_account_api_returns_reconfigure_code_then_accepts_force(tmp_path):
    write_recorder(
        tmp_path,
        [{"name": "长沙售后", "username": "account", "password": "secret"}],
    )
    service = config_service(tmp_path)
    app = FastAPI()
    app.include_router(create_router(service))
    client = TestClient(app)
    payload = {
        "name": "长沙售后",
        "username": "account",
        "password": "secret",
        "has_multiple_robots": False,
    }

    conflict = client.post("/api/config-center/daily-accounts", json=payload)

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DAILY_ACCOUNT_RECONFIGURE_REQUIRED"

    replaced = client.post(
        "/api/config-center/daily-accounts",
        json={**payload, "force_reconfigure": True},
    )

    assert replaced.status_code == 200
    assert replaced.json()["reconfigured"] is True
