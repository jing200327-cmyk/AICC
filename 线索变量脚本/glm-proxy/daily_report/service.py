from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import DailyReportFile, DailyReportJob, DailyReportPreview


class DailyReportError(Exception):
    code = 'DAILY_REPORT_ERROR'
    message = 'Daily report failed'

    def __init__(self, detail: str = ''):
        super().__init__(detail or self.message)
        self.detail = detail


class InvalidReportDateError(DailyReportError):
    code = 'INVALID_REPORT_DATE'
    message = 'REPORT_DATE must be YYMMDD'


class InvalidReportStoreError(DailyReportError):
    code = 'INVALID_REPORT_STORE'
    message = 'Report store is not configured'


class DailyReportService:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.jobs: dict[str, DailyReportJob] = {}
        self.tasks: dict[str, asyncio.Task] = {}

    def list_stores(self) -> list[dict[str, str]]:
        stores = [{'code': 'all', 'name': '所有'}]
        for account in self._load_accounts():
            name = str(account.get('name') or '').strip()
            if name:
                stores.append({'code': name, 'name': name})
        return stores

    def start_job(self, report_date: str | None = None, store: str = 'all', refresh_clue: bool = False) -> DailyReportJob:
        report_date = self._validate_report_date(report_date)
        store = (store or 'all').strip()
        store_name = self._validate_store(store)
        command = [sys.executable, str(self.project_root / 'main.py')]
        now = datetime.now().isoformat()
        job = DailyReportJob(
            job_id=f'daily_report_{report_date}_{uuid.uuid4().hex[:10]}',
            status='running',
            report_date=report_date,
            store=store,
            store_name=store_name,
            command=command,
            cwd=str(self.project_root),
            created_at=now,
            updated_at=now,
            refresh_clue=bool(refresh_clue),
        )
        self.jobs[job.job_id] = job
        self.tasks[job.job_id] = asyncio.create_task(self._run_job(job.job_id))
        return job

    def get_job(self, job_id: str) -> DailyReportJob | None:
        return self.jobs.get(job_id)

    def get_raw_files_status(self, report_date: str | None = None, store: str = 'all') -> dict[str, Any]:
        report_date = self._validate_report_date(report_date)
        store = (store or 'all').strip()
        store_name = self._validate_store(store)
        accounts = self._load_accounts()
        if store not in ('', 'all', '所有'):
            accounts = [account for account in accounts if str(account.get('name') or '').strip() == store]

        raw_dir = self.project_root / 'data' / report_date / '原始数据'
        items = []
        for account in accounts:
            name = str(account.get('name') or '').strip()
            clue_path = raw_dir / f'{name}-outcall-线索明细-{report_date}.xlsx'
            call_path = raw_dir / f'{name}-aicc-话单-{report_date}.xlsx'
            items.append({
                'store': name,
                'clue_exists': clue_path.exists(),
                'clue_path': str(clue_path) if clue_path.exists() else '',
                'call_exists': call_path.exists(),
                'call_path': str(call_path) if call_path.exists() else '',
            })

        return {
            'report_date': report_date,
            'store': store,
            'store_name': store_name,
            'raw_dir': str(raw_dir),
            'has_existing_clue': any(item['clue_exists'] for item in items),
            'items': items,
        }

    async def _run_job(self, job_id: str):
        job = self.jobs[job_id]
        env = os.environ.copy()
        env['REPORT_DATE'] = job.report_date
        if job.refresh_clue:
            env['REPORT_REFRESH_CLUE'] = '1'
        else:
            env.pop('REPORT_REFRESH_CLUE', None)
        if job.store != 'all':
            env['REPORT_STORE'] = job.store
        else:
            env.pop('REPORT_STORE', None)
        env['PYTHONIOENCODING'] = 'utf-8'

        try:
            proc = await asyncio.create_subprocess_exec(
                *job.command,
                cwd=job.cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode('utf-8', errors='replace')
            error_output = stderr.decode('utf-8', errors='replace')
            job.returncode = proc.returncode
            job.log = output + error_output
            job.reports = self._collect_reports(job.report_date, job.store, job.log)
            job.outputs = self._collect_outputs(job.report_date)
            job.status = 'completed' if proc.returncode == 0 else 'failed'
            if proc.returncode != 0:
                job.error = {
                    'code': 'DAILY_REPORT_EXECUTION_FAILED',
                    'message': 'Daily report script failed',
                    'detail': self._tail(job.log),
                }
        except Exception as exc:
            job.status = 'failed'
            job.log = f'{job.log}\n{exc}'.strip()
            job.error = {
                'code': 'DAILY_REPORT_EXECUTION_FAILED',
                'message': 'Daily report script failed',
                'detail': str(exc),
            }
        finally:
            job.completed_at = datetime.now().isoformat()
            job.updated_at = job.completed_at

    def _validate_report_date(self, report_date: str | None) -> str:
        value = (report_date or datetime.now().strftime('%y%m%d')).strip()
        if not re.fullmatch(r'\d{6}', value):
            raise InvalidReportDateError(value)
        try:
            datetime.strptime(value, '%y%m%d')
        except ValueError as exc:
            raise InvalidReportDateError(value) from exc
        return value

    def _validate_store(self, store: str) -> str:
        if store in ('', 'all', '所有'):
            return '所有'
        names = {str(account.get('name') or '').strip() for account in self._load_accounts()}
        if store not in names:
            raise InvalidReportStoreError(store)
        return store

    def _load_accounts(self) -> list[dict[str, Any]]:
        tools_dir = self.project_root / 'tools'
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        from recorder import ACCOUNTS
        return list(ACCOUNTS)

    def _collect_reports(self, report_date: str, store: str, log: str) -> list[DailyReportPreview]:
        report_dir = self.project_root / 'data' / report_date / '每日报告'
        if not report_dir.exists():
            return []

        filenames = []
        for match in re.finditer(r'报告:\s*([^\r\n]+?\.txt)', log):
            filenames.append(match.group(1).strip())

        paths: list[Path]
        if filenames:
            seen = set()
            paths = []
            for filename in filenames:
                path = report_dir / filename
                if path.exists() and path.name not in seen:
                    paths.append(path)
                    seen.add(path.name)
        elif store not in ('all', '所有'):
            paths = sorted(report_dir.glob(f'{store}_每日报告_{report_date}.txt'))
        else:
            paths = sorted(report_dir.glob(f'*_每日报告_{report_date}.txt'))

        return [self._report_preview(path, report_date) for path in paths]

    def _report_preview(self, path: Path, report_date: str) -> DailyReportPreview:
        content = path.read_text(encoding='utf-8', errors='replace').strip()
        suffix = f'_每日报告_{report_date}'
        name = path.stem[:-len(suffix)] if path.stem.endswith(suffix) else path.stem
        return DailyReportPreview(name=name, filename=path.name, path=str(path), content=content)

    def _collect_outputs(self, report_date: str) -> list[DailyReportFile]:
        out_dir = self.project_root / 'data' / report_date
        if not out_dir.exists():
            return []
        outputs = []
        for path in sorted(out_dir.rglob('*')):
            if path.is_file() and not path.name.startswith('~$'):
                kind = 'report' if '每日报告' in path.parts else ('summary' if '汇总表' in path.parts else 'data')
                outputs.append(DailyReportFile(filename=path.name, path=str(path), kind=kind, size=path.stat().st_size))
        return outputs

    def _tail(self, text: str, limit: int = 1200) -> str:
        return text[-limit:] if len(text) > limit else text


def job_to_dict(job: DailyReportJob) -> dict[str, Any]:
    return asdict(job)