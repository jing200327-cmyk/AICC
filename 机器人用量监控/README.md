# 外呼机器人用量监控

该目录保存 AICC 运营工作台“机器人用量监控”模块的运行产物。后端适配代码位于 `线索变量脚本/glm-proxy/robot_quota`。

## 统计口径

- A：目标日期话单中，排除通话状态包含“线路限制”的通话通次。
- B：`A / 每日限额`。
- B 大于 100% 时标记为“超量”。
- 默认每日限额为 200；机器人名称同时包含“番禺”和“售后”时默认限额为 400。
- `ACCOUNTS` 可通过 `daily_call_quota` 设置账户默认限额，通过 `robot_quotas` 为指定机器人设置限额。

## 原始数据

账户和机器人范围来自 `龙星行报表工具_核心文件_260629/tools/recorder.py` 的 `ACCOUNTS`。

1. 如果目标日期所有配置机器人已经生成日报且原始话单存在，直接复用日报目录中的话单。
2. 如果日报或原始话单缺失，按日报 `main.py` 链路补齐对应门店。
3. 多机器人账户只统计 `required_group_values` 中配置的机器人。

机器人 ID 按以下顺序解析：原始话单 ID 列、`ACCOUNTS.robot_ids`、本地缓存、平台任务列表的“任务名称到 robotId”映射。无法确认时写入“未识别”并返回警告，不生成虚假 ID。

## 输出结构

```text
机器人用量监控/
├── data/YYMMDD/
│   ├── 外呼机器人用量_YYMMDD.xlsx
│   └── 外呼机器人用量_YYMMDD.json
├── reports/daily/YYMMDD/
├── reports/weekly/YYMMDD_YYMMDD/
├── logs/YYMMDD/
└── config/robot_ids.json
```

每日 Excel 包含两个 Sheet：

- `超量记录`：与 `robot-quota-weekly-report` Skill 兼容，条目格式为 `• [机器人ID]机器人名称(最高XX.XX%)`。
- `用量明细`：包含所有机器人 ID、名称、门店、A、限额、B、状态和排除通次。

## API

- `POST /api/robot-quota/jobs`：提交指定日期用量任务。
- `GET /api/robot-quota/jobs/{job_id}`：轮询任务。
- `GET /api/robot-quota/preview`：读取指定日期明细。
- `GET /api/robot-quota/workbook`：下载每日 Excel。
- `POST /api/robot-quota/reports/daily`：生成日报 PNG。
- `POST /api/robot-quota/reports/weekly`：生成周报 PNG，周期最多 7 天。

## 验证

从 `线索变量脚本/glm-proxy` 运行：

```powershell
venv\Scripts\python.exe -m pytest tests/test_robot_quota.py -q
```
