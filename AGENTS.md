# Repository overview

AICC 运营工作台是一个内部运营平台。活动前端是仓库根目录的 aicc-frontend-demo.html；FastAPI 应用由 线索变量脚本/glm-proxy/server.py 组装并提供页面、API 和任务服务。线索导入、预分割与外呼、日报工具保留各自原有 Python 核心，通过 glm-proxy 中的适配服务接入。

# Source-of-truth files

- 线索变量脚本/glm-proxy/server.py：应用组装、路径解析、路由注册和本地页面入口。
- aicc-frontend-demo.html：当前工作台前端。不要把 线索变量脚本/frontend 自动视为活动前端。
- 线索变量脚本/glm-proxy/requirements.txt：平台后端依赖。
- 建银-线索自动预分割与导入脚本/建银-线索自动预分割与导入脚本/config.yaml：外呼环境和租户配置，包含敏感值。
- 龙星行报表工具_核心文件_260629/tools/recorder.py 中的 ACCOUNTS：日报账户和机器人分组配置，包含敏感值。
- 各功能目录的 AGENTS.md：模块专属规则；修改跨目录适配代码时按下方路由读取。

# Project structure

- 线索变量脚本/glm-proxy：FastAPI 服务、五个功能适配包、SQLite、上传输出和测试。
- 线索变量脚本/线索变量脚本：线索导入的门店处理脚本。
- 线索变量脚本/建银线索：线索导入运行数据和 TXT 输出。
- 建银-线索自动预分割与导入脚本/建银-线索自动预分割与导入脚本：预分割模板、批次文件、外呼配置和租户处理核心。
- 龙星行报表工具_核心文件_260629：日报抓取、处理、汇总、预览源数据和输出。
- .agents/skills：仓库本地 Codex Skills。

# Setup and development commands

后端命令从 线索变量脚本/glm-proxy 运行：

~~~
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
python server.py --port 18765
~~~

start.bat 会创建 venv、安装 requirements.txt 并启动 server.py。工作台通过 http://127.0.0.1:18765/aicc-frontend-demo.html 访问；不要使用 file URL 验证依赖 API 的功能。

三个核心工具各有自己的 requirements.txt。仅在直接运行对应核心工具时安装其依赖。

# Build, test, lint and typecheck

平台没有前端构建步骤；根 HTML 由 FastAPI 直接提供。后端测试从 线索变量脚本/glm-proxy 运行：

~~~
python -m pytest tests -q
~~~

优先运行受影响模块的测试，再在跨模块或服务装配变更后运行完整测试集。仓库当前没有统一 lint、format 或 typecheck 配置；不要虚构命令。至少对修改的 Python 文件执行语法检查，对前端脚本执行 JavaScript 语法检查并通过本地 HTTP 页面验证。

# Architecture and implementation conventions

- 保持 API、service、models/repository 和旧核心工具之间的适配边界。除非任务明确要求，不重构旧脚本。
- FastAPI 错误保持结构化 code、message、detail；前端按 code 处理可恢复冲突。
- 文件名、门店名、批次名和任务类型是前后端契约。修改时同步检查 API、前端和任务记录。
- 路径由 server.py 的环境变量覆盖或仓库相对默认值解析；不要在新代码中新增仅适用于一台机器的绝对路径。
- 前端展示手机号等敏感字段时必须脱敏；日志和错误不得回显密码、令牌或完整客户数据。
- 所有外部平台调用、生产外呼、日报重拉和批次停止都属于有副作用操作。测试优先使用临时目录、伪服务或已存在的单元测试。

# Change boundaries

- 保留工作树中无法解释的现有修改，不回滚、不覆盖。
- 不在文档、测试夹具、日志或响应中复制 config.yaml、recorder.py 中的凭据值。
- 不手工修改运行生成的 Excel、TXT、SQLite 或日志来模拟功能完成。
- 对会清空或覆盖当日输出目录的逻辑，必须限制到目标日期和门店，并保留确认或冲突处理。

# Generated files

以下内容是运行产物或本地环境，不作为手工维护的源文件：venv、__pycache__、.pytest_cache、glm-proxy/storage、glm-proxy/uploads、glm-proxy/outputs、线索预分割下的日期目录、龙星行报表工具 data 下的日期和区间目录、建银线索中的任务输入输出、日志、SQLite、Excel 临时文件。

config_center/config_store.json 由配置中心服务维护；如需改变格式，应修改服务和迁移逻辑，不直接编辑运行副本。

# Validation requirements

- API 变更：验证成功响应、结构化错误和至少一个失败分支。
- 文件处理变更：使用临时目录或测试夹具验证文件名、行数、覆盖范围和输出内容。
- 外呼变更：运行恢复/队列测试；不得用生产平台作为自动验证。
- 日报变更：运行日报与月度汇总测试，并检查生成文件或图片预览。
- 前端变更：通过 18765 本地服务打开页面，检查控制台和相关 API 请求。

# Directory-specific routing

- 线索导入：读取 线索变量脚本/glm-proxy/lead_import/AGENTS.md。该规则也适用于门店脚本目录和前端线索导入界面。
- 线索预分割与自动外呼：读取 建银-线索自动预分割与导入脚本/建银-线索自动预分割与导入脚本/AGENTS.md。修改 glm-proxy/split_import、glm-proxy/outcall 或对应前端时同样适用。
- 龙星行日报：读取 龙星行报表工具_核心文件_260629/AGENTS.md。修改 glm-proxy/daily_report 或日报前端时同样适用。
- 任务记录：读取 线索变量脚本/glm-proxy/task_records/AGENTS.md。
- 配置中心：读取 线索变量脚本/glm-proxy/config_center/AGENTS.md。

# Documentation expectations

只有长期稳定规则发生变化时更新 AGENTS.md。当前任务状态、一次性故障和未完成计划写入 TASK_STATE.md，不得写入 AGENTS.md。新增 API 或配置格式时同步更新相关 README、模块 AGENTS.md 或现有说明文档。
