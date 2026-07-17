# Module scope

本规则覆盖机器人用量监控运行目录，并通过根 AGENTS.md 的路由适用于 `glm-proxy/robot_quota` 和对应前端页面。

# Source of truth

- `glm-proxy/robot_quota/service.py`：日报复用、原始话单处理、限额计算、Excel 和图片任务。
- `glm-proxy/robot_quota/report_renderer.py`：保留周报 Skill 的解析、频次、每日 Top3 和图片渲染逻辑，并提供日报模式。
- `龙星行报表工具_核心文件_260629/tools/recorder.py` 的 `ACCOUNTS`：账户、目标机器人、展示名及可选限额和 ID 映射。
- `glm-proxy/tests/test_robot_quota.py`：统计口径、文件契约、图片和 API 验证。

# Data rules

- 目标日期按原始话单的结束时间筛选，缺失时才回退开始时间。
- 通话状态或通话详情包含“线路限制”的记录不得计入 A。
- B 必须保存为比例数值，Excel 使用百分比格式展示。
- 配额优先使用账户 `robot_quotas` 中的机器人映射，其次使用账户 `daily_call_quota`；均未配置时默认 200，名称同时包含“番禺”和“售后”的机器人默认 400。
- `required_group_values` 是多机器人账户的统计白名单，不得把同租户其它机器人混入结果。
- 不得伪造机器人 ID；无法从原始数据、配置、缓存或平台任务元数据确认时必须标记未识别并给出警告。
- 每日 Excel 的 `超量记录` Sheet 保持日报/周报 Skill 输入格式，`用量明细` Sheet 保存全部机器人明细；修改任一端时同步验证解析契约。

# Safety boundary

- 自动测试不得登录生产平台，使用临时 Excel 和注入的 runner/resolver。
- 日志、错误和 API 响应不得包含 ACCOUNTS 中的用户名、密码、token 或 Cookie。
- `data`、`reports`、`logs` 和 `config/robot_ids.json` 是运行产物，不手工编辑来模拟完成。

# Validation

修改统计或图片逻辑后运行 `venv\Scripts\python.exe -m pytest tests/test_robot_quota.py -q`。修改服务装配或任务记录后运行完整 `tests`，前端变更必须通过 18765 本地 HTTP 页面验证。
