# Module scope

本规则覆盖任务记录 API 和聚合服务，以及前端任务记录页面。

# Source of truth

- api.py：/api/task-records 查询参数和结构化错误。
- service.py：任务类型、状态显示、内存任务、文件系统扫描、日期筛选和去重。
- server.py：将线索导入、预分割、外呼和日报服务注入 TaskRecordService。
- aicc-frontend-demo.html：任务类型和日期筛选、刷新、详情和下载交互。

# Implementation rules

- 任务记录是聚合视图，不是第二套任务执行器。不得在查询中启动、重跑、停止或修改源任务。
- 保持任务类型代码稳定：lead_import、split_preview、outcall_test、outcall_formal、daily_report。
- 内存任务优先提供实时状态；文件系统扫描用于补充重启前产物。去重必须避免同一输出同时显示为 memory 和 filesystem。
- 文件系统扫描只读取已配置的输入/输出根目录，并忽略 Excel 临时文件。
- 任务名称、执行人、时间、输入和输出字段是前端契约。新增任务类型时同步更新 TASK_TYPES、状态映射、前端筛选和详情。
- 日期输入使用 YYYY-MM-DD；无指定日期时按 days 形成包含当天的区间。
- 错误展示只保留可操作摘要，不泄露客户数据、凭据或完整日志。

# Validation

当前没有独立任务记录测试文件。修改本模块时应新增针对聚合、日期过滤、去重和文件扫描的测试，并至少运行：

~~~
python -m pytest tests -q
~~~

通过本地 API 验证全部任务类型、单类型筛选、近一周和指定日期。
