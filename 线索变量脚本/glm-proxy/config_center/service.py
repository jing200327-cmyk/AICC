from __future__ import annotations

import ast
import hashlib
import json
import pprint
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from lead_import.models import StoreScript
from split_import.models import SplitStore


class ConfigCenterError(Exception):
    code = 'CONFIG_CENTER_ERROR'
    message = 'Config center operation failed'
    status_code = 400

    def __init__(self, detail: str = ''):
        super().__init__(detail or self.message)
        self.detail = detail


class ConfigValidationError(ConfigCenterError):
    code = 'CONFIG_VALIDATION_ERROR'
    message = 'Configuration input is invalid'
    status_code = 422


class ConfigConflictError(ConfigCenterError):
    code = 'CONFIG_CONFLICT'
    message = 'Configuration already exists'
    status_code = 409


class DailyAccountReconfigureRequired(ConfigConflictError):
    code = 'DAILY_ACCOUNT_RECONFIGURE_REQUIRED'
    message = 'Daily report account reconfiguration requires confirmation'

    def __init__(self, name: str, identical: bool):
        self.name = name
        self.identical = identical
        super().__init__(f'{name} 已在 ACCOUNTS 中存在，请确认是否重新配置')


class ConfigCenterService:
    def __init__(self, lead_service: Any, split_service: Any, outcall_config_path: Path, daily_project_root: Path):
        self.lead_service = lead_service
        self.split_service = split_service
        self.outcall_config_path = Path(outcall_config_path)
        self.daily_project_root = Path(daily_project_root)
        self.lead_script_dir = Path(__file__).resolve().parents[2] / '线索变量脚本'
        self.split_root = Path(split_service.split_root)
        self.store_path = Path(__file__).resolve().parent / 'config_store.json'
        self._apply_persisted_config()

    def summary(self) -> dict[str, Any]:
        data = self._load_store()
        return {
            'lead_scripts': data.get('lead_scripts', []),
            'split_stores': data.get('split_stores', []),
            'outcall_config_path': str(self.outcall_config_path),
            'daily_recorder_path': str(self._recorder_path()),
        }

    def save_lead_script(self, action_type: str, store_name: str, filename: str, content: bytes) -> dict[str, Any]:
        store_name = self._require_text(store_name, '门店名称')
        action_type = (action_type or 'create').strip()
        if action_type not in {'create', 'update'}:
            raise ConfigValidationError('功能类型必须是新增脚本或脚本更新')
        suffix = Path(filename or '').suffix.lower()
        if suffix != '.py':
            raise ConfigValidationError('线索导入脚本仅支持 .py 文件')
        if not content:
            raise ConfigValidationError('上传脚本不能为空')

        self.lead_script_dir.mkdir(parents=True, exist_ok=True)
        script_path = self.lead_script_dir / f'{self._safe_filename(store_name)}.py'
        if script_path.exists() and action_type == 'create' and not self._lead_store_exists(store_name):
            raise ConfigConflictError(f'{script_path.name} 已存在，请选择脚本更新')
        script_path.write_bytes(content)

        data = self._load_store()
        stores = data.setdefault('lead_scripts', [])
        existing = next((item for item in stores if item.get('store_name') == store_name), None)
        if existing and action_type == 'create':
            raise ConfigConflictError(f'{store_name} 已在线索导入配置中存在，请选择脚本更新')
        store_code = (existing or {}).get('store_code') or self._store_code('lead', store_name)
        item = {
            'store_code': store_code,
            'store_name': store_name,
            'city': '',
            'brand': '',
            'keywords': [store_name],
            'script_path': str(script_path),
            'folder_name': store_name,
        }
        if existing:
            existing.update(item)
        else:
            stores.append(item)
        self._save_store(data)
        self._register_lead_script(item)
        return {'message': '线索导入脚本配置已保存', 'store': item}

    def save_split_store(self, store_name: str, filename: str, content: bytes) -> dict[str, Any]:
        store_name = self._require_text(store_name, '门店名称')
        suffix = Path(filename or '').suffix.lower()
        if suffix != '.xlsx':
            raise ConfigValidationError('门店模板仅支持 .xlsx 文件')
        if not content:
            raise ConfigValidationError('上传模板不能为空')

        self.split_root.mkdir(parents=True, exist_ok=True)
        template_path = self.split_root / f'{self._safe_filename(store_name)}-模板.xlsx'
        template_path.write_bytes(content)

        data = self._load_store()
        stores = data.setdefault('split_stores', [])
        existing = next((item for item in stores if item.get('store_name') == store_name), None)
        store_code = (existing or {}).get('store_code') or self._store_code('split', store_name)
        item = {
            'store_code': store_code,
            'store_name': store_name,
            'file_prefix': store_name,
            'script_name': f'split_excel_{store_name}-模板.py',
            'template_path': str(template_path),
        }
        if existing:
            existing.update(item)
        else:
            stores.append(item)
        self._save_store(data)
        self._register_split_store(item)
        return {'message': '线索预分割门店配置已保存', 'store': item}

    def save_outcall_tenant(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = self._require_text(payload.get('name'), 'name')
        prefixes = self._split_values(payload.get('prefixes')) or [name]
        test_environment = {
            'username': self._text(payload.get('environments_test_username')),
            'password': self._text(payload.get('environments_test_password')),
            'robot_id': self._text(payload.get('environments_test_robot_id')),
            'dealer_id': self._text(payload.get('environments_test_dealer_id')),
        }
        prod_environment = {
            'username': self._require_text(
                payload.get('environments_prod_username'),
                'environments_prod_username',
            ),
            'password': self._require_text(
                payload.get('environments_prod_password'),
                'environments_prod_password',
            ),
            'robot_id': self._require_text(
                payload.get('environments_prod_robot_id'),
                'environments_prod_robot_id',
            ),
            'dealer_id': self._text(payload.get('environments_prod_dealer_id')),
        }
        existing_names = self._configured_tenant_names()
        if name in existing_names:
            raise ConfigConflictError(f'{name} 已在 config.yaml tenants 中存在')

        tenant = {
            'name': name,
            'prefixes': prefixes,
            'environments': {
                'test': test_environment,
                'prod': prod_environment,
            },
            'task_name_template': '{tenant}{date}-{batch}',
        }
        data = self._load_store()
        stores = data.setdefault('split_stores', [])
        existing_store = next(
            (item for item in stores if item.get('store_name') == name),
            None,
        )
        runtime_store = next(
            (item for item in self.split_service.list_stores() if item.store_name == name),
            None,
        )
        store_code = (
            (existing_store or {}).get('store_code')
            or getattr(runtime_store, 'store_code', '')
            or self._store_code('split', name)
        )
        store_item = {
            'store_code': store_code,
            'store_name': name,
            'file_prefix': name,
            'script_name': f'split_excel_{name}-模板.py',
        }
        if existing_store:
            existing_store.update(store_item)
            store_item = existing_store
        else:
            stores.append(store_item)

        config_existed = self.outcall_config_path.exists()
        original_config = (
            self.outcall_config_path.read_text(encoding='utf-8')
            if config_existed
            else ''
        )
        try:
            self._append_tenant_yaml(tenant)
            self._save_store(data)
        except Exception:
            if config_existed:
                self.outcall_config_path.write_text(original_config, encoding='utf-8')
            elif self.outcall_config_path.exists():
                self.outcall_config_path.unlink()
            raise
        self._register_split_store(store_item)
        return {
            'message': '自动外呼租户配置已写入 config.yaml，门店已加入预分割菜单',
            'tenant': {
                'name': name,
                'prefixes': prefixes,
                'has_test_environment': all(
                    test_environment.get(key)
                    for key in ('username', 'password', 'robot_id')
                ),
                'prod_configured': True,
                'task_name_template': tenant['task_name_template'],
            },
            'store': store_item,
        }

    def save_daily_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = self._require_text(payload.get('name'), 'name')
        mtd_start_date = self._optional_report_date(
            payload.get('mtd_start_date'),
            'mtd_start_date',
        )
        account = {
            'name': name,
            'username': self._require_text(payload.get('username'), 'username'),
            'password': self._require_text(payload.get('password'), 'password'),
        }
        if mtd_start_date:
            account['mtd_start_date'] = mtd_start_date
        has_multiple = self._as_bool(payload.get('has_multiple_robots'))
        if has_multiple:
            required_values = self._split_values(payload.get('required_group_values'))
            if not required_values:
                raise ConfigValidationError('required_group_values 不能为空')
            display_names = self._parse_mapping(payload.get('group_display_names'))
            summary_names = self._parse_mapping(payload.get('group_summary_names')) or dict(display_names)
            account.update({
                'group_by_call_field': self._text(payload.get('group_by_call_field')) or '机器人',
                'required_group_values': required_values,
                'group_display_names': display_names,
                'group_summary_names': summary_names,
            })
        accounts = self._load_daily_accounts()
        existing_index = next(
            (index for index, item in enumerate(accounts) if self._text(item.get('name')) == name),
            None,
        )
        reconfigured = existing_index is not None
        if existing_index is not None:
            existing = accounts[existing_index]
            managed_keys = {
                'name',
                'username',
                'password',
                'group_by_call_field',
                'required_group_values',
                'group_display_names',
                'group_summary_names',
                'mtd_start_date',
            }
            existing_managed = {
                key: value
                for key, value in existing.items()
                if key in managed_keys
            }
            if not self._as_bool(payload.get('force_reconfigure')):
                raise DailyAccountReconfigureRequired(name, identical=existing_managed == account)
            preserved = {
                key: value
                for key, value in existing.items()
                if key not in managed_keys
            }
            accounts[existing_index] = {**account, **preserved}
        else:
            accounts.append(account)
        self._write_daily_accounts(accounts)
        account_summary = {
            'name': name,
            'has_multiple_robots': has_multiple,
            'robot_count': len(account.get('required_group_values') or []) if has_multiple else 1,
        }
        if mtd_start_date:
            account_summary['mtd_start_date'] = mtd_start_date
        return {
            'message': '龙星行日报账号配置已重新写入 ACCOUNTS' if reconfigured else '龙星行日报账号配置已写入 ACCOUNTS',
            'reconfigured': reconfigured,
            'account': account_summary,
        }

    def _apply_persisted_config(self) -> None:
        data = self._load_store()
        for item in data.get('lead_scripts', []):
            self._register_lead_script(item)
        for item in data.get('split_stores', []):
            self._register_split_store(item)

    def _register_lead_script(self, item: dict[str, Any]) -> None:
        script = StoreScript(
            item['store_code'],
            item['store_name'],
            item.get('city', ''),
            item.get('brand', ''),
            list(item.get('keywords') or [item['store_name']]),
            item['script_path'],
            item.get('folder_name') or item['store_name'],
        )
        self.lead_service.registry.upsert(script)

    def _register_split_store(self, item: dict[str, Any]) -> None:
        store = SplitStore(
            item['store_code'],
            item['store_name'],
            item.get('file_prefix') or item['store_name'],
            item.get('script_name') or f"split_excel_{item['store_name']}-模板.py",
        )
        self.split_service.upsert_store(store)

    def _lead_store_exists(self, store_name: str) -> bool:
        return any(store.folder_name == store_name or store.store_name == store_name for store in self.lead_service.registry.list_stores())

    def _configured_tenant_names(self) -> set[str]:
        text = self.outcall_config_path.read_text(encoding='utf-8') if self.outcall_config_path.exists() else ''
        return set(re.findall(r'^\s*-\s+name:\s+["\']?([^"\'\n]+)', text, flags=re.MULTILINE))

    def _append_tenant_yaml(self, tenant: dict[str, Any]) -> None:
        self.outcall_config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.outcall_config_path.exists():
            self.outcall_config_path.write_text('environment: test\nsettings: {}\ntenants:\n', encoding='utf-8')
        block = self._tenant_yaml_block(tenant)
        text = self.outcall_config_path.read_text(encoding='utf-8').rstrip()
        if 'tenants:' not in text:
            text += '\n\ntenants:'
        self.outcall_config_path.write_text(f'{text}\n{block}\n', encoding='utf-8')

    def _tenant_yaml_block(self, tenant: dict[str, Any]) -> str:
        quote = lambda value: json.dumps(str(value), ensure_ascii=False)
        lines = [f'  - name: {quote(tenant["name"])}', '    prefixes:']
        for prefix in tenant['prefixes']:
            lines.append(f'      - {quote(prefix)}')
        lines.extend(['    environments:', '      test:'])
        for key in ('username', 'password', 'robot_id', 'dealer_id'):
            lines.append(
                f'        {key}: {quote(tenant["environments"]["test"].get(key, ""))}'
            )
        lines.append('      prod:')
        for key in ('username', 'password', 'robot_id', 'dealer_id'):
            lines.append(
                f'        {key}: {quote(tenant["environments"]["prod"].get(key, ""))}'
            )
        lines.append('    task_name_template: "{tenant}{date}-{batch}"')
        return '\n'.join(lines)

    def _recorder_path(self) -> Path:
        return self.daily_project_root / 'tools' / 'recorder.py'

    def _load_daily_accounts(self) -> list[dict[str, Any]]:
        text = self._recorder_path().read_text(encoding='utf-8')
        module = ast.parse(text)
        for node in module.body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'ACCOUNTS' for target in node.targets):
                value = ast.literal_eval(node.value)
                if not isinstance(value, list):
                    raise ConfigValidationError('ACCOUNTS 不是列表')
                return value
        raise ConfigValidationError('未找到 ACCOUNTS 配置')

    def _write_daily_accounts(self, accounts: list[dict[str, Any]]) -> None:
        path = self._recorder_path()
        text = path.read_text(encoding='utf-8')
        module = ast.parse(text)
        account_node = None
        for node in module.body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'ACCOUNTS' for target in node.targets):
                account_node = node
                break
        if account_node is None or not hasattr(account_node, 'end_lineno'):
            raise ConfigValidationError('无法定位 ACCOUNTS 配置块')
        lines = text.splitlines()
        rendered = 'ACCOUNTS = ' + pprint.pformat(accounts, width=120, sort_dicts=False)
        lines[account_node.lineno - 1:account_node.end_lineno] = rendered.splitlines()
        updated_text = '\n'.join(lines) + '\n'
        try:
            ast.parse(updated_text)
        except SyntaxError as exc:
            raise ConfigValidationError(f'生成的 ACCOUNTS 配置语法无效：{exc}') from exc
        temporary_path = path.with_suffix('.py.tmp')
        temporary_path.write_text(updated_text, encoding='utf-8')
        temporary_path.replace(path)

    def _load_store(self) -> dict[str, Any]:
        if not self.store_path.exists():
            return {'lead_scripts': [], 'split_stores': []}
        try:
            return json.loads(self.store_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            raise ConfigValidationError(f'配置中心持久化文件损坏：{exc}') from exc

    def _save_store(self, data: dict[str, Any]) -> None:
        self.store_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def _store_code(self, prefix: str, store_name: str) -> str:
        digest = hashlib.sha1(store_name.encode('utf-8')).hexdigest()[:10]
        ascii_part = re.sub(r'[^a-z0-9]+', '_', store_name.lower()).strip('_')
        if ascii_part:
            return f'{prefix}_{ascii_part}_{digest}'
        return f'{prefix}_custom_{digest}'

    def _safe_filename(self, value: str) -> str:
        return re.sub(r'[\\/:*?"<>|\r\n]+', '_', value).strip() or '未命名门店'

    def _require_text(self, value: Any, field: str) -> str:
        text = self._text(value)
        if not text:
            raise ConfigValidationError(f'{field} 不能为空')
        return text

    def _optional_report_date(self, value: Any, field: str) -> str:
        text = self._text(value)
        if not text:
            return ''
        if not re.fullmatch(r'[0-9]{6}', text):
            raise ConfigValidationError(f'{field} 必须使用 YYMMDD 格式')
        try:
            datetime.strptime(text, '%y%m%d')
        except ValueError as exc:
            raise ConfigValidationError(f'{field} 不是有效日期') from exc
        return text

    def _text(self, value: Any) -> str:
        return str(value or '').strip()

    def _as_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return self._text(value).lower() in {'1', 'true', 'yes', 'y'}

    def _split_values(self, value: Any) -> list[str]:
        if isinstance(value, list):
            raw = []
            for item in value:
                raw.extend(self._split_values(item))
            return raw
        text = self._text(value)
        if not text:
            return []
        return [part.strip() for part in re.split(r'[\n,，]+', text) if part.strip()]

    def _parse_mapping(self, value: Any) -> dict[str, str]:
        text = self._text(value)
        if not text:
            return {}
        mapping: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if ':' in line:
                key, val = line.split(':', 1)
            elif '：' in line:
                key, val = line.split('：', 1)
            else:
                raise ConfigValidationError(f'映射格式错误：{line}')
            mapping[key.strip()] = val.strip()
        return mapping
