"""
API 调用模块 — 封装所有外呼平台接口
"""
import json
import time
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import aiohttp

from .config import TenantConfig

logger = logging.getLogger(__name__)
RESULTS_DIR = Path(__file__).parent.parent / "results"


def _generate_request_id() -> str:
    return str(int(datetime.now().timestamp() * 1000))


def _common_headers(base_url: str, token: Optional[str] = None) -> dict:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Origin": base_url,
        "Referer": f"{base_url}/outcall-manage/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "X-Request-Id": _generate_request_id(),
        "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _cookies(env_config) -> dict:
    return {
        "remember": "true",
        "username": env_config.username,
        "password": env_config.password,
    }


def _save_result(tenant_name: str, endpoint: str, data: dict, suffix: str = ""):
    tenant_dir = RESULTS_DIR / tenant_name
    tenant_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{endpoint}{suffix}.json"
    with open(tenant_dir / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


async def login(
    session: aiohttp.ClientSession,
    base_url: str,
    tenant: TenantConfig,
    env_config,
    client_id: str = "110011",
) -> Optional[str]:
    url = f"{base_url}/bc/v1/users/login"
    payload = {
        "username": env_config.username,
        "password": env_config.password,
        "remember": True,
        "clientId": client_id,
    }
    headers = {
        **_common_headers(base_url),
        "Content-Type": "application/json",
    }
    logger.info(f"[{tenant.name}] 正在登录 {base_url} ...")
    _save_result(tenant.name, "login", {"request": payload}, "_request")

    try:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            text = await resp.text()
            logger.info(f"[{tenant.name}] 登录响应状态码: {resp.status}")
            logger.debug(f"[{tenant.name}] 登录响应: {text}")
            result = json.loads(text)
            _save_result(tenant.name, "login", result, "_response")

            if result.get("code") == 200:
                token = result.get("data", {}).get("accessToken")
                if token:
                    logger.info(f"[{tenant.name}] 登录成功，已获取 token")
                    return token
            logger.error(f"[{tenant.name}] 登录失败: {result.get('msg', '未知错误')}")
            return None
    except Exception as e:
        logger.error(f"[{tenant.name}] 登录异常: {e}")
        return None


async def upload_file(
    session: aiohttp.ClientSession,
    base_url: str,
    tenant: TenantConfig,
    token: str,
    env_config,
    file_path: Path,
) -> Optional[str]:
    url = f"{base_url}/calltask/upload-file"
    headers = _common_headers(base_url, token)
    cookies = _cookies(env_config)
    logger.info(f"[{tenant.name}] 正在上传文件: {file_path.name}")

    try:
        with open(file_path, "rb") as f:
            file_content = f.read()

        form = aiohttp.FormData()
        form.add_field(
            "file",
            file_content,
            filename=file_path.name,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        async with session.post(
            url, headers=headers, cookies=cookies, data=form, timeout=60
        ) as resp:
            text = await resp.text()
            logger.info(f"[{tenant.name}] 文件上传响应状态码: {resp.status}")
            logger.debug(f"[{tenant.name}] 文件上传响应: {text}")
            result = json.loads(text)
            _save_result(tenant.name, "upload", result)

            fid = result.get("data") or result.get("fid")
            if fid:
                logger.info(f"[{tenant.name}] 文件上传成功, fid={fid}")
                return str(fid)
            logger.error(f"[{tenant.name}] 文件上传未获取到 fid: {result}")
            return None
    except Exception as e:
        logger.error(f"[{tenant.name}] 文件上传异常: {e}")
        return None


async def initiate_outcall(
    session: aiohttp.ClientSession,
    base_url: str,
    tenant: TenantConfig,
    token: str,
    env_config,
    fid: str,
    task_name: str,
) -> Optional[dict]:
    url = f"{base_url}/calltask/v1/call-taskses/batch-import"
    headers = {
        **_common_headers(base_url, token),
        "Content-Type": "application/json",
    }
    cookies = _cookies(env_config)
    payload = {
        "fid": fid,
        "taskName": task_name,
        "robotId": env_config.robot_id,
        "tenantId": "",
        "llmServiceName": "Default",
        "ttsVoiceName": "Default",
        "ttsSpeechRate": "Default",
        "enableDcd": False,
        "groupId": "",
        "dealerId": env_config.dealer_id or "",
    }
    logger.info(f"[{tenant.name}] 正在发起外呼: {task_name}")
    _save_result(tenant.name, "outcall", {"request": payload}, "_request")

    for attempt in range(3):
        try:
            async with session.post(
                url, headers=headers, cookies=cookies, json=payload, timeout=30
            ) as resp:
                text = await resp.text()
                logger.info(f"[{tenant.name}] 外呼发起响应状态码: {resp.status}")
                logger.debug(f"[{tenant.name}] 外呼发起响应: {text}")
                result = json.loads(text)
                _save_result(tenant.name, "outcall", result, "_response")

                if result.get("code") == 200:
                    logger.info(f"[{tenant.name}] 外呼发起成功")
                    return result
                logger.error(f"[{tenant.name}] 外呼发起失败: {result.get('msg')}")
                return None
        except Exception as e:
            logger.error(f"[{tenant.name}] 外呼发起异常 (尝试 {attempt+1}/3): {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
    return None


async def get_task_status(
    session: aiohttp.ClientSession,
    base_url: str,
    tenant: TenantConfig,
    token: str,
    env_config,
    robot_id: str = "",
) -> Optional[dict]:
    url = f"{base_url}/esl/v2/task/getPageCallTasks"
    headers = {
        **_common_headers(base_url, token),
        "Content-Type": "application/json",
    }
    cookies = _cookies(env_config)
    payload = {
        "startTime": "",
        "endTime": "",
        "robotId": robot_id,
        "id": "",
        "taskName": "",
        "taskStatus": "",
        "isClue": 1,
        "expLimit": 1,
        "pageSize": 50,
        "currentPage": 1,
        "actualPhoneNumber": "",
        "phoneNumber": "",
        "clueId": "",
    }
    logger.debug(f"[{tenant.name}] 查询任务状态...")

    try:
        async with session.post(
            url, headers=headers, cookies=cookies, json=payload, timeout=30
        ) as resp:
            text = await resp.text()
            result = json.loads(text)
            _save_result(tenant.name, "task_status", result)
            if result.get("code") == 200:
                return result
            logger.error(f"[{tenant.name}] 任务状态查询失败: {result.get('msg')}")
            return None
    except Exception as e:
        logger.error(f"[{tenant.name}] 任务状态查询异常: {e}")
        return None


async def get_tasks_by_phone(
    session: aiohttp.ClientSession,
    base_url: str,
    tenant: TenantConfig,
    token: str,
    env_config,
    phone_number: str,
) -> Optional[dict]:
    # 这里复用“任务列表查询”接口，只是把 phoneNumber 填进去，用来判断这个手机号最近是否出现过。
    url = f"{base_url}/esl/v2/task/getPageCallTasks"
    headers = {
        **_common_headers(base_url, token),
        "Content-Type": "application/json",
    }
    cookies = _cookies(env_config)
    payload = {
        "startTime": "",
        "endTime": "",
        "robotId": "",
        "id": "",
        "taskName": "",
        "taskStatus": "",
        "isClue": 1,
        "expLimit": 1,
        "pageSize": 10,
        "currentPage": 1,
        "actualPhoneNumber": "",
        "phoneNumber": phone_number,
        "clueId": "",
    }
    logger.info(f"[{tenant.name}] 正在预检查重复导入手机号: {phone_number}")
    _save_result(tenant.name, "duplicate_precheck", {"request": payload}, "_request")

    try:
        async with session.post(
            url, headers=headers, cookies=cookies, json=payload, timeout=30
        ) as resp:
            text = await resp.text()
            logger.info(f"[{tenant.name}] 重复导入预检查响应状态码: {resp.status}")
            logger.debug(f"[{tenant.name}] 重复导入预检查响应: {text}")
            result = json.loads(text)
            _save_result(tenant.name, "duplicate_precheck", result, "_response")
            if result.get("code") == 200:
                return result
            logger.error(f"[{tenant.name}] 重复导入预检查失败: {result.get('msg')}")
            return None
    except Exception as e:
        logger.error(f"[{tenant.name}] 重复导入预检查异常: {e}")
        return None


async def find_task_by_name(
    session: aiohttp.ClientSession,
    base_url: str,
    tenant: TenantConfig,
    token: str,
    env_config,
    task_name: str,
) -> Optional[dict]:
    result = await get_task_status(
        session, base_url, tenant, token, env_config,
        robot_id=env_config.robot_id,
    )
    if not result:
        return None
    records = result.get("data", {}).get("records", [])
    for record in records:
        if record.get("taskName") == task_name:
            return record
    return None


async def wait_for_task_created(
    session: aiohttp.ClientSession,
    base_url: str,
    tenant: TenantConfig,
    token: str,
    env_config,
    task_name: str,
    poll_interval: int = 5,
    max_wait_seconds: int = 60,
    terminate_event=None,
) -> Optional[dict]:
    logger.info(f"[{tenant.name}] 确认任务是否已创建: {task_name}")
    waited = 0
    while waited <= max_wait_seconds:
        if terminate_event and terminate_event.is_set():
            logger.info(f"[{tenant.name}] 任务创建确认被终止: {task_name}")
            return None
        task = await find_task_by_name(
            session, base_url, tenant, token, env_config, task_name
        )
        if task:
            logger.info(f"[{tenant.name}] 已确认任务创建: {task_name}")
            return task
        if waited >= max_wait_seconds:
            break
        await asyncio.sleep(poll_interval)
        waited += poll_interval
    logger.error(f"[{tenant.name}] 任务未创建或未出现在任务列表: {task_name}")
    return None


async def wait_for_task_completion(
    session: aiohttp.ClientSession,
    base_url: str,
    tenant: TenantConfig,
    token: str,
    env_config,
    task_name: str,
    poll_interval: int = 30,
    max_wait_seconds: int = 7200,
    terminate_event=None,
) -> Tuple[bool, Optional[dict]]:
    logger.info(f"[{tenant.name}] 等待任务完成: {task_name}")
    waited = 0
    while waited < max_wait_seconds:
        if terminate_event and terminate_event.is_set():
            logger.info(f"[{tenant.name}] 任务监控被终止: {task_name}")
            return False, None
        task = await find_task_by_name(
            session, base_url, tenant, token, env_config, task_name
        )
        if task:
            state = task.get("state")
            if state == 2:
                logger.info(f"[{tenant.name}] 任务已完成: {task_name}")
                return True, task
            elif state == 1:
                logger.info(
                    f"[{tenant.name}] 任务进行中: {task_name} (已等待 {waited}s)"
                )
            else:
                logger.warning(f"[{tenant.name}] 任务状态未知: state={state}")
        await asyncio.sleep(poll_interval)
        waited += poll_interval
    logger.warning(f"[{tenant.name}] 等待任务超时: {task_name}")
    return False, None
