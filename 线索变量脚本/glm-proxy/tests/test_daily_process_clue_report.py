from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest


AICC_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = AICC_ROOT / '龙星行报表工具_核心文件_260629' / 'tools'
PROCESS_PATH = TOOLS_DIR / 'process_clue_report.py'


def load_process_module():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location(
        'daily_process_clue_report_under_test',
        PROCESS_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_daily_population_uses_dispatched_clues_and_separates_historical_calls(
    tmp_path,
):
    process = load_process_module()
    clues = pd.DataFrame(
        [
            {
                '线索ID': 'new-called',
                '线索下发时间': '2026-07-18 09:00:00',
                '客户手机号': '13800000001',
            },
            {
                '线索ID': 'new-pending',
                '线索下发时间': '2026-07-18 10:00:00',
                '客户手机号': '13800000002',
            },
        ]
    )
    calls = pd.DataFrame(
        [
            {
                '通话ID': 'call-1',
                '线索ID': 'new-called',
                '结束时间': '2026-07-18 10:00:00',
                '机器人': '机器人甲',
                '通话状态': '未接通',
                '客户真实号码': '13800000001',
            },
            {
                '通话ID': 'call-2',
                '线索ID': 'new-called',
                '结束时间': '2026-07-18 11:00:00',
                '机器人': '机器人甲',
                '通话状态': '已接通',
                '客户真实号码': '13800000001',
            },
            {
                '通话ID': 'call-3',
                '线索ID': 'history-called',
                '结束时间': '2026-07-18 12:00:00',
                '机器人': '机器人甲',
                '通话状态': '已接通',
                '客户真实号码': '13800000003',
            },
        ]
    )

    deduped = process.deduplicate_calls(calls, tmp_path, '测试门店')
    population, history_calls, diagnostics = process.build_daily_reporting_population(
        clues,
        deduped,
        pd.Timestamp('2026-07-18'),
        group_by_call_field='机器人',
        required_group_values=['机器人甲'],
        df_call_mtd=calls,
    )

    assert len(deduped) == 2
    assert set(population['线索ID']) == {
        'new-called',
        'new-pending',
    }
    assert population.set_index('线索ID').loc['new-called', '通话ID'] == 'call-2'
    assert population.set_index('线索ID').loc['new-pending', '机器人'] == '机器人甲'
    assert history_calls['线索ID'].tolist() == ['history-called']
    assert diagnostics == {
        'daily_dispatched_clues': 2,
        'daily_called_clues': 2,
        'daily_dispatched_called_clues': 1,
        'daily_called_historical_clues': 1,
        'daily_uncalled_clues': 1,
        'daily_population': 2,
    }
    duplicate_file = tmp_path / '测试门店_重复线索话单.xlsx'
    assert duplicate_file.exists()
    duplicate_calls = pd.read_excel(duplicate_file, engine='openpyxl')
    assert len(duplicate_calls) == 2
    assert set(duplicate_calls['通话ID']) == {'call-1', 'call-2'}
    assert set(duplicate_calls['同线索当日话单数']) == {2}


def test_daily_call_count_excludes_historical_and_recall_clues():
    process = load_process_module()
    raw_calls = pd.DataFrame(
        [
            {'线索ID': 'new-called', '通话ID': 'call-1'},
            {'线索ID': 'new-called', '通话ID': 'call-2'},
            {'线索ID': 'history-called', '通话ID': 'call-3'},
        ]
    )
    daily_population = pd.DataFrame(
        [
            {'线索ID': 'new-called'},
            {'线索ID': 'new-pending'},
        ]
    )

    assert process.count_calls_for_clue_population(
        raw_calls,
        daily_population,
    ) == 2


def test_uncalled_daily_clue_is_counted_as_unconnected():
    process = load_process_module()
    population = pd.DataFrame(
        [
            {
                '线索ID': 'called',
                '通话状态': '已接通',
                '线索状态': '有效',
                '客户意向等级': '高意向',
                '通话状态详情': '',
                '通话时长': 30,
                '通话ID': 'call-1',
                '客户真实号码': '13800000001',
            },
            {
                '线索ID': 'uncalled',
                '通话状态': pd.NA,
                '线索状态': pd.NA,
                '客户意向等级': pd.NA,
                '通话状态详情': pd.NA,
                '通话时长': pd.NA,
                '通话ID': pd.NA,
                '客户真实号码': pd.NA,
            },
        ]
    )
    history = pd.DataFrame(
        columns=['线索ID', '通话状态', '意向等级']
    )

    result = process.generate_report(
        population,
        history,
        total_xiansuo=2,
    )

    assert result['total'] == 2
    assert result['jietong_count'] == 1
    assert result['weijietong_count'] == 1
    assert result['top1_name'] == '无话单/未外呼'


def test_daily_population_regression_198_called_minus_81_history_is_117_new():
    process = load_process_module()
    target = pd.Timestamp('2026-07-18')
    clues = pd.DataFrame(
        [
            {
                '线索ID': f'new-{index}',
                '线索下发时间': target,
            }
            for index in range(117)
        ]
    )
    calls = pd.DataFrame(
        [
            {
                '线索ID': clue_id,
                '结束时间': target + pd.Timedelta(hours=10),
                '通话ID': f'call-{index}',
            }
            for index, clue_id in enumerate(
                [f'new-{index}' for index in range(117)]
                + [f'history-{index}' for index in range(81)]
            )
        ]
    )

    population, history_calls, diagnostics = (
        process.build_daily_reporting_population(clues, calls, target)
    )

    assert len(calls) == 198
    assert len(population) == 117
    assert len(history_calls) == 81
    assert diagnostics['daily_population'] == 117
    assert diagnostics['daily_called_historical_clues'] == 81


def test_daily_population_filters_date_before_deduplicating_clue_ids():
    process = load_process_module()
    clues = pd.DataFrame(
        [
            {
                '线索ID': 'reimported',
                '线索下发时间': '2026-07-18 09:00:00',
            },
            {
                '线索ID': 'reimported',
                '线索下发时间': '2026-07-19 09:00:00',
            },
        ]
    )
    calls = pd.DataFrame(
        [
            {
                '线索ID': 'reimported',
                '结束时间': '2026-07-18 10:00:00',
                '通话ID': 'call-1',
            }
        ]
    )

    population, _, diagnostics = process.build_daily_reporting_population(
        clues,
        calls,
        pd.Timestamp('2026-07-18'),
    )

    assert population['线索ID'].tolist() == ['reimported']
    assert diagnostics['daily_population'] == 1


def test_group_reconciliation_keeps_unmatched_multi_robot_clues_visible():
    process = load_process_module()
    population = pd.DataFrame(
        [
            {'线索ID': '1', '机器人': '机器人甲'},
            {'线索ID': '2', '机器人': '未匹配机器人'},
            {'线索ID': '3', '机器人': '其它机器人'},
        ]
    )

    result = process.reconcile_group_population(
        population,
        '机器人',
        ['机器人甲', '机器人乙'],
    )

    assert result == {
        'source_total': 3,
        'included': 1,
        'excluded': 1,
        'unmatched': 1,
    }


def test_daily_population_uses_clue_robot_mapping_for_uncalled_multi_robot_clue():
    process = load_process_module()
    clues = pd.DataFrame(
        [
            {
                '线索ID': 'pending-a',
                '线索下发时间': '2026-07-18 09:00:00',
                '客户手机号': '13800000001',
                '机器人': '机器人甲',
            },
            {
                '线索ID': 'pending-b',
                '线索下发时间': '2026-07-18 09:30:00',
                '客户手机号': '13800000002',
                '机器人': '机器人乙',
            },
        ]
    )
    calls = pd.DataFrame(
        columns=['线索ID', '结束时间', '机器人', '通话ID']
    )

    population, _, _ = process.build_daily_reporting_population(
        clues,
        calls,
        pd.Timestamp('2026-07-18'),
        group_by_call_field='机器人',
        required_group_values=['机器人甲', '机器人乙'],
        df_call_mtd=calls,
    )

    assert population.set_index('线索ID')['机器人'].to_dict() == {
        'pending-a': '机器人甲',
        'pending-b': '机器人乙',
    }


def test_junyi_tenant_keeps_sixty_shaoguan_clues_and_zero_junyi_clues():
    process = load_process_module()
    junyi_robot = '龙星行-广州龙星骏宜'
    shaoguan_robot = '龙星行-新车首呼-广东韶关'
    clues = pd.DataFrame(
        [
            {
                '线索ID': f'shaoguan-{index}',
                '线索下发时间': '2026-07-18 09:00:00',
                '客户手机号': f'138****{index:04d}',
                '机器人': shaoguan_robot,
            }
            for index in range(60)
        ]
    )
    calls = pd.DataFrame(columns=['线索ID', '结束时间', '机器人', '通话ID'])

    population, _, diagnostics = process.build_daily_reporting_population(
        clues,
        calls,
        pd.Timestamp('2026-07-18'),
        group_by_call_field='机器人',
        required_group_values=[junyi_robot, shaoguan_robot],
        df_call_mtd=calls,
    )

    counts = population.groupby('机器人').size().to_dict()
    assert diagnostics['daily_dispatched_clues'] == 60
    assert counts.get(shaoguan_robot) == 60
    assert counts.get(junyi_robot, 0) == 0


def test_monthly_group_stats_prefers_clue_robot_and_falls_back_to_call_robot():
    process = load_process_module()
    clues = pd.DataFrame(
        [
            {
                '线索ID': 'clue-mapped',
                '机器人': '机器人甲',
                '通话状态': '已接通',
                '线索状态': '有效',
            },
            {
                '线索ID': 'call-fallback',
                '机器人': '',
                '通话状态': '未接通',
                '线索状态': '无效',
            },
        ]
    )
    calls = pd.DataFrame(
        [
            {
                '线索ID': 'clue-mapped',
                '机器人': '错误的话单机器人',
                '结束时间': pd.Timestamp('2026-07-22 10:00:00'),
                '通话状态': '已接通',
            },
            {
                '线索ID': 'call-fallback',
                '机器人': '机器人乙',
                '结束时间': pd.Timestamp('2026-07-22 11:00:00'),
                '通话状态': '未接通',
            },
        ]
    )

    stats = process.build_monthly_stats_by_group(clues, calls, '机器人')

    assert stats['机器人甲']['累计线索量'] == 1
    assert stats['机器人乙']['累计线索量'] == 1
    assert '错误的话单机器人' not in stats


def test_monthly_stats_uses_terminal_clue_status_and_all_calls():
    process = load_process_module()
    clues = pd.DataFrame([
        {'线索ID': '1', '通话状态': '已接通', '线索状态': '有效'},
        {'线索ID': '2', '通话状态': '未接通', '线索状态': '待定'},
    ])
    calls = pd.DataFrame([
        {'线索ID': '1'},
        {'线索ID': '1'},
        {'线索ID': '2'},
    ])

    stats = process.build_monthly_stats(clues, calls)

    assert stats == {
        '累计线索量': 2,
        '累计接通量': 1,
        '累计有效线索量': 1,
        '累计呼叫通次': 3,
    }


def test_daily_population_falls_back_to_history_and_marks_unmatched():
    process = load_process_module()
    clues = pd.DataFrame(
        [
            {
                '线索ID': 'history-mapped',
                '线索下发时间': '2026-07-18 09:00:00',
                '客户手机号': '13800000001',
                '机器人': '',
            },
            {
                '线索ID': 'still-unmatched',
                '线索下发时间': '2026-07-18 09:30:00',
                '客户手机号': '13800000002',
                '机器人': '',
            },
        ]
    )
    daily_calls = pd.DataFrame(
        columns=['线索ID', '结束时间', '机器人', '通话ID']
    )
    historical_calls = pd.DataFrame(
        [
            {
                '线索ID': 'history-mapped',
                '结束时间': '2026-07-17 12:00:00',
                '机器人': '机器人乙',
                '通话ID': 'old-call',
            }
        ]
    )

    population, _, _ = process.build_daily_reporting_population(
        clues,
        daily_calls,
        pd.Timestamp('2026-07-18'),
        group_by_call_field='机器人',
        required_group_values=['机器人甲', '机器人乙'],
        df_call_mtd=historical_calls,
    )

    assert population.set_index('线索ID')['机器人'].to_dict() == {
        'history-mapped': '机器人乙',
        'still-unmatched': '未匹配机器人',
    }
    assert process.reconcile_group_population(
        population,
        '机器人',
        ['机器人甲', '机器人乙'],
    ) == {
        'source_total': 2,
        'included': 1,
        'excluded': 0,
        'unmatched': 1,
    }


def test_historical_rebuild_uses_later_call_for_robot_mapping():
    process = load_process_module()
    clues = pd.DataFrame([
        {
            '线索ID': 'called-later',
            '线索下发时间': '2026-07-01 09:00:00',
            '客户手机号': '13800000001',
            '机器人': '',
        },
    ])
    no_same_day_calls = pd.DataFrame(
        columns=['线索ID', '结束时间', '机器人', '通话ID']
    )
    complete_month_calls = pd.DataFrame([
        {
            '线索ID': 'called-later',
            '结束时间': '2026-07-20 12:00:00',
            '机器人': '机器人乙',
            '通话ID': 'later-call',
        },
    ])

    population, _, diagnostics = process.build_daily_reporting_population(
        clues,
        no_same_day_calls,
        pd.Timestamp('2026-07-01'),
        group_by_call_field='机器人',
        required_group_values=['机器人甲', '机器人乙'],
        df_call_mtd=complete_month_calls,
    )

    assert population.set_index('线索ID').loc['called-later', '机器人'] == '机器人乙'
    assert diagnostics['daily_uncalled_clues'] == 1


def test_group_reconciliation_rejects_unmatched_clues():
    process = load_process_module()

    with pytest.raises(ValueError, match='无法匹配机器人'):
        process.validate_group_reconciliation(
            {
                'source_total': 2,
                'included': 1,
                'excluded': 0,
                'unmatched': 1,
            },
            '测试租户',
        )


def test_excel_artifact_uses_timestamped_fallback_when_target_is_locked(
    monkeypatch, tmp_path
):
    process = load_process_module()
    target = tmp_path / '门店_通话列表_去重.xlsx'
    frame = pd.DataFrame([{'线索ID': '1'}])
    original_to_excel = pd.DataFrame.to_excel

    def fake_to_excel(self, path, *args, **kwargs):
        if Path(path) == target:
            raise PermissionError('target is locked')
        return original_to_excel(self, path, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, 'to_excel', fake_to_excel)
    written = process.write_excel_artifact(frame, target)

    assert written != target
    assert written.exists()
    assert written.name.startswith('门店_通话列表_去重_本次生成_')


def test_daily_population_fills_nonempty_call_intent_into_string_column():
    process = load_process_module()
    clues = pd.DataFrame(
        {
            '线索ID': pd.Series(['called', 'pending'], dtype='string'),
            '线索下发时间': ['2026-07-18 09:00:00', '2026-07-18 10:00:00'],
            '客户意向等级': pd.Series([pd.NA, pd.NA], dtype='string'),
        }
    )
    calls = pd.DataFrame(
        [
            {
                '线索ID': 'called',
                '结束时间': '2026-07-18 11:00:00',
                '意向等级': '高意向',
            }
        ]
    )

    population, _, _ = process.build_daily_reporting_population(
        clues, calls, pd.Timestamp('2026-07-18')
    )

    intents = population.set_index('线索ID')['客户意向等级']
    assert intents['called'] == '高意向'
    assert pd.isna(intents['pending'])
