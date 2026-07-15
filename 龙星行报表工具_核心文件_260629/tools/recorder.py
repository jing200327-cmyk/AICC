# -*- coding: utf-8 -*-
import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

ACCOUNTS = [{'name': '长沙', 'username': 'lxhchangsha1234', 'password': 'changsha123456'},
 {'name': '翔鹏', 'username': 'lxhxiangpeng1234', 'password': 'xp1123456'},
 {'name': '骏宜', 'username': 'lxhjunyi1234', 'password': 'jy123456'},
 {'name': '韶关',
  'username': 'lxhshaoguan123',
  'password': 'shaoguan1234',
  'group_by_call_field': '机器人',
  'required_group_values': ['龙星行-新车首呼-广东韶关'],
  'group_display_names': {'龙星行-新车首呼-广东韶关': '韶关'},
  'group_summary_names': {'龙星行-新车首呼-广东韶关': '韶关'}},
 {'name': '广西龙星行',
  'username': 'gxlxhnn123456',
  'password': 'guangxinanning1234',
  'group_by_call_field': '机器人',
  'required_group_values': ['龙星行-新车首呼-广西南宁', '龙星行-新车首呼-广西玉林'],
  'group_display_names': {'龙星行-新车首呼-广西南宁': '广西龙星行-南宁新车首呼', '龙星行-新车首呼-广西玉林': '广西龙星行-玉林新车首呼'},
  'group_summary_names': {'龙星行-新车首呼-广西南宁': '南宁新车首呼', '龙星行-新车首呼-广西玉林': '玉林新车首呼'}},
 {'name': '海珠龙星行',
  'username': 'guangzhouhaizhu1234',
  'password': 'gzhz123456',
  'group_by_call_field': '机器人',
  'mtd_start_date': '260603',
  'merge_summary_title': '广州新车',
  'required_group_values': ['龙星行-新车首呼-广东广州海珠', '龙星行-新车首呼-广东广州番禺'],
  'group_display_names': {'龙星行-新车首呼-广东广州海珠': '广州龙星行-海珠新车首呼', '龙星行-新车首呼-广东广州番禺': '广州龙星行-番禺新车首呼'}},
 {'name': '广州龙星行',
  'username': 'lxhguangzhou123',
  'password': 'guangzhoulxh1234',
  'group_by_call_field': '机器人',
  'mtd_start_date': '260518',
  'merge_summary_title': '广州售后',
  'required_group_values': ['龙星行-广州龙星行-售后-活动招揽', '龙星行-广州龙星行-售后-续保提醒'],
  'group_display_names': {'龙星行-广州龙星行-售后-活动招揽': '广州龙星行-售后-活动招揽', '龙星行-广州龙星行-售后-续保提醒': '广州龙星行-售后-续保提醒'},
  'exclude_clue_ids': ['2056196796951138305',
                       '2056196098764095489',
                       '2056195749621841921',
                       '2056188808517488641',
                       '2056188808467156993',
                       '2056188808391659521']},
 {'name': '长沙售后', 'username': 'changshashouhou1234', 'password': 'shouhou123456'}]

BASE_URL = "https://service.aidcc.cn"
LOGIN_PATH = "/bc/v1/users/login"
CLUE_EXPORT_PATH = "/openapi-server/v2/call-clues/export-adviser-clue"
CALL_EXPORT_PATH = "/esl/v2/task/export-task-list"
CLIENT_ID = "110011"



def refresh_clue_enabled() -> bool:
    return (os.environ.get("REPORT_REFRESH_CLUE") or "").strip().lower() in {"1", "true", "yes", "y"}

def report_datetime() -> datetime:
    raw = os.environ.get("REPORT_DATE")
    if raw:
        return datetime.strptime(raw, "%y%m%d")
    return datetime.now()


def _request_id() -> str:
    return str(int(datetime.now().timestamp() * 1000))


def build_headers(token: str | None = None, content_type: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/outcall-manage/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
        "X-Request-Id": _request_id(),
        "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def build_cookies(credentials: dict) -> dict[str, str]:
    return {
        "remember": "true",
        "username": credentials["username"],
        "password": credentials["password"],
    }


def _encode_cookie(cookies: dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in cookies.items())


def post_json(
    url: str,
    headers: dict[str, str],
    payload: dict,
    timeout: int,
    cookies: dict[str, str] | None = None,
) -> tuple[int, dict]:
    request_headers = dict(headers)
    if cookies:
        request_headers["Cookie"] = _encode_cookie(cookies)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=request_headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        status = exc.code

    try:
        result = json.loads(text)
    except ValueError:
        result = {"code": status, "msg": text}
    return status, result


def login(credentials: dict, timeout: int = 30) -> str:
    payload = {
        "username": credentials["username"],
        "password": credentials["password"],
        "remember": True,
        "clientId": CLIENT_ID,
    }
    status, result = post_json(
        f"{BASE_URL}{LOGIN_PATH}",
        headers=build_headers(content_type="application/json"),
        payload=payload,
        timeout=timeout,
    )
    if status >= 400:
        raise RuntimeError(f"登录 HTTP 状态异常 {status}：{json.dumps(result, ensure_ascii=False)}")
    token = result.get("data", {}).get("accessToken")
    if result.get("code") != 200 or not token:
        raise RuntimeError(f"登录失败：{json.dumps(result, ensure_ascii=False)}")
    return token


def _write_clue_export(
    credentials: dict,
    token: str,
    month_start: str,
    dest_path: Path,
    report_dt: datetime,
    call_status: str = "",
    timeout: int = 60,
) -> Path:
    """导出线索明细（接口直接返回 Excel 文件流）"""
    end_of_today = report_dt.strftime("%Y-%m-%d 23:59:59")
    payload = {
        "customerName": "",
        "robot": "",
        "phoneNumber": "",
        "seriesIds": [],
        "seriesName": "",
        "callStatus": call_status,
        "startTime": month_start,
        "endTime": end_of_today,
        "intentLevelArr": [],
        "clueFlowType": "",
        "missedCallReasonList": [],
        "clueId": "",
        "storeId": [],
        "size": 10,
        "page": 1,
        "childChannels": [],
    }
    headers = build_headers(token=token, content_type="application/json")
    cookies = build_cookies(credentials)

    request_headers = dict(headers)
    request_headers["Cookie"] = _encode_cookie(cookies)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}{CLUE_EXPORT_PATH}",
        data=data,
        headers=request_headers,
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        content = response.read()

    dest_path.write_bytes(content)
    return dest_path


def _read_clue_export(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, engine="openpyxl", dtype={"线索ID": str})


def _merge_clue_exports(paths: list[Path], dest_path: Path) -> None:
    frames = []
    for path in paths:
        try:
            df = _read_clue_export(path)
        except Exception as exc:
            raise RuntimeError(f"线索明细导出文件读取失败 {path.name}: {exc}") from exc
        if not df.empty:
            frames.append(df)

    if not frames:
        raise RuntimeError("线索明细导出为空")

    merged = pd.concat(frames, ignore_index=True)
    if "线索ID" not in merged.columns:
        raise RuntimeError("线索明细导出文件缺少线索ID列")

    before = len(merged)
    merged["线索ID"] = merged["线索ID"].astype(str).str.strip()
    merged = merged.drop_duplicates(subset=["线索ID"], keep="first")
    merged.to_excel(dest_path, index=False, engine="openpyxl")
    print(f"  线索明细合并去重: {before} -> {len(merged)} 条")


def export_clue(
    credentials: dict,
    token: str,
    month_start: str,
    dest_path: Path,
    report_dt: datetime,
    timeout: int = 60,
) -> Path:
    """导出线索明细，并补拉默认导出可能遗漏的待重呼线索。"""
    base_path = dest_path.with_name(f"{dest_path.stem}__all{dest_path.suffix}")
    retry_path = dest_path.with_name(f"{dest_path.stem}__待重呼{dest_path.suffix}")

    _write_clue_export(credentials, token, month_start, base_path, report_dt, timeout=timeout)
    _write_clue_export(credentials, token, month_start, retry_path, report_dt, call_status="待重呼", timeout=timeout)
    _merge_clue_exports([base_path, retry_path], dest_path)

    for temp_path in (base_path, retry_path):
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass

    return dest_path

def export_call(
    credentials: dict,
    token: str,
    month_start: str,
    dest_path: Path,
    report_dt: datetime,
    timeout: int = 60,
) -> Path:
    """导出通话列表（接口返回 TOS 临时链接，再下载文件）"""
    start_iso = month_start.replace(" ", "T")  # "2026-06-01T00:00:00"
    end_iso = report_dt.strftime("%Y-%m-%dT23:59:59")
    payload = {
        "startTime": start_iso,
        "endTime": end_iso,
        "pageSize": 10,
        "currentPage": 1,
    }
    headers = build_headers(token=token, content_type="application/json")
    cookies = build_cookies(credentials)

    status, result = post_json(
        f"{BASE_URL}{CALL_EXPORT_PATH}",
        headers=headers,
        payload=payload,
        timeout=timeout,
        cookies=cookies,
    )

    if status >= 400 or result.get("code") != 200:
        raise RuntimeError(
            f"话单导出失败 HTTP {status}：{json.dumps(result, ensure_ascii=False)}"
        )

    download_url = result.get("data")
    if not download_url:
        raise RuntimeError(
            f"话单导出响应无下载链接：{json.dumps(result, ensure_ascii=False)}"
        )

    req = urllib.request.Request(
        download_url, headers={"User-Agent": headers["User-Agent"]}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        dest_path.write_bytes(response.read())

    return dest_path


def crawl(output_dir: str | Path, accounts: list | None = None) -> dict[str, dict[str, Path]]:
    report_dt = report_datetime()
    today = report_dt.strftime("%y%m%d")
    month_start = report_dt.strftime("%Y-%m-01 00:00:00")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = out_dir / "原始数据"
    raw_dir.mkdir(parents=True, exist_ok=True)
    error_dir = out_dir / "错误日志"
    error_dir.mkdir(parents=True, exist_ok=True)

    result = {}
    refresh_clue = refresh_clue_enabled()

    for acc in (accounts or ACCOUNTS):
        name = acc["name"]
        username = acc["username"]
        password = acc["password"]
        clue_file = raw_dir / f"{name}-outcall-线索明细-{today}.xlsx"
        call_file = raw_dir / f"{name}-aicc-话单-{today}.xlsx"


        if clue_file.exists() and call_file.exists() and not refresh_clue:
            print(f"  {name}: 原始数据已存在，跳过爬取")
            result[name] = {"clue": clue_file, "call": call_file}
            continue

        credentials = {"username": username, "password": password}
        last_error = None
        for attempt in range(1, 3):
            try:
                if attempt > 1:
                    print(f"  {name}: 第 {attempt} 次重新爬取...")

                print(f"  {name}: 登录中...")
                token = login(credentials)

                if refresh_clue or not clue_file.exists():
                    if refresh_clue and clue_file.exists():
                        print(f"  {name}: 用户选择重拉线索明细，成功后覆盖原文件")
                    print(f"  {name}: 导出线索明细...")
                    export_clue(credentials, token, month_start, clue_file, report_dt)
                    print(f"  {name}: 线索明细已保存 → {clue_file.name}")
                else:
                    print(f"  {name}: 线索明细已存在，跳过")

                if not call_file.exists():
                    print(f"  {name}: 导出通话列表...")
                    export_call(credentials, token, month_start, call_file, report_dt)
                    print(f"  {name}: 通话列表已保存 → {call_file.name}")
                else:
                    print(f"  {name}: 通话列表已存在，跳过")

                result[name] = {"clue": clue_file, "call": call_file}
                break
            except Exception as exc:
                last_error = exc
                print(f"  {name}: 第 {attempt} 次爬取失败：{exc}")
                error_log = error_dir / f"{name}-错误日志-{today}-第{attempt}次.txt"
                error_log.write_text(
                    f"时间：{datetime.now().isoformat()}\n"
                    f"账号：{username}\n"
                    f"错误：{exc}\n",
                    encoding="utf-8",
                )
        else:
            print(f"  {name}: 两次爬取均失败，跳过该账号")

    return result


if __name__ == "__main__":
    crawl(Path(__file__).parent.parent / "data" / report_datetime().strftime("%y%m%d"))
