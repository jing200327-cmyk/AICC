---
name: task-state-checkpoint
description: 在上下文压缩、任务交接、切换线程或暂停多文件任务前，将当前任务保存为简洁且有证据支撑的 TASK_STATE.md。在一个重要阶段已经验证完成，或当前实现状态可能丢失时使用。不要用它定义长期仓库规则；维护 AGENTS.md 应使用 repository-context-bootstrap。
---

# 任务状态检查点

记录一个尚未完成任务的实时状态，使另一个 Codex 会话无需依赖对话记忆即可继续工作。`TASK_STATE.md` 是动态且可随时重建的状态文件，不是项目规则。

## 使用方式

- 隐式触发：上下文即将压缩、准备暂停或交接任务、一个重要阶段刚完成，或者任务已经修改多个文件。
- 显式调用示例：`使用 $task-state-checkpoint 保存当前任务状态，准备切换线程。`
- 预期结果：在仓库根目录创建或更新 `TASK_STATE.md`，不修改、暂存、提交或清理其它工作树文件。

## 收集实时证据

从仓库根目录仅收集只读证据：

- 当前日期和时间
- 仓库根目录、当前分支和 HEAD 提交
- `git status --short`
- staged、unstaged 和 untracked 文件分类
- `git diff --stat` 和 `git diff --name-status`
- `git diff --cached --stat`
- 仅在解释行为确有必要时读取少量相关局部 diff
- 当前任务中实际运行过的命令、执行结果和目前可复现的错误

不得收集或写入环境变量值、凭据、令牌、私有业务数据、完整日志或完整 diff。收集快照时不得运行任何会暂存、提交、重置、清理或以其它方式修改工作树的命令。

## 写入 TASK_STATE.md

在仓库根目录创建或原子更新 `TASK_STATE.md`。先写入临时文件，再通过重命名替换目标文件，避免留下不完整快照。使用以下固定结构：

~~~
# Task State

## Snapshot identity
- Updated at
- Repository
- Branch
- HEAD
- Working tree status

## Goal

## Success criteria

## Scope

## Completed

## Current implementation

## Changed files

## Decisions

## Validation

## Known issues and blockers

## Remaining work

## Next action

## Resume instructions

## Diff summary
~~~

每个章节都应简洁并有证据支撑：

- `Completed` 只记录已经实际完成并验证的工作。
- `Changed files` 列出每个相关路径、修改原因、重要符号或配置，以及“完成”“部分完成”或“待检查”状态。
- `Validation` 只记录实际执行过的命令、真实结果和失败情况。
- `Remaining work` 按依赖顺序排列；`Next action` 只记录一个优先级最高且可以立即执行的步骤。
- `Resume instructions` 指明恢复时首先读取的文件和需要运行的检查。
- `Diff summary` 区分 staged、unstaged 和 untracked 文件；说明每个文件的净变更意图和审查风险，不得粘贴完整 diff。

更新已有检查点时，保留仍然有效的决定，删除过时的临时状态，将已验证工作从 `Remaining work` 移到 `Completed`，并依据当前 Git 状态核对每个文件条目。不得只凭旧快照声称某项工作已经完成，必须以当前证据重新确认。

## 职责边界

不要在此流程中创建或重写 `AGENTS.md`。长期规则应使用 `repository-context-bootstrap`；安全消费本快照并恢复工作应使用 `task-state-resume`。
