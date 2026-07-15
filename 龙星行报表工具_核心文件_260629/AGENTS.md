# Module scope

本规则覆盖龙星行日报核心工具，并通过根 AGENTS.md 的路由覆盖 glm-proxy/daily_report 和前端日报工作台。

# Source of truth

- main.py：日报入口、账户选择、抓取结果处理和 process_clue_report.py 调用。
- tools/recorder.py 中的 ACCOUNTS：门店账号、机器人分组、展示名、汇总名和上线日期。
- tools/process_clue_report.py：原始话单/线索清洗、关联、日报和汇总表生成。
- glm-proxy/daily_report/service.py：任务执行、动态门店分区、月度横向汇总、全门店汇总和图片预览。
- README.md、日度月度汇总表数据计算说明.md：运行方法和指标口径。
- glm-proxy/tests/test_daily_monthly_summary.py 与 test_daily_account_configuration.py：汇总口径、补数、动态配置和 API 契约。

# Runtime contract

- REPORT_DATE 使用 YYMMDD；REPORT_STORE 选择 ACCOUNTS 中的门店或 all。
- REPORT_OUTPUT_DIR 可改变输出根；REPORT_REFRESH_CLUE 控制是否重拉线索明细。
- 标准入口是 main.py。已有原始 Excel 时可按 README 直接运行 tools/process_clue_report.py，但参数和日期必须对应。
- 新门店和机器人必须通过 ACCOUNTS 的 name、分组字段、显示名和汇总名贯通抓取、处理、预览和月度汇总。
- 上线日期 mtd_start_date 决定月度补数起点；上线前日期必须跳过，不伪造零数据。

# Data and reporting rules

- data/YYMMDD 和 data/YYMMDD_YYMMDD 是运行产物。不要手工修改日报、汇总表或原始数据来掩盖处理问题。
- 保留 Excel 样式、数字格式、百分比和机器人列对齐；读取数值时不要把 64.74% 变为 6474%。
- 多机器人账户按 required_group_values 过滤；展示名、汇总名和合并标题必须与实际产出文件一致。
- 动态预览和月度门店列表从当前 ACCOUNTS 派生；不要为新门店再增加独立静态列表。
- 月份模式默认按自然月累计；账户可用 mtd_start_date（YYMMDD）配置 MTD 下界。自定义日期范围从范围起点连续累计；若账户下界更晚则取较晚日期，并使用覆盖有效范围的跨月原始快照重算全部日期。MTD 线索与话单都不得早于该有效起点。
- 全门店汇总只收集目标日期汇总目录中的门店汇总表，排除自身生成的总表。

# Safety boundary

recorder.py 含登录凭据。不得在日志、错误、文档、测试或 API 响应中输出凭据、cookie 或 token。真实抓取、重拉数据和补跑会访问外部平台；自动测试使用临时目录和模拟数据，不执行真实下载。

# Validation

从 glm-proxy 运行：

~~~
python -m pytest tests/test_daily_monthly_summary.py tests/test_daily_account_configuration.py -q
~~~

修改处理口径时同时验证日报、MTD、Daily、机器人分组、百分比格式和生成图片。修改 main.py 或 recorder.py 后执行 Python 语法检查；跨服务变更后运行完整 tests。
