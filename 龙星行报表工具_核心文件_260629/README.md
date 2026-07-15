# 龙星行线索数据报告自动化

版本：v3.0
更新：2026-06-15

自动登录外呼系统和呼叫系统，通过纯 API 爬取线索明细和通话列表，生成每日数据报告及日度月度汇总 Excel。

---

## 功能

1. **纯 API 爬取** — 通过 HTTP 接口直接导出数据，不再依赖 Playwright 浏览器自动化
2. **断点续爬** — 同一目录下文件已存在则自动跳过，支持中断后继续
3. **重试机制** — 每个账号最多 2 次重试，失败自动记录错误日志
4. **数据处理** — 通话列表去重、手机号脱敏同步、线索与通话基于线索ID匹配、phone 格式校验
5. **日报输出** — 结构化报告文本，含接通数/率、意向层级分布、未接通原因 TOP3、重呼情况
6. **日度月度汇总表** — 每次产出日报后自动生成汇总 Excel，包含：
   - MTD 板块：累计线索量/接通量/有效线索量（取自全月线索明细表筛选截止 `--date`）+ 呼叫通次（取自话单表筛选截止 `--date`）
   - Daily Report 板块：当日数据 + 昨日全天对比
7. **历史报告** — 指定 `--date` 重新处理，支持回溯任意日期
8. **按机器人分组统计** — 租户可配置按原话单表字段（如 `机器人`）拆分输出每日数据报告和汇总表
9. **多租户支持** — 建银 5 店 + 龙星行 5 店，共 10 个门店账号

> MTD 线索指标从全月线索明细表中筛选**截止至 `--date` 日期**的线索计算。例如用 17 号的文件处理 16 号的数据时，只统计月初～16 号的线索，而非全表。这样回溯历史日期时 MTD 不包含未来日期的线索。

---

## 技术架构

### 整体数据流

```
                    ┌─────────────────────────┐
                    │   tools/recorder.py      │
                    │   （纯 HTTP API 调用）   │
                    └──────────┬──────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       外呼系统(outcall   呼叫系统(aicc     数据写入
       -manage) 导出线索    -poc) 导出话单    本地文件
              │                │
              └────────┬───────┘
                       ▼
               data/{date}/原始数据/
               ├── {店名}-outcall-线索明细-{date}.xlsx
               └── {店名}-aicc-话单-{date}.xlsx
                       │
                       ▼
               tools/process_clue_report.py
               → 去重 / 脱敏 / 匹配 / 统计
                       │
                       ▼
               tools/daily_summary.py
               → data/{date}/汇总表/ + 每日报告/
```

### 接口清单

#### 已有接口（门店信息维护在用）

| 接口 | 方法 | 路径 | 功能 |
|------|------|------|------|
| 登录 | POST | `/bc/v1/users/login` | 获取 accessToken |

#### 爬取专用接口（v3.0 新增）

| 接口 | 方法 | 路径 | 响应类型 |
|------|------|------|---------|
| 导出线索明细 | POST | `/openapi-server/v2/call-clues/export-adviser-clue` | 直接返回 Excel 文件流 |
| 导出通话列表 | POST | `/esl/v2/task/export-task-list` | 返回 JSON，内含 TOS 临时下载链接 |

认证方式：`Authorization: Bearer {token}` + Cookie（`remember=true&username=xxx&password=xxx`）

> 详细接口文档见 `recorder-api迁移PRD-260615.md`

### 账号体系

| 系统 | 门店 | 账号数 | 配置位置 |
|------|------|--------|---------|
| 外呼系统 + 呼叫系统 | 建银（售后银马、武汉骏马店、林肯美诚售后、合肥建银马自达店、天翔林肯店） | 5 | `NEW_ACCOUNTS`（`run_jianyin_stores.py`） |
| 外呼系统 + 呼叫系统 | 龙星行（长沙、翔鹏、骏宜、海珠龙星行、广州龙星行） | 5 | `ACCOUNTS`（`tools/recorder.py`） |

两个系统共用同一套登录认证，一次登录获取通用 token。

---

## 安装

### 环境要求

- Python 3.8+
- macOS / Linux / Windows

### 步骤

```bash
# 1. 进入项目目录
cd "/Users/tangtangtang/工作/冰兰智能/龙星行-报表数据/报告产出脚本"

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate   # Mac/Linux
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt
```

### 依赖说明

| 包 | 用途 |
|---|------|
| `pandas` | 数据处理 |
| `openpyxl` | Excel 读写 |

> v3.0 已移除 `playwright` 依赖，无需安装 Chromium 浏览器。

---

## 运行

### 1. 全流程：爬取 + 处理 + 汇总

#### 建银 5 店

```bash
source venv/bin/activate
python run_jianyin_stores.py
```

流程：
1. `recorder.py` 登录 5 个建银账号 → 导出线索明细和话单
2. 原始文件保存到 `data/{YYMMDD}/原始数据/`
3. `process_clue_report.py` 读取原始文件 → 按当天筛选 → 去重/脱敏/匹配 → 输出日报文本
4. `daily_summary.py` 生成汇总 Excel → `data/{YYMMDD}/汇总表/`

#### 龙星行 5 店

```bash
python tools/recorder.py
# 或指定输出目录
python tools/recorder.py /path/to/output
```

### 2. 单独产出日报（已有原始文件）

```bash
python tools/process_clue_report.py \
  --call_file data/260614/原始数据/长沙-aicc-话单-260615.xlsx \
  --xiansuo_file data/260614/原始数据/长沙-outcall-线索明细-260615.xlsx \
  --company 长沙 \
  --date 260614 \
  --output_dir data/260614/
```

### 3. 按机器人分组统计

```bash
python tools/process_clue_report.py \
  --call_file data/260614/原始数据/广州龙星行-aicc-话单-260615.xlsx \
  --xiansuo_file data/260614/原始数据/广州龙星行-outcall-线索明细-260615.xlsx \
  --company 广州龙星行 \
  --date 260614 \
  --output_dir data/260614/ \
  --group_by_call_field 机器人 \
  --mtd_start_date 260518 \
  --merge_summary_title 广州 \
  --required_group_values "龙星行-广州龙星行-售后-活动招揽,龙星行-广州龙星行-售后-续保提醒" \
  --group_display_names '{"龙星行-广州龙星行-售后-活动招揽":"广州龙星行-售后-活动招揽","龙星行-广州龙星行-售后-续保提醒":"广州龙星行-售后-续保提醒"}' \
  --exclude_clue_ids "2056196796951138305,2056196098764095489,2056195749621841921,2056188808517488641,2056188808467156993,2056188808391659521"
```

配置后脚本会按话单表中指定字段拆分，输出多份日报和汇总表。

### 4. 重新生成历史日期报告

```bash
python run_history_reports.py
```

> 修改脚本中的 `DATES` 变量指定目标日期。

---

## 参数说明

### process_clue_report.py

| 参数 | 必填 | 说明 |
|------|------|------|
| `--call_file` | 是 | 通话列表 xlsx 路径 |
| `--company` | 是 | 门店名称，用于输出文件命名 |
| `--date` | 否 | 日期（YYMMDD），默认当天 |
| `--output_dir` | 否 | 输出目录，默认当前目录 |
| `--xiansuo_file` | 否 | 线索明细 xlsx 路径（不传则仅生成历史线索报告） |
| `--group_by_call_field` | 否 | 按话单字段分组统计，如 `机器人` |
| `--mtd_start_date` | 否 | MTD 起始日期（YYMMDD），不传则按月初计算 |
| `--required_group_values` | 否 | 强制输出的分组值，逗号分隔 |
| `--merge_summary_title` | 否 | 分组汇总表的文件标题 |
| `--group_display_names` | 否 | 分组展示名称映射，JSON 对象 |
| `--exclude_clue_ids` | 否 | 剔除的线索 ID，逗号或空白分隔 |
| `--clue_match_limit` | 否 | 仅使用筛选后前 N 条线索参与匹配 |

### recorder.py（crawl 函数）

```python
from tools.recorder import crawl

# 使用默认账号列表
result = crawl("/path/to/output")

# 或指定账号
result = crawl("/path/to/output", accounts=ACCOUNTS)

# 返回值：{店名: {"clue": Path, "call": Path}}
```

---

## 输出目录结构

```
data/{YYMMDD}/
├── 原始数据/                           # 爬取产出
│   ├── {店名}-outcall-线索明细-{date}.xlsx
│   └── {店名}-aicc-话单-{date}.xlsx
├── 中间文件/                           # 处理中间产物
│   ├── {店名}_通话列表_去重.xlsx
│   ├── 匹配结果_{店名}_当日线索通话记录表.xlsx
│   ├── 匹配结果_{店名}_历史线索通话记录表.xlsx
│   └── 匹配结果_{店名}_历史线索通话记录表_补充.xlsx
├── 每日报告/                           # 日报文本
│   ├── {店名}_每日报告_{date}.txt
│   └── {分组名}_每日报告_{date}.txt     # 有分组的门店
├── 汇总表/                             # Excel 汇总
│   └── {店名}_日度月度汇总表_{date}.xlsx
├── 错误日志/                           # 爬取失败记录
│   └── {店名}-错误日志-{date}-第N次.txt
└── 截图/                               # （旧版遗留，API 模式不再生成）
```

---

## 报告输出示例

```
【长沙 260510】推送新增线索量 250 条，其中：
① 接通线索 170 条（68.00%）
- 意向线索（36 条，接通数占比21%）
  - 状态：有效
- 无效线索（30 条，接通数占比18%）
  - 无意向：30 条
- 意向不明线索（104 条，接通数占比61%）
  - 未表明意向：64 条
  - 接通<=15秒：40 条

② 未接通线索（80 条，32.00%）
未接通原因TOP3：
- 未接通-拒接：28 条
- 未接通-暂时无法拨通：13 条
- 未接通-占线：12 条

③ 线索重呼情况：
- 线索量 60 条
- 接通 24 条
  - 其中意向线索 1 条
- 未接通 36 条
```

---

## 日度月度汇总表字段

### MTD（月至今累计）

| 字段 | 数据来源 | 说明 |
|------|---------|------|
| 累计线索量 | 全月线索明细表（截止至 `--date`） | 筛选 `线索下发时间 <= date` 后的行数 |
| 接通量 | 同上 | 同上范围中通话状态含"已接通" |
| 有效线索量 | 同上 | 同上范围中线索状态="有效" |
| 呼叫通次 | 全月话单表（截止至 `--date`） | 筛选 `结束时间 <= date` 后的行数 |
| 接通率/接通有效率/整体有效率 | — | 以上数值计算 |

### Daily Report（当日详情）

| 字段 | 数据来源 | 说明 |
|------|---------|------|
| 新增线索量 | 每日日报 | 线索下发时间==当天 |
| 昨日全天对比 | `_tracking/` JSON | 前一天的记录值 |
| 新增线索接通量 | 每日日报 | 当天接通线索数 |
| 新增线索呼叫通次 | 原始话单表 | 筛选后行数 |
| 比率指标 | — | 当天分子/分母重算 |

> 详细计算逻辑见 `日度月度汇总表数据计算说明.md`

---

## 支持的账号

### 建银 5 店

| 门店 | 账号 |
|------|------|
| 售后银马 | jyshym1234 |
| 武汉骏马店 | jywhjm12345 |
| 林肯美诚售后 | jyshmc123456 |
| 合肥建银马自达店 | jyshmzd |
| 天翔林肯店 | jywhtx |

### 龙星行 5 店

| 门店 | 账号 |
|------|------|
| 长沙 | lxhchangsha1234 |
| 翔鹏 | lxhxiangpeng1234 |
| 骏宜 | lxhjunyi1234 |
| 海珠龙星行 | guangzhouhaizhu1234 |
| 广州龙星行 | lxhguangzhou123 |

---

## 项目结构

```
报告产出脚本/
├── main.py                          # 旧版入口（保留兼容）
├── run_jianyin_stores.py            # 建银 5 店全流程入口
├── run_history_reports.py           # 历史日期回溯工具
├── requirements.txt                 # Python 依赖
├── README.md                        # 本文件
├── 日度月度汇总表数据计算说明.md        # 字段计算逻辑
├── prd/                             # 开发过程的需求文档
├── tools/
│   ├── recorder.py                  # 数据爬取（纯 API，v3.0 重写）
│   ├── process_clue_report.py       # 数据处理与报表生成
│   ├── daily_summary.py             # 日度月度汇总表生成
│   └── jianyin_trend_summary.py     # 趋势分析工具
├── data/
│   ├── {YYMMDD}/                    # 每日产出目录
│   │   ├── 原始数据/
│   │   ├── 中间文件/
│   │   ├── 每日报告/
│   │   ├── 汇总表/
│   │   └── 错误日志/
│   ├── 3 月/                        # 3 月历史数据
│   ├── 4 月/                        # 4 月历史数据
│   └── 5 月/                        # 5 月历史数据
├── _tracking/                       # 月度跟踪数据（JSON，自动生成，.gitignore）
└── venv/                            # 虚拟环境
```

---

## 模块说明

### tools/recorder.py — 数据爬取（v3.0 重写）

```python
from tools.recorder import crawl

# 使用默认账号列表
result = crawl("/path/to/output")

# 返回：{店名: {"clue": Path, "call": Path}}
```

**核心流程**：
1. 遍历账号列表
2. 判断文件是否已存在 → 存在则跳过（断点续爬）
3. 登录 → `POST /bc/v1/users/login` → 获取 accessToken
4. 导出线索明细 → `POST /openapi-server/v2/call-clues/export-adviser-clue` → 直接保存 Excel
5. 导出通话列表 → `POST /esl/v2/task/export-task-list` → 取 TOS 链接 → 二次下载 Excel
6. 失败则重试（最多 2 次），错误日志写入 `错误日志/` 目录

> v3.0 之前使用 Playwright 浏览器自动化，需要安装 Chromium 并模拟点击操作。v3.0 改为纯 HTTP API 调用，消除了浏览器依赖。

### tools/process_clue_report.py — 数据处理

```bash
python tools/process_clue_report.py \
  --call_file 话单文件.xlsx \
  --xiansuo_file 线索明细文件.xlsx \
  --company 长沙 \
  --date 260510 \
  --output_dir ./输出目录
```

**处理流程**：
1. 按 `--date` 筛选话单（结束时间）和线索（下发时间）
2. 话单去重（同一线索 ID 保留最新通话）
3. 脱敏号码检查
4. 手机号格式校验（11 位检测）
5. 线索与话单基于线索 ID 左连接匹配
6. 按 `--group_by_call_field` 分组统计（可选）
7. 输出日报文本 + 匹配结果表
8. 调用 `daily_summary` 生成汇总 Excel + 更新 tracking

### tools/daily_summary.py — 日度月度汇总

- **MTD**：线索指标来自全月线索表筛选截止 `--date`，呼叫通次来自话单表筛选截止 `--date`
- **Daily**：来自当日日报
- **昨日对比**：从 `_tracking/` 取前一天的记录重算比率
- 输出：`{公司}_日度月度汇总表_{YYMMDD}.xlsx`

---

## 关键设计决策

| 决策点 | 说明 |
|--------|------|
| 爬取 vs 报表日期分离 | 爬取日期=当天（导出全月数据），报表日期=目标日期（筛选当天） |
| 话单去重 | 同一线索多次通话只保留最新一条，避免重复计算 |
| 断点续爬 | 文件已存在即跳过，支持中断后继续 |
| 重试机制 | 每个账号 2 次重试，失败写日志不中断整体流程 |
| tracking 文件 | 追加写入，记录每日指标，用于昨日对比 |
| MTD 呼叫通次 | 直接从话单表计算，不依赖 tracking 累加（避免误差累积） |
| API 迁移 | v3.0 将爬取模块从 Playwright 浏览器自动化改为纯 HTTP API 调用 |

---

## 常见问题

### Q: 爬取失败怎么办？

检查错误日志（`data/{date}/错误日志/`），常见原因：
- 账号密码错误 → 检查 `ACCOUNTS` 或 `NEW_ACCOUNTS` 配置
- 网络超时 → 重试机制会自动处理，2 次均失败则记录日志
- 接口变更 → 联系后端确认导出接口路径是否变化

### Q: 如何回溯历史日期？

原始文件已存在的情况下：
```bash
python tools/process_clue_report.py \
  --call_file data/260601/原始数据/长沙-aicc-话单-260601.xlsx \
  --xiansuo_file data/260601/原始数据/长沙-outcall-线索明细-260601.xlsx \
  --company 长沙 \
  --date 260601 \
  --output_dir data/260601/
```

### Q: 数据放在哪个目录？

按日期命名，例如今天的报告放在 `data/260615/`，昨天的放在 `data/260614/`。目录名格式为 `YYMMDD`。

### Q: 如何新增门店？

在 `tools/recorder.py` 的 `ACCOUNTS` 列表或 `run_jianyin_stores.py` 的 `NEW_ACCOUNTS` 列表中追加账号配置：
```python
{"name": "门店名", "username": "账号", "password": "密码", "mtd_start_date": "250613"}
```

`mtd_start_date` 为可选的 MTD 统计下界，格式为 `YYMMDD`。配置后，MTD 仅统计线索下发时间和话单结束时间不早于该日期的数据；例如 `250613` 表示 2025-06-13。也可以在 AICC 运营工作台的配置中心填写该字段。

如需分组统计，同时配置 `group_by_call_field`、`required_group_values`、`group_display_names` 等参数。

---

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v3.0 | 2026-06-15 | **重大变更**：recorder.py 从 Playwright 浏览器自动化迁移为纯 HTTP API 调用；新增 5 个建银门店账号（共 10 店）；移除 playwright 依赖 |
| v2.3 | 2026-05-18 | 新增广州龙星行租户；支持按话单字段（机器人）拆分统计；支持剔除指定线索ID |
| v2.2 | 2026-05-18 | MTD 呼叫通次改为从话单源表筛选截止 `--date`，不再依赖 tracking 逐日累加 |
| v2.1 | 2026-05-18 | MTD 线索计算改为按 `--date` 截止日期筛选，支持回溯历史日期时 MTD 不包含未来线索 |
| v2.0 | 2026-05-10 | 爬虫设置月初时间窗口；MTD 改为从全月线索表直取；tracking 精简为呼叫通次+昨日数据；子文件夹归类；调整 data/ 目录；新增计算说明文档 |
| v1.0 | 2026-05-06 | 初始版本：录制爬虫 + 数据处理 + 月度表 |
