---
name: task-state-resume
description: Safely continue an interrupted or context-compressed coding task by comparing TASK_STATE.md with live Git state and current code. Use when the user asks to continue prior work, a new session finds TASK_STATE.md, or task context was compressed. Do not use to create durable AGENTS.md rules or to write a checkpoint before pausing.
---

# Task State Resume

Resume from evidence, never from an old summary alone. Current Git state, current code, and newly executed tests override TASK_STATE.md.

## Reconcile State

1. Locate and read every applicable root or nested AGENTS.md / AGENTS.override.md.
2. Read root TASK_STATE.md.
3. Collect current read-only evidence:
   - branch and HEAD
   - git status --short
   - git diff --stat
   - git diff --name-status
   - staged diff status, including git diff --cached --stat
4. Compare the live branch, HEAD, and changed-file sets with the checkpoint.

Treat the checkpoint as potentially stale when branch or HEAD differs. When a diff disagrees with the snapshot, use current Git state. When a file listed in the snapshot has changed, read its current relevant section before relying on the old description.

## Read Progressively

Read first:

- files named in Resume instructions, Next action, and Changed files
- currently changed files relevant to the goal
- the tests and configuration directly required by the next action

Do not scan the whole repository unless this focused evidence cannot safely establish the task boundary.

## Report Before Editing

Before modifying code, give a short status statement covering:

- current goal
- confirmed completed work
- differences between checkpoint and live state
- next action

If there is an unexplained branch switch, conflicting changes, or extensive external modification, stop before writing and report the difference. Never overwrite user changes that cannot be explained from current evidence.

## Continue and Checkpoint

Perform only the next action supported by the reconciled state. Verify new work with appropriate commands. After an important phase, before pausing, or before context compression, invoke or follow task-state-checkpoint to refresh TASK_STATE.md.

## Safety Rules

- Prefer current Git state over an old checkpoint.
- Prefer current source over an old summary.
- Prefer actual test output over historical claims.
- Do not assume a snapshot file is unchanged merely because it is listed.
- Do not copy secrets, environment values, full diffs, or long logs into a new checkpoint.
