"""
租户处理模块 — 单租户的登录、批次队列、限流、状态监控
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List

from .config import AppConfig, TenantConfig, ExcelFile, count_leads_in_excel
from .api import (
    login,
    upload_file,
    initiate_outcall,
    query_task_by_name,
    wait_for_task_created,
    wait_for_task_completion,
)

logger = logging.getLogger(__name__)


class LeadCounter:
    def __init__(self, max_leads: int, window_minutes: int):
        self.max_leads = max_leads
        self.window_seconds = window_minutes * 60
        self.records: List[float] = []

    def _cleanup(self):
        now = time.time()
        self.records = [t for t in self.records if now - t < self.window_seconds]

    def current_count(self) -> int:
        self._cleanup()
        return sum(
            r for r in self.records if isinstance(r, (int, float)) and r > 0
        )

    def can_import(self, lead_count: int) -> bool:
        recorded_count = len(self.records)
        return (recorded_count + lead_count) <= self.max_leads

    def wait_seconds(self, lead_count: int) -> float:
        if not self.records:
            return 0
        now = time.time()
        valid = [t for t in self.records if now - t < self.window_seconds]
        if len(valid) + lead_count <= self.max_leads:
            return 0
        num_to_clear = len(valid) + lead_count - self.max_leads
        if num_to_clear <= 0 or num_to_clear > len(valid):
            num_to_clear = len(valid)
        oldest = valid[num_to_clear - 1] if num_to_clear <= len(valid) else valid[-1]
        return oldest + self.window_seconds - now + 1

    def add(self, lead_count: int):
        now = time.time()
        for _ in range(lead_count):
            self.records.append(now)

    def record_timestamp(self, ts: float):
        self.records.append(ts)


class TenantStatus:
    def __init__(self, tenant_name: str):
        self.tenant_name = tenant_name
        self.state = "初始化"
        self.current_batch = ""
        self.lead_count_window = 0
        self.max_leads = 100
        self.task_id = ""
        self.task_state = ""
        self.message = ""
        self.queued_batches: List[str] = []
        self.total_imported = 0
        self.total_batches = 0
        self.completed_batches = 0
        self.batch_results: List[dict] = []
        self.skipped_batches: List[str] = []
        self.updated_at = datetime.now()
        self.terminate_event = asyncio.Event()

    def to_dict(self) -> dict:
        return {
            "tenant": self.tenant_name,
            "state": self.state,
            "batch": self.current_batch,
            "leads": f"{self.lead_count_window}/{self.max_leads}",
            "task": self.task_id[:12] + "..." if len(self.task_id) > 12 else self.task_id,
            "task_state": self.task_state,
            "msg": self.message[:30] if self.message else "",
            "queue": ", ".join(self.queued_batches[:5]),
            "progress": f"{self.completed_batches}/{self.total_batches}",
        }

    def is_terminated(self) -> bool:
        return self.terminate_event.is_set()

    def request_terminate(self):
        self.terminate_event.set()
        self.state = "已终止"
        self.message = "用户手动终止"
        self.queued_batches = []

    def record_batch_result(
        self,
        batch_name: str,
        ok: bool,
        message: str,
        actual_count: int = 0,
        lead_count: int = 0,
    ):
        # 实时状态会被下一批覆盖；批次结果用于最终面板保留每个批次的成败。
        self.batch_results.append({
            "batch": batch_name,
            "ok": ok,
            "message": message,
            "actual_count": actual_count,
            "lead_count": lead_count,
        })


async def process_tenant(
    config: AppConfig,
    tenant: TenantConfig,
    files: List[ExcelFile],
    status: TenantStatus,
    resume_existing: bool = False,
):
    env_config = tenant.get_env_config(config.environment)
    base_url = config.base_url

    if not files:
        status.state = "无文件"
        status.message = f"未找到匹配前缀 '{tenant.prefixes}' 的 Excel 文件"
        return

    if not env_config.username or not env_config.password:
        status.state = "配置缺失"
        status.message = f"环境 {config.environment} 的账号密码未配置"
        return

    if not env_config.robot_id:
        status.state = "配置缺失"
        status.message = f"环境 {config.environment} 的 robot_id 未配置"
        return

    status.total_batches = len(files)
    status.queued_batches = [f.batch_name for f in files]

    import aiohttp

    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        status.state = "登录中"
        token = await login(
            session, base_url, tenant, env_config,
            client_id=config.settings.client_id,
        )
        if not token:
            status.state = "登录失败"
            status.message = "无法获取 token"
            return

        lead_counter = LeadCounter(
            max_leads=config.settings.max_leads_per_window,
            window_minutes=config.settings.time_window_minutes,
        )
        status.max_leads = config.settings.max_leads_per_window
        batch_initiate_time = None
        prev_lead_count = 0

        for i, excel_file in enumerate(files):
            if status.is_terminated():
                return

            batch_name = excel_file.batch_name
            status.current_batch = batch_name
            status.queued_batches = [f.batch_name for f in files[i + 1:]]

            lead_count = count_leads_in_excel(excel_file.file_path)
            task_name = tenant.task_name_template.format(
                tenant=tenant.name, batch=batch_name,
                date=datetime.now().strftime("%m%d"),
            )

            if resume_existing:
                status.state = "查询平台任务"
                status.message = f"检查批次 {batch_name} 是否已在平台创建"
                query_ok, existing_task = await query_task_by_name(
                    session, base_url, tenant, token, env_config, task_name
                )
                if not query_ok:
                    status.state = "平台状态查询失败"
                    status.task_state = "未确认"
                    status.message = f"无法确认平台是否已有任务 {task_name}，已停止恢复以防重复外呼"
                    status.record_batch_result(batch_name, False, status.message)
                    return
                if existing_task:
                    status.skipped_batches.append(batch_name)
                    state = existing_task.get("state")
                    if state == 2:
                        actual_cnt = int(existing_task.get("actualCnt") or 0)
                        connect_rate = int(round(actual_cnt / lead_count * 100)) if lead_count else 0
                        status.task_state = "已完成"
                        status.completed_batches += 1
                        status.message = f"平台已有任务，跳过上传；接通 {actual_cnt}/{lead_count} 条（接通率 {connect_rate}%）"
                        status.record_batch_result(
                            batch_name, True, status.message,
                            actual_count=actual_cnt, lead_count=lead_count,
                        )
                        continue
                    if state == 1:
                        status.state = "监控已有任务"
                        status.task_id = str(existing_task.get("id") or "")
                        status.task_state = "进行中"
                        status.message = f"平台任务 {task_name} 正在执行，等待完成"
                        success, task_info = await wait_for_task_completion(
                            session,
                            base_url,
                            tenant,
                            token,
                            env_config,
                            task_name,
                            poll_interval=config.settings.poll_interval_seconds,
                            terminate_event=status.terminate_event,
                        )
                        if status.is_terminated():
                            return
                        if success and task_info:
                            actual_cnt = int(task_info.get("actualCnt") or 0)
                            connect_rate = int(round(actual_cnt / lead_count * 100)) if lead_count else 0
                            status.task_state = "已完成"
                            status.completed_batches += 1
                            status.message = f"平台已有任务已完成；接通 {actual_cnt}/{lead_count} 条（接通率 {connect_rate}%）"
                            status.record_batch_result(
                                batch_name, True, status.message,
                                actual_count=actual_cnt, lead_count=lead_count,
                            )
                        else:
                            status.task_state = "超时/未知"
                            status.message = f"平台已有任务 {task_name} 状态未知，未重复上传"
                            status.record_batch_result(batch_name, False, status.message)
                        continue

                    status.task_state = f"未知状态 {state}"
                    status.message = f"平台已有任务 {task_name} 状态未知，未重复上传"
                    status.record_batch_result(batch_name, False, status.message)
                    continue

            if batch_initiate_time is not None and prev_lead_count > 0:
                # 同租户下一批不能立刻发起，要等上一批发起时间 + 上一批线索数 * 40 秒。
                min_next_start = batch_initiate_time + prev_lead_count * 40
                now = time.time()
                if now < min_next_start:
                    expected_start = datetime.fromtimestamp(min_next_start).strftime("%H:%M")
                    status.state = "批次延时"
                    status.message = f"预计 {expected_start} 发起"
                    logger.info(f"[{tenant.name}] {status.message}")
                    while time.time() < min_next_start:
                        if status.is_terminated():
                            return
                        await asyncio.sleep(1)

            logger.info(
                f"[{tenant.name}] 批次 {batch_name}: 文件包含 {lead_count} 条线索"
            )

            if not lead_counter.can_import(lead_count):
                wait_sec = lead_counter.wait_seconds(lead_count)
                status.state = "限流等待"
                status.message = f"等待 {wait_sec:.0f}s 以满足 {config.settings.max_leads_per_window}条/{config.settings.time_window_minutes}min 限制"
                logger.info(f"[{tenant.name}] {status.message}")
                await asyncio.sleep(wait_sec)

            if status.is_terminated():
                return

            status.state = "上传文件"
            fid = await upload_file(
                session, base_url, tenant, token, env_config, excel_file.file_path
            )
            if not fid:
                status.state = "上传失败"
                status.message = f"文件 {batch_name} 上传失败"
                status.record_batch_result(batch_name, False, status.message)
                continue

            if status.is_terminated():
                return

            status.state = "发起外呼"
            result = await initiate_outcall(
                session, base_url, tenant, token, env_config, fid, task_name
            )
            if not result:
                status.state = "外呼失败"
                status.message = f"批次 {batch_name} 外呼发起失败"
                status.record_batch_result(batch_name, False, status.message)
                continue

            initiate_time = time.time()
            status.state = "确认任务"
            created_task = await wait_for_task_created(
                session,
                base_url,
                tenant,
                token,
                env_config,
                task_name,
                terminate_event=status.terminate_event,
            )
            if status.is_terminated():
                return
            if not created_task:
                status.state = "任务未创建"
                status.task_state = "未出现"
                status.message = "未成功创建任务"
                status.record_batch_result(batch_name, False, status.message)
                continue

            batch_initiate_time = initiate_time
            prev_lead_count = lead_count

            task_id = ""
            data = result.get("data", {})
            if isinstance(data, dict):
                task_id = str(data.get("id") or data.get("taskId") or "")
            if not task_id and created_task:
                task_id = str(created_task.get("id") or "")
            status.task_id = task_id

            lead_counter.add(lead_count)
            status.lead_count_window = lead_counter.current_count()
            status.completed_batches += 1

            if status.is_terminated():
                return

            status.state = "监控任务"
            success, task_info = await wait_for_task_completion(
                session,
                base_url,
                tenant,
                token,
                env_config,
                task_name,
                poll_interval=config.settings.poll_interval_seconds,
                terminate_event=status.terminate_event,
            )
            if status.is_terminated():
                return
            if success and task_info:
                status.task_state = "已完成"
                actual_cnt = int(task_info.get("actualCnt") or 0)
                connect_rate = int(round(actual_cnt / lead_count * 100)) if lead_count else 0
                status.message = f"接通 {actual_cnt}/{lead_count} 条（接通率 {connect_rate}%）"
                status.record_batch_result(
                    batch_name,
                    True,
                    status.message,
                    actual_count=actual_cnt,
                    lead_count=lead_count,
                )
            else:
                status.task_state = "超时/未知"
                status.message = "任务状态未知或超时"
                status.record_batch_result(batch_name, False, status.message)

        failed_count = sum(1 for item in status.batch_results if not item["ok"])
        skipped_count = len(status.skipped_batches)
        skipped_message = f"，跳过 {skipped_count} 批次" if skipped_count else ""
        connected_count = sum(item.get("actual_count", 0) for item in status.batch_results if item["ok"])
        expected_count = sum(item.get("lead_count", 0) for item in status.batch_results if item["ok"])
        connect_rate = int(round(connected_count / expected_count * 100)) if expected_count else 0
        connect_message = f"，接通 {connected_count}/{expected_count} 条（总接通率 {connect_rate}%）"
        if failed_count:
            status.state = "处理完成"
            status.message = f"成功 {status.total_batches - failed_count}/{status.total_batches}，失败 {failed_count}{skipped_message}{connect_message}"
        else:
            status.state = "全部完成"
            status.message = f"共 {status.total_batches} 批次全部处理完毕{skipped_message}{connect_message}"
        status.queued_batches = []
