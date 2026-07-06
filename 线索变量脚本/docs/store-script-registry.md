# Store Script Registry

## Scope

The current lead variable scripts live in:

`E:\ai\workflow\线索变量脚本\线索变量脚本`

Most legacy scripts are top-level scripts with hard-coded Excel input paths and txt output paths. They are not safe to import directly from an API request because importing executes the whole file. Several scripts also contain mojibake text from an earlier encoding conversion, so the backend wrapper treats the legacy files as business-rule references and calls a maintained registry-driven processor instead of accepting arbitrary script paths from clients.

## Common Output Contract

Each registered store emits one JSON object per line with these fields:

- `carNo`
- `carType`
- `last_maintain_mileage`
- `last_maintain_time`
- `advised_maintain_time`
- `duration`
- `powerType`
- `assigned_store`

Dates are normalized to `YYYY-MM-DD` where possible. `advised_maintain_time` is six months after `last_maintain_time`, matching the existing scripts.

## Registered Stores

### 合肥海康达店

- 门店编码 `store_code`: `hefei_haikangda`
- 城市: 合肥
- 品牌/特征: 海康达
- 脚本路径: `线索变量脚本/合肥海康达.py`
- 输入文件要求: Excel workbook; columns should include vehicle plate, model, date, and optional mileage fields.
- 识别规则: filename/content keyword `合肥海康达`, `海康达`.
- 调用方式: registry wrapper. Legacy script is top-level and has hard-coded path `C:\Users\Grace\Desktop\日期.xlsx`.
- 输出 txt 路径: unified output directory `outputs/lead-import/hefei_haikangda/{yyyyMMdd}/{job_id}.txt`.
- 已知风险: legacy file contains mojibake and hard-coded local path.

### 合肥建银马自达店

- 门店编码 `store_code`: `hefei_mazda`
- 城市: 合肥
- 品牌/特征: 马自达, 建银
- 脚本路径: `线索变量脚本/合肥马自达.py`
- 输入文件要求: Excel workbook; common columns include vehicle plate, vehicle series, date, and optional mileage.
- 识别规则: filename/content keyword `合肥马自达`, `合肥建银马自达`, `建银马自达`.
- 调用方式: registry wrapper. Legacy script is top-level and has hard-coded macOS path.
- 输出 txt 路径: unified output directory `outputs/lead-import/hefei_mazda/{yyyyMMdd}/{job_id}.txt`.
- 已知风险: legacy file contains mojibake and hard-coded local path.

### 天翔林肯店

- 门店编码 `store_code`: `tianxiang_lincoln`
- 城市: 未在脚本中明确记录
- 品牌/特征: 林肯, 天翔
- 脚本路径: `线索变量脚本/天翔林肯.py`
- 输入文件要求: Excel workbook; common columns include vehicle plate, model, date, and optional mileage.
- 识别规则: filename/content keyword `天翔林肯`, `天翔`.
- 调用方式: registry wrapper. Legacy script is top-level and has hard-coded macOS path.
- 输出 txt 路径: unified output directory `outputs/lead-import/tianxiang_lincoln/{yyyyMMdd}/{job_id}.txt`.
- 已知风险: legacy file contains mojibake and hard-coded local path.

### 林肯美诚店

- 门店编码 `store_code`: `lincoln_meicheng`
- 城市: 未在脚本中明确记录
- 品牌/特征: 林肯, 美诚
- 脚本路径: `线索变量脚本/林肯美诚.py`
- 输入文件要求: Excel workbook; default legacy sheet is `Sheet1`.
- 识别规则: filename/sheet/content keyword `林肯美诚`, `美诚林肯`, `美诚`.
- 调用方式: registry wrapper; legacy script compiles but is top-level and hard-coded to `建银线索\林肯美诚\260701线索名单.xlsx`.
- 输出 txt 路径: unified output directory `outputs/lead-import/lincoln_meicheng/{yyyyMMdd}/{job_id}.txt`.
- 已知风险: importing the legacy script executes file IO immediately.

### 武汉银马店

- 门店编码 `store_code`: `wuhan_yinma`
- 城市: 武汉
- 品牌/特征: 银马, 马自达
- 脚本路径: `线索变量脚本/武汉银马.py`
- 增量脚本路径: `线索变量脚本/武汉银马7.2_按顺序导入.py`
- 输入文件要求: Excel workbook. Multiple sheets are supported; if a workbook has multiple sheets, the wrapper processes a selected sheet or the first data sheet.
- 识别规则: filename/sheet/content keyword `武汉银马`, `银马`.
- 调用方式: registry wrapper. `武汉银马7.2_按顺序导入.py` supports `--sheet`, but it still has a fixed `EXCEL_PATH`, so API uploads use the registry wrapper instead.
- 输出 txt 路径: unified output directory `outputs/lead-import/wuhan_yinma/{yyyyMMdd}/{job_id}.txt`.
- 已知风险: original script writes to a fixed txt path; wrapper avoids overwrite by writing to job-scoped output.

### 襄阳林肯店

- 门店编码 `store_code`: `xiangyang_lincoln`
- 城市: 襄阳
- 品牌/特征: 林肯
- 脚本路径: `线索变量脚本/襄阳林肯.py`
- 输入文件要求: Excel workbook; common columns include vehicle plate, model, date, and optional mileage.
- 识别规则: filename/content keyword `襄阳林肯`, `襄阳`.
- 调用方式: registry wrapper. Legacy script is top-level and has hard-coded macOS path.
- 输出 txt 路径: unified output directory `outputs/lead-import/xiangyang_lincoln/{yyyyMMdd}/{job_id}.txt`.
- 已知风险: legacy file contains mojibake and hard-coded local path.

### 骏马众诚店

- 门店编码 `store_code`: `junma_zhongcheng`
- 城市: 武汉, inferred from test fixture `武汉骏马-模板.xlsx`
- 品牌/特征: 骏马众诚, 骏马众城
- 脚本路径: `线索变量脚本/骏马众诚.py`
- 上月保养脚本路径: `线索变量脚本/骏马众城-上月保养.py`
- 输入文件要求: Excel workbook; common columns include vehicle plate, vehicle series, date, and optional mileage.
- 识别规则: filename/content keyword `骏马众诚`, `骏马众城`, `武汉骏马`, `骏马`.
- 调用方式: registry wrapper. Legacy scripts are top-level and have hard-coded macOS paths.
- 输出 txt 路径: unified output directory `outputs/lead-import/junma_zhongcheng/{yyyyMMdd}/{job_id}.txt`.
- 已知风险: legacy files contain mojibake and hard-coded local paths.

## Security Notes

- API clients may pass `force_store_code`, but it must match this registry.
- API clients cannot pass script paths or output directories.
- Uploaded files are copied into a job-scoped input directory.
- Generated txt files are written under a server-controlled output directory.
