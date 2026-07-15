---
name: repository-context-bootstrap
description: Establish or improve durable, evidence-based AGENTS.md guidance for a repository. Use when initializing Codex in a new project; creating, reviewing, or correcting AGENTS.md; or when Codex repeatedly chooses the wrong directory, commands, or project conventions. Do not use for a task handoff or live task progress; use task-state-checkpoint or task-state-resume instead.
---

# Repository Context Bootstrap

Create durable repository guidance from evidence, not assumptions. Keep AGENTS.md useful for every future task; keep dynamic task facts in TASK_STATE.md.

## Discover Before Reading

1. Run git rev-parse --show-toplevel and record the actual repository root and current working directory.
2. List only the root and relevant top-level directories. Locate, without recursively reading source:
   - root and nested AGENTS.md / AGENTS.override.md
   - README files
   - build manifests and lockfiles
   - CI, lint, formatter, test, typecheck, container, development-environment, and deployment configuration
3. Read the located files progressively. Inspect a subdirectory only when its manifests, configuration, or requested work make it relevant.
4. Treat repository files, Git state, successful command output, and explicit user statements as evidence. Label anything else as unknown and omit it from durable rules.

## Extract Durable Rules

Extract only facts expected to remain valid across tasks:

- repository purpose, major modules, and source-of-truth files
- setup, development, build, test, lint, format, and typecheck commands
- established architecture, generated-code boundaries, and implementation conventions
- directories that require extra approval or must not be edited
- generated or machine-owned files that must not be edited manually
- minimum validation required after a change
- directory-specific routing rules
- durable documentation expectations

Do not infer commands from a filename alone. Prefer scripts, CI workflows, package manifests, Makefiles, and tool configuration. Note command prerequisites when they are evidenced.

## Update AGENTS.md

Create or update the root AGENTS.md with concise, repository-specific sections:

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

Preserve valid user-authored rules. Edit only to remove contradictions, duplication, stale instructions, or claims lacking evidence. Create a nested AGENTS.md or AGENTS.override.md only when a subdirectory has rules that genuinely differ from the root.

Never put current task progress, temporary errors, branch state, a current diff, one-off requests, unverified guesses, secrets, environment-variable values, or credentials in AGENTS.md.

## Report Evidence

After updating, report each important rule with the repository file or successful command that supports it. State when no nested rule file was needed.

## Boundary

This skill owns long-lived project guidance only. Use task-state-checkpoint to record current work and task-state-resume to compare a prior checkpoint with live repository state.
