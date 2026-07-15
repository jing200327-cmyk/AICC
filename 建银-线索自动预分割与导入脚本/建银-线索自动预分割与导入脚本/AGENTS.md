# Module scope

本规则覆盖线索预分割与自动外呼核心目录，并通过根 AGENTS.md 的路由覆盖 glm-proxy/split_import、glm-proxy/outcall 和前端对应工作台。

# Source of truth

- glm-proxy/split_import/service.py：门店注册、模板筛选、5 条测试线索、45 条正式批次、号码校验、覆盖与预览。
- config.yaml：test/prod 平台和 tenants 配置，包含敏感凭据。
- src/config.py：配置模型和环境解析。
- src/tenant_processor.py：登录、上传、创建外呼、顺序等待、监控和统计的核心链路。
- glm-proxy/outcall/service.py：任务创建、重呼检查、停止后续批次、恢复队列和平台状态对账。
- glm-proxy/outcall/repository.py：SQLite 中的任务与队列暂停状态。
- glm-proxy/tests/test_outcall_recovery.py：停止、恢复、持久化和顺序处理回归测试。

# Split rules

- 模板必须是当前门店前缀开头的 xlsx，并位于 split_root。
- 保持默认规则：前 5 条生成 测试 文件，其余从编号 2 开始每 45 条一批。
- 每次预览会清空目标日期/门店目录中的旧 xlsx，并清理旧版平铺输出。任何修改必须证明不会删除其他日期或门店文件。
- 分割输出位于 线索预分割/YYMMDD/门店。该目录及其中 Excel 是运行产物，不手工编辑为测试结果。
- 号码和变量转换应使用表格结构与明确字段，不用文本替换模拟 Excel 处理。

# Outcall rules

- 环境只接受 test 或 prod；具体平台地址和账号来自 config.yaml，不在代码或文档复制凭据。
- 正式批次必须按编号顺序处理；前一平台任务完成后才处理下一批。
- 恢复时对平台当天任务对账：完成批次跳过，运行批次只监控，平台不存在的批次才上传。
- 停止当前未外呼批次只暂停后续调度，不声称停止平台中正在外呼的任务。
- 生产环境重呼检查和用户确认不得绕过。force_restart 只能来自明确的重新发起交互。
- 外呼任务和暂停状态持久化到 glm-proxy/storage/aicc.sqlite3；不要用内存状态作为重启后的唯一依据。

# Safety boundary

不要在自动测试或普通验证中登录真实平台、上传线索、创建生产任务或停止真实任务。涉及真实外呼必须由用户明确指定门店、环境和动作。日志、测试输出和文档不得包含密码、token、完整手机号或客户明细。

# Validation

从 glm-proxy 运行：

~~~
python -m pytest tests/test_outcall_recovery.py -q
~~~

预分割逻辑变更还需使用临时 xlsx 验证测试批次、正式批次顺序、总行数和二次生成覆盖范围。跨适配层变更后运行完整 tests。
