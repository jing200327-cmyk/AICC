---
name: task-state-checkpoint
description: Capture a concise, evidence-backed TASK_STATE.md before context compression, handoff, thread switching, or pausing a multi-file task. Use after an important verified phase or when current implementation state could be lost. Do not use to define durable repository rules; use repository-context-bootstrap for AGENTS.md.
---

# Task State Checkpoint

Record the live state of one unfinished task so another Codex session can resume without relying on conversation memory. TASK_STATE.md is dynamic and disposable; it is not project policy.

## Collect Live Evidence

From the repository root, collect only read-only evidence:

- current date and time
- repository root, branch, and HEAD commit
- git status --short
- staged, unstaged, and untracked file classification
- git diff --stat and git diff --name-status
- git diff --cached --stat
- small, relevant local diffs only when needed to explain behavior
- commands actually run during this task, their results, and current reproducible errors

Never collect or write environment-variable values, credentials, tokens, private payloads, complete logs, or complete diffs. Do not run commands that stage, commit, reset, clean, or otherwise modify the worktree while collecting a snapshot.

## Write TASK_STATE.md

Create or atomically update root TASK_STATE.md. Replace it through a temporary file and rename so a partial snapshot is never left behind. Use this structure:

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

Keep every section concise and evidence-based:

- Completed contains only work actually performed and verified.
- Changed files lists each relevant path, reason, important symbol/configuration, and completed, partial, or needs-review status.
- Validation includes only executed commands, actual results, and failures.
- Remaining work follows dependency order; Next action contains exactly the highest-priority actionable step.
- Resume instructions name the first files to read and checks to run.
- Diff summary distinguishes staged, unstaged, and untracked files; state each file's net intent and review risk without pasting full diffs.

When updating an existing checkpoint, retain still-valid decisions, remove stale temporary state, move verified work from Remaining to Completed, and reconcile every file entry with current Git state. Do not trust a previous snapshot's completion claim without current evidence.

## Boundary

Do not create or rewrite AGENTS.md here. Use repository-context-bootstrap for long-lived rules. Use task-state-resume to consume this snapshot safely.
