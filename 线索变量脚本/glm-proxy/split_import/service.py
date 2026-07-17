from __future__ import annotations

import re
import uuid
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

from .models import SplitJob, SplitOutputFile, SplitSourceFile, SplitStore


CHUNK_SIZE = 45
START_NUMBER = 2
TEST_FILE_ROWS = 5
REQUIRED_COLUMNS = ['客户姓氏', '被叫号码', '客户真实手机号', '意向车型', '来源平台', '变量']


class SplitImportError(Exception):
    code = 'SPLIT_IMPORT_ERROR'
    message = 'Split preview failed'

    def __init__(self, detail: str = ''):
        super().__init__(detail or self.message)
        self.detail = detail


class InvalidSplitStoreError(SplitImportError):
    code = 'INVALID_SPLIT_STORE'
    message = 'Split store is not registered'


class SplitFileNotFoundError(SplitImportError):
    code = 'SPLIT_FILE_NOT_FOUND'
    message = 'Selected split source file does not exist'


class InvalidSplitFileError(SplitImportError):
    code = 'INVALID_SPLIT_FILE'
    message = 'Selected file is not a valid Excel file for this store'


class SplitSchemaError(SplitImportError):
    code = 'SPLIT_SCHEMA_ERROR'
    message = 'Excel file is missing required columns'


class InvalidSplitOutputModeError(SplitImportError):
    code = 'INVALID_SPLIT_OUTPUT_MODE'
    message = 'Split output mode must be overwrite or append'


class SplitOutputConflictError(SplitImportError):
    code = 'SPLIT_OUTPUT_CONFLICT'
    message = 'Split output files already exist'

    def __init__(self, store_name: str, output_dir: Path, existing_files: list[str]):
        self.store_name = store_name
        self.output_dir = str(output_dir)
        self.existing_files = existing_files
        super().__init__(f'{store_name} 当日已有分割文件，请选择覆盖或继续追加')


class SplitImportService:
    def __init__(self, split_root: Path):
        self.split_root = Path(split_root)
        self.jobs: dict[str, SplitJob] = {}
        self.stores: dict[str, SplitStore] = {
            'hefei_mazda': SplitStore('hefei_mazda', '合肥马自达', '合肥马自达', 'split_excel_合肥马自达-模板.py'),
            'meicheng_lincoln': SplitStore('meicheng_lincoln', '美诚林肯', '美诚林肯', 'split_excel_美诚林肯-模板.py'),
            'tianxiang_lincoln': SplitStore('tianxiang_lincoln', '天翔林肯', '天翔林肯', 'split_excel_天翔林肯-模板.py'),
            'wuhan_junma': SplitStore('wuhan_junma', '武汉骏马', '武汉骏马', 'split_excel_武汉骏马-模板.py'),
            'yinma': SplitStore('yinma', '银马', '银马', 'split_excel_银马-模板.py'),
        }

    def list_stores(self) -> list[SplitStore]:
        return list(self.stores.values())

    def upsert_store(self, store: SplitStore) -> None:
        self.stores[store.store_code] = store

    def get_store(self, store_code: str) -> SplitStore:
        try:
            return self.stores[store_code]
        except KeyError as exc:
            raise InvalidSplitStoreError(store_code) from exc

    def get_job(self, job_id: str) -> SplitJob | None:
        return self.jobs.get(job_id)

    def list_files(self, store_code: str) -> list[SplitSourceFile]:
        store = self.get_store(store_code)
        if not self.split_root.exists():
            return []
        files = []
        for path in sorted(self.split_root.glob(f'{store.file_prefix}*.xlsx'), key=lambda item: item.stat().st_mtime, reverse=True):
            if path.is_file() and not path.name.startswith('~$'):
                files.append(self._source_file(path))
        return files

    def preview_split(self, store_code: str, filename: str, output_mode: str = '') -> SplitJob:
        store = self.get_store(store_code)
        source_path = self._resolve_source_file(store, filename)
        source = self._source_file(source_path)
        job_id = f"split_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:10]}"
        output_dir = self.split_root / datetime.now().strftime('%y%m%d') / store.store_name
        output_dir.mkdir(parents=True, exist_ok=True)
        base_name = source_path.stem.split('-')[0]
        existing_files = self._list_output_files(output_dir, base_name)
        output_mode = str(output_mode or '').strip().lower()
        if output_mode and output_mode not in {'overwrite', 'append'}:
            raise InvalidSplitOutputModeError(output_mode)
        if existing_files and not output_mode:
            raise SplitOutputConflictError(
                store.store_name,
                output_dir,
                [path.name for path in existing_files],
            )
        if not output_mode:
            output_mode = 'overwrite'

        try:
            df = pd.read_excel(source_path, converters={'被叫号码': normalize_phone, '客户真实手机号': normalize_phone})
            if df.empty or len(df.columns) == 0:
                raise InvalidSplitFileError('Excel 文件为空')
            missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
            if missing_columns:
                raise SplitSchemaError(', '.join(missing_columns))
            df['被叫号码'] = df['被叫号码'].apply(normalize_phone)
            df['客户真实手机号'] = df['客户真实手机号'].apply(normalize_phone)

            outputs: list[SplitOutputFile] = []
            invalid_rows = 0
            valid_rows = 0
            if output_mode == 'overwrite':
                self._clear_output_dir(output_dir)
                self._clear_legacy_output_files(output_dir.parent, base_name)
                if len(df) > 0:
                    test_output, test_invalid = self._write_batch(
                        df.iloc[:TEST_FILE_ROWS],
                        output_dir / f'{base_name}-测试.xlsx',
                        'test',
                        '测试批次',
                    )
                    invalid_rows += test_invalid
                    valid_rows += test_output.row_count
                    outputs.append(test_output)
                remaining_df = df.iloc[TEST_FILE_ROWS:]
                first_batch_number = START_NUMBER
            else:
                remaining_df = df
                first_batch_number = self._next_batch_number(existing_files, base_name)

            num_files = (
                (len(remaining_df) + CHUNK_SIZE - 1) // CHUNK_SIZE
                if len(remaining_df) > 0
                else 0
            )
            for index in range(num_files):
                start_idx = index * CHUNK_SIZE
                end_idx = min((index + 1) * CHUNK_SIZE, len(remaining_df))
                batch_number = first_batch_number + index
                output, batch_invalid = self._write_batch(
                    remaining_df.iloc[start_idx:end_idx],
                    output_dir / f'{base_name}-{batch_number}.xlsx',
                    f'formal{batch_number}',
                    f'正式批次 {batch_number}',
                )
                invalid_rows += batch_invalid
                valid_rows += output.row_count
                outputs.append(output)

            all_outputs = self._read_all_outputs(output_dir, base_name)
            job = SplitJob(
                job_id=job_id,
                status='completed',
                store_code=store.store_code,
                store_name=store.store_name,
                source_file=source,
                output_dir=str(output_dir),
                script_name=store.script_name,
                outputs=outputs,
                total_rows=len(df),
                valid_rows=valid_rows,
                invalid_rows=invalid_rows,
                created_at=datetime.now().isoformat(),
                output_mode=output_mode,
                all_outputs=all_outputs,
            )
        except SplitImportError as exc:
            job = SplitJob(
                job_id=job_id,
                status='failed',
                store_code=store.store_code,
                store_name=store.store_name,
                source_file=source,
                output_dir=str(output_dir),
                script_name=store.script_name,
                outputs=[],
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                created_at=datetime.now().isoformat(),
                error={'code': exc.code, 'message': exc.message, 'detail': exc.detail},
                output_mode=output_mode,
            )
        except Exception as exc:
            job = SplitJob(
                job_id=job_id,
                status='failed',
                store_code=store.store_code,
                store_name=store.store_name,
                source_file=source,
                output_dir=str(output_dir),
                script_name=store.script_name,
                outputs=[],
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                created_at=datetime.now().isoformat(),
                error={'code': 'SPLIT_EXECUTION_FAILED', 'message': 'Split execution failed', 'detail': str(exc)},
                output_mode=output_mode,
            )
        self.jobs[job.job_id] = job
        return job

    def _list_output_files(self, output_dir: Path, base_name: str) -> list[Path]:
        if not output_dir.exists():
            return []
        files = [
            path
            for path in output_dir.glob(f'{base_name}-*.xlsx')
            if path.is_file() and not path.name.startswith('~$')
        ]
        return sorted(files, key=lambda path: self._output_file_sort_key(path, base_name))

    def _output_file_sort_key(self, path: Path, base_name: str) -> tuple[int, int]:
        suffix = path.stem[len(base_name) + 1:]
        if suffix == '测试':
            return (0, 0)
        return (1, int(suffix)) if suffix.isdigit() else (2, 0)

    def _next_batch_number(self, existing_files: list[Path], base_name: str) -> int:
        numbers = []
        for path in existing_files:
            suffix = path.stem[len(base_name) + 1:]
            if suffix.isdigit():
                numbers.append(int(suffix))
        return max(numbers, default=START_NUMBER - 1) + 1

    def _read_all_outputs(self, output_dir: Path, base_name: str) -> list[SplitOutputFile]:
        return [
            self._read_output_file(path, base_name)
            for path in self._list_output_files(output_dir, base_name)
        ]

    def _read_output_file(self, path: Path, base_name: str) -> SplitOutputFile:
        df = pd.read_excel(
            path,
            converters={'被叫号码': normalize_phone, '客户真实手机号': normalize_phone},
        )
        for column in ('被叫号码', '客户真实手机号'):
            if column in df.columns:
                df[column] = df[column].apply(normalize_phone)
        suffix = path.stem[len(base_name) + 1:]
        if suffix == '测试':
            batch_key = 'test'
            batch_name = '测试批次'
        else:
            batch_key = f'formal{suffix}'
            batch_name = f'正式批次 {suffix}'
        preview_rows = [
            mask_row(record)
            for record in df.head(5).fillna('').to_dict(orient='records')
        ]
        return SplitOutputFile(
            batch_key=batch_key,
            batch_name=batch_name,
            filename=path.name,
            path=str(path),
            row_count=len(df),
            columns=[str(column) for column in df.columns],
            preview_rows=preview_rows,
        )

    def _delete_output_file(self, path: Path) -> None:
        try:
            path.unlink()
        except PermissionError as exc:
            raise SplitImportError(f'无法覆盖旧分割文件，文件可能正被 Excel/WPS 打开：{path}') from exc
        except OSError as exc:
            raise SplitImportError(f'无法覆盖旧分割文件：{path}；{exc}') from exc

    def _clear_output_dir(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for path in output_dir.glob('*.xlsx'):
            if path.is_file() and not path.name.startswith('~$'):
                self._delete_output_file(path)

    def _clear_legacy_output_files(self, date_dir: Path, base_name: str) -> None:
        if not date_dir.exists():
            return
        for path in date_dir.glob(f'{base_name}-*.xlsx'):
            if path.is_file() and not path.name.startswith('~$'):
                self._delete_output_file(path)

    def _resolve_source_file(self, store: SplitStore, filename: str) -> Path:
        safe_name = Path(filename).name
        if Path(safe_name).suffix.lower() != '.xlsx':
            raise InvalidSplitFileError('仅支持 .xlsx 文件')
        if not safe_name.startswith(store.file_prefix):
            raise InvalidSplitFileError(f'文件名需以 {store.file_prefix} 开头')
        path = (self.split_root / safe_name).resolve()
        root = self.split_root.resolve()
        if root not in path.parents or not path.exists() or not path.is_file():
            raise SplitFileNotFoundError(safe_name)
        return path

    def _source_file(self, path: Path) -> SplitSourceFile:
        stat = path.stat()
        return SplitSourceFile(
            filename=path.name,
            path=str(path),
            size=stat.st_size,
            updated_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        )

    def _write_batch(self, df: pd.DataFrame, output_path: Path, batch_key: str, batch_name: str) -> tuple[SplitOutputFile, int]:
        valid_rows = []
        invalid_count = 0
        for _, row in df.iterrows():
            if not is_valid_phone(row['被叫号码']) or not is_valid_phone(row['客户真实手机号']):
                invalid_count += 1
            else:
                valid_rows.append(row)
        valid_df = pd.DataFrame(valid_rows, columns=df.columns)
        valid_df.to_excel(output_path, index=False)
        preview_df = valid_df.head(5).copy()
        preview_rows = [mask_row(record) for record in preview_df.fillna('').to_dict(orient='records')]
        return SplitOutputFile(
            batch_key=batch_key,
            batch_name=batch_name,
            filename=output_path.name,
            path=str(output_path),
            row_count=len(valid_df),
            columns=[str(col) for col in valid_df.columns],
            preview_rows=preview_rows,
        ), invalid_count


PHONE_PATTERN = re.compile(r'1\d{10}|0\d{2,3}-?\d{7,8}|0\d{9,11}')
MULTI_PHONE_SEPARATOR_PATTERN = re.compile(r'[,，、;；/\\|\r\n\t]+')


def extract_first_phone(phone_str: str) -> str:
    phone_text = phone_str.replace('－', '-').replace('—', '-').replace('–', '-')
    compact_text = re.sub(r'[\s\u3000]+', '', phone_text)

    match = PHONE_PATTERN.search(compact_text)
    if match:
        return match.group(0)

    for part in MULTI_PHONE_SEPARATOR_PATTERN.split(phone_text):
        part = re.sub(r'[\s\u3000]+', '', part)
        if part:
            return part

    return compact_text


def normalize_phone(phone: Any) -> str:
    if pd.isna(phone):
        return ''
    phone_str = str(phone).strip()
    if not phone_str:
        return ''
    phone_str = extract_first_phone(phone_str)
    numeric_text = phone_str.replace(',', '')
    if re.fullmatch(r'[+-]?\d+(\.\d+)?([eE][+-]?\d+)?', numeric_text) and not re.fullmatch(r'[+-]?0\d+', numeric_text):
        try:
            number = Decimal(numeric_text)
            if number == number.to_integral_value():
                return format(number.quantize(Decimal(1)), 'f')
        except InvalidOperation:
            pass
    return phone_str


def is_valid_phone(phone: Any) -> bool:
    phone_str = normalize_phone(phone)
    if not phone_str:
        return False
    digits = re.sub(r'\D', '', phone_str)
    if re.fullmatch(r'1\d{10}', digits):
        return True
    if phone_str.startswith('0') and 10 <= len(digits) <= 12:
        return True
    return False


def mask_phone(value: Any) -> str:
    text = normalize_phone(value)
    digits = re.sub(r'\D', '', text)
    if len(digits) == 11 and digits.startswith('1'):
        return f'{digits[:3]}****{digits[-4:]}'
    return text


def mask_row(record: dict[str, Any]) -> dict[str, Any]:
    masked = {}
    for key, value in record.items():
        if '手机号' in str(key) or '号码' in str(key):
            masked[str(key)] = mask_phone(value)
        else:
            masked[str(key)] = '' if pd.isna(value) else value
    return masked


def job_to_dict(job: SplitJob) -> dict[str, Any]:
    return asdict(job)
