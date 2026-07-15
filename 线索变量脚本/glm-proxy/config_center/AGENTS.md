# Module scope

本规则覆盖配置中心 API、配置写入服务和前端配置中心表单。

# Source of truth

- api.py：/api/config-center 的 summary、lead-scripts、split-stores、outcall-tenants 和 daily-accounts。
- service.py：输入校验、冲突处理、注册表更新和目标文件写入。
- config_store.json：配置中心维护的线索脚本与预分割门店持久化数据。
- 外呼 config.yaml：tenants 和 test/prod 环境配置。
- 日报 tools/recorder.py 中的 ACCOUNTS：日报账号与机器人配置。
- tests/test_daily_account_configuration.py：日报账号新增、动态注册、重配确认和 API 回归。

# Write contracts

- 新增或更新线索脚本只接受 py；门店模板只接受 xlsx；路径和文件名必须经过安全化。
- 线索脚本和预分割门店写入 config_store.json 后，必须同步更新运行中的 registry 或 stores。
- 外呼租户写入 config.yaml 的 tenants，保持 task_name_template 和 test/prod 层级。不要把凭据返回给前端或写入日志。
- 日报账户只替换 recorder.py 的 ACCOUNTS 赋值。写入前解析并校验 Python 语法，使用临时文件替换，保留表单未管理的高级字段。mtd_start_date 是配置中心管理的可选 YYMMDD 字段，空值会清除该门店已有的 MTD 下界。
- 同名日报账户先返回 DAILY_ACCOUNT_RECONFIGURE_REQUIRED；只有用户确认后的 force_reconfigure 才原位替换，禁止重复追加。
- 所有校验错误和冲突使用结构化 code、message、detail，并保持 422/409 等语义状态。

# Change boundaries

- 不直接编辑运行生成的 config_store.json 来实现功能；修改服务逻辑并通过 API 或测试验证。
- config.yaml 和 recorder.py 含敏感值。读取时只提取结构，不在响应、测试快照、文档或日志中复制密码、token、cookie 或完整账户对象。
- 写入多个目标时说明部分失败行为；不要把计划中的跨文件更新报告为已完成。

# Validation

日报配置变更运行：

~~~
python -m pytest tests/test_daily_account_configuration.py -q
~~~

线索、预分割或外呼配置变更应增加对应 API 和持久化测试。所有配置中心变更还需验证服务重启后能重新加载配置，并在跨模块变更后运行完整 tests。
