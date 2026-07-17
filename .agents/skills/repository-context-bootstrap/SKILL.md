---
name: repository-context-bootstrap
description: 为仓库建立或改进长期稳定且有证据支撑的 AGENTS.md 规则。初始化新项目的 Codex 上下文，创建、审查或纠正 AGENTS.md，或者 Codex 反复选择错误目录、运行错误命令、违反项目约定时使用。不要用于任务交接或记录当前任务进度；这些情况应使用 task-state-checkpoint 或 task-state-resume。
---

# 仓库上下文初始化

依据真实证据创建长期仓库规则，不依赖猜测。`AGENTS.md` 应对未来每个任务都有用；当前任务的动态事实应写入 `TASK_STATE.md`。

## 使用方式

- 隐式触发：新项目首次配置 Codex、需要创建或审查 `AGENTS.md`，或者 Codex 经常读取错误目录、使用错误命令、重复违反项目规则。
- 显式调用示例：`使用 $repository-context-bootstrap 审查当前仓库并依据真实配置创建 AGENTS.md。`
- 改进规则示例：`使用 $repository-context-bootstrap 检查现有 AGENTS.md，删除过时规则并补充真实测试命令。`
- 预期结果：创建或更新长期有效的根目录规则；只有子目录确实存在不同约束时才创建嵌套规则，并说明每条重要规则的仓库依据。

## 先定位再读取

1. 运行 `git rev-parse --show-toplevel`，记录真实 Git 根目录和当前工作目录。
2. 只列出根目录和相关一级目录，定位以下文件，但不要递归读取全部源码：
   - 根目录和嵌套的 `AGENTS.md`、`AGENTS.override.md`
   - `README` 文件
   - 构建清单和锁文件
   - CI、lint、格式化、测试、类型检查、容器、开发环境和部署配置
3. 渐进式读取已定位的文件。只有子目录的构建清单、配置或当前请求使其相关时，才继续检查该目录。
4. 只把仓库文件、Git 状态、成功命令输出和用户明确陈述视为证据。其它内容标记为未知，不写入长期规则。

## 提取长期规则

只提取预计能跨任务长期成立的事实：

- 仓库用途、主要模块和事实来源文件
- 安装、开发、构建、测试、lint、格式化和类型检查命令
- 已建立的架构、生成代码边界和实现约定
- 需要额外审批或禁止修改的目录
- 不得手工编辑的生成文件或工具维护文件
- 每次变更后的最低验证要求
- 特定目录的规则路由
- 长期文档要求

不得仅凭文件名推测命令。优先以脚本、CI 工作流、包清单、`Makefile` 和工具配置为依据。只有存在证据时才记录命令前置条件。

## 更新 AGENTS.md

创建或更新根目录 `AGENTS.md`，使用简洁且针对当前仓库的章节：

1. Repository overview
2. Source-of-truth files
3. Project structure
4. Setup and development commands
5. Build, test, lint, and typecheck
6. Architecture and implementation conventions
7. Change boundaries
8. Generated files
9. Validation requirements
10. Directory-specific routing
11. Documentation expectations

保留用户手写且仍然有效的规则。只有为了解决矛盾、重复、过时指令或缺少证据的声明时才修改现有内容。仅当子目录规则确实不同于根目录时，才创建嵌套 `AGENTS.md` 或 `AGENTS.override.md`。

不得把当前任务进度、临时错误、当前分支状态、当前 diff、一次性请求、未经验证的猜测、秘密、环境变量值或凭据写入 `AGENTS.md`。

## 报告证据

更新完成后，说明每条重要规则所依据的仓库文件或成功执行的命令。如果无需创建嵌套规则文件，也应明确说明。

## 职责边界

该 Skill 只负责长期有效的项目规则。当前工作状态应使用 `task-state-checkpoint` 记录；根据旧快照和实时仓库状态恢复任务应使用 `task-state-resume`。
