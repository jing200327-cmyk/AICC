# Module scope

本规则覆盖线索导入 FastAPI 适配包，并通过根 AGENTS.md 的路由覆盖 线索变量脚本/线索变量脚本 中的门店脚本、线索变量脚本/建银线索 的运行目录和前端线索导入界面。

# Source of truth

- api.py：/api/leads/import 接口、上传、任务详情和 TXT 下载。
- service.py：文件大小与扩展名校验、多 Sheet 选择、门店确认、输入保存和任务状态。
- registry.py：内置门店代码、展示名、关键词、脚本路径和输出文件夹映射。
- processor.py：Excel/CSV 读取、字段标准化和 TXT 生成。
- 线索变量脚本/线索变量脚本 下的门店 Python 文件：旧门店处理逻辑。
- tests/test_lead_import.py：门店识别、多 Sheet、上传、错误和下载契约。

# Implementation rules

- 前端明确选择的门店通过 force_store_code 决定脚本；自动识别只能作为候选和校验信息。
- 多 Sheet 文件必须先返回 SHEET_SELECTION_REQUIRED，再以用户选择的合法 Sheet 重试。
- 上传文件名只使用 basename；继续限制扩展名、空文件、大小和 Sheet 名。
- 内置门店映射修改时同步检查 registry.py、门店脚本文件名、folder_name 和前端选项。配置中心新增门店走 registry.upsert，不要复制一套旁路注册表。
- 保持 LeadImportJob 的 completed、failed、need_confirmation 状态及结构化错误契约。
- TXT 和输入文件包含客户敏感信息。前端预览需脱敏或限制展示，日志不得记录完整手机号和整行客户数据。

# File boundaries

- 建银线索中的 Excel/TXT 是任务产物，不作为源代码编辑。
- 默认门店脚本先通过适配层调用；除非需求明确，不批量改写旧脚本。
- 输出必须留在目标门店文件夹，禁止根据未校验的上传路径写入任意目录。

# Validation

从 glm-proxy 运行：

~~~
python -m pytest tests/test_lead_import.py -q
~~~

改变通用服务、server.py 或前端契约后再运行完整 tests。至少覆盖选定门店、多 Sheet、失败结构和 TXT 下载。
