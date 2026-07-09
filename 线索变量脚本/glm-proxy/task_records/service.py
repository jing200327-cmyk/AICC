from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


TASK_TYPES = [
    {'code': 'all', 'name': '全部任务类型'},
    {'code': 'lead_import', 'name': '线索导入'},
    {'code': 'split_preview', 'name': '线索预分割'},
    {'code': 'outcall_test', 'name': '测试线索外呼'},
    {'code': 'outcall_formal', 'name': '正式线索外呼'},
    {'code': 'daily_report', 'name': '龙星行日报'},
]

TASK_TYPE_NAMES = {item['code']: item['name'] for item in TASK_TYPES}
STATUS_NAMES = {
    'pending': '待执行',
    'processing': '执行中',
    'running': '执行中',
    'completed': '完成',
    'failed': '失败',
    'terminated': '已终止',
    'need_confirmation': '待确认',
}


@dataclass
class TaskRecord:
    task_id: str
    task_type: str
    task_type_name: str
    task_name: str
    executor: str
    status: str
    status_name: str
    input_file: str
    output_files: list[str]
    output_paths: list[str]
    created_at: str
    completed_at: str
    error: str = ''
    source: str = 'memory'


class TaskRecordError(Exception):
    code = 'TASK_RECORD_ERROR'
    message = 'Task record query failed'

    def __init__(self, detail: str = ''):
        super().__init__(detail or self.message)
        self.detail = detail


class InvalidTaskTypeError(TaskRecordError):
    code = 'INVALID_TASK_TYPE'
    message = 'Task type is not supported'


class InvalidTaskDateError(TaskRecordError):
    code = 'INVALID_TASK_DATE'
    message = 'Task date must be YYYY-MM-DD'


class TaskRecordService:
    def __init__(self, lead_service: Any, split_service: Any, outcall_service: Any, daily_report_service: Any):
        self.lead_service = lead_service
        self.split_service = split_service
        self.outcall_service = outcall_service
        self.daily_report_service = daily_report_service

    def list_records(self, task_type: str = 'all', task_date: str = '', days: int = 7) -> dict[str, Any]:
        task_type = (task_type or 'all').strip()
        if task_type not in TASK_TYPE_NAMES:
            raise InvalidTaskTypeError(task_type)
        target_date = self._parse_date(task_date)
        start_date = target_date or (date.today() - timedelta(days=max(1, days) - 1))
        end_date = target_date or date.today()

        records = []
        records.extend(self._lead_import_records())
        records.extend(self._split_records())
        records.extend(self._outcall_records())
        records.extend(self._daily_report_records())
        records.extend(self._scan_lead_import_records())
        records.extend(self._scan_split_records())
        records.extend(self._scan_daily_report_records())

        records = self._dedupe(records)
        records = [
            record for record in records
            if (task_type == 'all' or record.task_type == task_type)
            and self._record_in_range(record, start_date, end_date)
        ]
        records.sort(key=lambda item: item.created_at or item.completed_at, reverse=True)
        return {
            'task_types': TASK_TYPES,
            'date': target_date.isoformat() if target_date else '',
            'date_start': start_date.isoformat(),
            'date_end': end_date.isoformat(),
            'records': [asdict(record) for record in records],
            'total': len(records),
        }

    def _lead_import_records(self) -> list[TaskRecord]:
        records = []
        for job in getattr(self.lead_service, 'jobs', {}).values():
            store_name = job.detected_store.store_name if job.detected_store else '未知门店'
            created_at = self._iso(job.created_at)
            completed_at = self._iso(job.updated_at) if job.status in {'completed', 'failed', 'need_confirmation'} else ''
            yymmdd = self._yymmdd_from_iso(created_at)
            output_path = job.output.txt_file_path or ''
            records.append(TaskRecord(
                task_id=job.job_id,
                task_type='lead_import',
                task_type_name=TASK_TYPE_NAMES['lead_import'],
                task_name=f'{store_name}{yymmdd}导入',
                executor='运营专员',
                status=job.status,
                status_name=self._status_name(job.status),
                input_file=job.input_file.filename,
                output_files=[Path(output_path).name] if output_path else [],
                output_paths=[output_path] if output_path else [],
                created_at=created_at,
                completed_at=completed_at,
                error=self._job_error(job.error),
            ))
        return records

    def _split_records(self) -> list[TaskRecord]:
        records = []
        for job in getattr(self.split_service, 'jobs', {}).values():
            output_paths = [item.path for item in job.outputs]
            records.append(TaskRecord(
                task_id=job.job_id,
                task_type='split_preview',
                task_type_name=TASK_TYPE_NAMES['split_preview'],
                task_name=f'{job.store_name}-模板预分割',
                executor='运营专员',
                status=job.status,
                status_name=self._status_name(job.status),
                input_file=job.source_file.filename,
                output_files=[item.filename for item in job.outputs],
                output_paths=output_paths,
                created_at=job.created_at,
                completed_at=job.created_at if job.status in {'completed', 'failed'} else '',
                error=self._dict_error(job.error),
            ))
        return records

    def _outcall_records(self) -> list[TaskRecord]:
        records = []
        for job in getattr(self.outcall_service, 'jobs', {}).values():
            task_type = 'outcall_test' if job.mode == 'test' else 'outcall_formal'
            suffix = '测试' if job.mode == 'test' else '正式'
            records.append(TaskRecord(
                task_id=job.job_id,
                task_type=task_type,
                task_type_name=TASK_TYPE_NAMES[task_type],
                task_name=f'{job.store_name}-{suffix}',
                executor='运营专员',
                status=job.status,
                status_name=self._status_name(job.status),
                input_file='、'.join(file.filename for file in job.files),
                output_files=[file.filename for file in job.files],
                output_paths=[file.path for file in job.files],
                created_at=job.created_at,
                completed_at=job.updated_at if job.status in {'completed', 'failed', 'terminated'} else '',
                error=self._dict_error(job.error),
            ))
        return records

    def _daily_report_records(self) -> list[TaskRecord]:
        records = []
        for job in getattr(self.daily_report_service, 'jobs', {}).values():
            yyyyMMdd = self._yyyymmdd_from_report_date(job.report_date)
            output_paths = [item.path for item in job.outputs]
            records.append(TaskRecord(
                task_id=job.job_id,
                task_type='daily_report',
                task_type_name=TASK_TYPE_NAMES['daily_report'],
                task_name=f'{yyyyMMdd}日报生成',
                executor='运营专员',
                status=job.status,
                status_name=self._status_name(job.status),
                input_file='main.py',
                output_files=[item.filename for item in job.outputs],
                output_paths=output_paths,
                created_at=job.created_at,
                completed_at=job.completed_at if job.status in {'completed', 'failed'} else '',
                error=self._dict_error(job.error),
            ))
        return records

    def _scan_lead_import_records(self) -> list[TaskRecord]:
        records = []
        input_root = Path(getattr(self.lead_service, 'input_root', ''))
        registry = getattr(self.lead_service, 'registry', None)
        if not input_root.exists() or not registry:
            return records
        stores = list(registry.list_stores())
        for store in stores:
            store_dir = input_root / store.folder_name
            if not store_dir.exists():
                continue
            for output_path in sorted(store_dir.glob('*.txt'), key=lambda item: item.stat().st_mtime, reverse=True):
                stat = output_path.stat()
                created_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
                yymmdd = self._yymmdd_from_iso(created_at)
                job_prefix = output_path.name.split('_', 3)[:3]
                input_files = []
                if len(job_prefix) == 3:
                    prefix = '_'.join(job_prefix)
                    input_files = [path.name for path in store_dir.glob(f'{prefix}_*.xls*')]
                records.append(TaskRecord(
                    task_id=f'lead_file:{output_path}',
                    task_type='lead_import',
                    task_type_name=TASK_TYPE_NAMES['lead_import'],
                    task_name=f'{store.store_name}{yymmdd}导入',
                    executor='运营专员',
                    status='completed',
                    status_name=self._status_name('completed'),
                    input_file='、'.join(input_files),
                    output_files=[output_path.name],
                    output_paths=[str(output_path)],
                    created_at=created_at,
                    completed_at=created_at,
                    source='filesystem',
                ))
        return records

    def _scan_split_records(self) -> list[TaskRecord]:
        records = []
        split_root = Path(getattr(self.split_service, 'split_root', ''))
        if not split_root.exists():
            return records
        stores = list(getattr(self.split_service, 'stores', {}).values())
        for date_dir in sorted(split_root.iterdir(), reverse=True):
            if not date_dir.is_dir() or not re.fullmatch(r'\d{6}', date_dir.name):
                continue
            for store in stores:
                scan_dir = date_dir / store.store_name
                if not scan_dir.exists():
                    scan_dir = date_dir
                files = sorted(scan_dir.glob(f'{store.file_prefix}-*.xlsx'), key=self._split_output_sort_key)
                files = [path for path in files if path.is_file() and not path.name.startswith('~$')]
                if not files:
                    continue
                latest = max(path.stat().st_mtime for path in files)
                created_at = datetime.fromtimestamp(latest).isoformat()
                source_path = split_root / f'{store.file_prefix}-模板.xlsx'
                records.append(TaskRecord(
                    task_id=f'split_file:{date_dir.name}:{store.store_code}',
                    task_type='split_preview',
                    task_type_name=TASK_TYPE_NAMES['split_preview'],
                    task_name=f'{store.store_name}-模板预分割',
                    executor='运营专员',
                    status='completed',
                    status_name=self._status_name('completed'),
                    input_file=source_path.name,
                    output_files=[path.name for path in files],
                    output_paths=[str(path) for path in files],
                    created_at=created_at,
                    completed_at=created_at,
                    source='filesystem',
                ))
        return records

    def _scan_daily_report_records(self) -> list[TaskRecord]:
        records = []
        data_root = Path(getattr(self.daily_report_service, 'project_root', '')) / 'data'
        if not data_root.exists():
            return records
        for date_dir in sorted(data_root.iterdir(), reverse=True):
            if not date_dir.is_dir() or not re.fullmatch(r'\d{6}', date_dir.name):
                continue
            outputs = []
            for path in date_dir.rglob('*'):
                if path.is_file() and not path.name.startswith('~$') and ('每日报告' in path.parent.name or '汇总表' in path.parent.name):
                    outputs.append(path)
            if not outputs:
                continue
            latest = max(path.stat().st_mtime for path in outputs)
            created_at = datetime.fromtimestamp(latest).isoformat()
            records.append(TaskRecord(
                task_id=f'daily_file:{date_dir.name}',
                task_type='daily_report',
                task_type_name=TASK_TYPE_NAMES['daily_report'],
                task_name=f'{self._yyyymmdd_from_report_date(date_dir.name)}日报生成',
                executor='运营专员',
                status='completed',
                status_name=self._status_name('completed'),
                input_file='main.py',
                output_files=[path.name for path in sorted(outputs)],
                output_paths=[str(path) for path in sorted(outputs)],
                created_at=created_at,
                completed_at=created_at,
                source='filesystem',
            ))
        return records

    def _dedupe(self, records: list[TaskRecord]) -> list[TaskRecord]:
        deduped = []
        seen_outputs = set()
        seen_ids = set()
        for record in records:
            key = tuple(sorted(path for path in record.output_paths if path))
            id_key = record.task_id
            if id_key in seen_ids:
                continue
            if key and key in seen_outputs:
                continue
            seen_ids.add(id_key)
            if key:
                seen_outputs.add(key)
            deduped.append(record)
        return deduped

    def _record_in_range(self, record: TaskRecord, start_date: date, end_date: date) -> bool:
        record_dt = self._parse_iso_date(record.created_at or record.completed_at)
        if not record_dt:
            return True
        return start_date <= record_dt <= end_date

    def _parse_date(self, value: str) -> date | None:
        value = (value or '').strip()
        if not value:
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError as exc:
            raise InvalidTaskDateError(value) from exc

    def _parse_iso_date(self, value: str) -> date | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None

    def _iso(self, value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value or '')

    def _status_name(self, status: str) -> str:
        return STATUS_NAMES.get(status or '', status or '--')

    def _job_error(self, error: Any) -> str:
        if not error:
            return ''
        return getattr(error, 'detail', '') or getattr(error, 'message', '') or str(error)

    def _dict_error(self, error: dict[str, Any] | None) -> str:
        if not error:
            return ''
        return str(error.get('detail') or error.get('message') or error)

    def _yymmdd_from_iso(self, value: str) -> str:
        parsed = self._parse_iso_date(value)
        return parsed.strftime('%y%m%d') if parsed else ''

    def _yyyymmdd_from_report_date(self, value: str) -> str:
        value = (value or '').strip()
        if re.fullmatch(r'\d{6}', value):
            return f'20{value}'
        return value

    def _split_output_sort_key(self, path: Path):
        if '测试' in path.stem or '娴嬭瘯' in path.stem:
            return (0, 0)
        match = re.search(r'-(\d+)$', path.stem)
        return (1, int(match.group(1)) if match else 9999)
