# /worktree-plan — Parallel Development Planning

Set up Git worktrees for parallel agentic execution.

## Instructions

### Step 1: Assess the Task
1. Read the current task description carefully
2. Identify if it can be decomposed into independent sub-tasks
3. Estimate if parallel execution would save time (tasks >30 min benefit most)

### Step 2: Create Worktrees
For each independent sub-task, create an isolated worktree:

```bash
# From the repository root
git worktree add ../CARBS-<task-name> -b feature/<task-name>
cd ../CARBS-<task-name>/crypto-arbitrage-system
```

Recommended worktree roles:
- `CARBS-implement` — Primary implementation agent
- `CARBS-review` — Skeptical reviewer / adversarial critic
- `CARBS-test` — Test writing and coverage analysis
- `CARBS-docs` — Documentation synchronization

### Step 3: Assign Tasks
For each worktree, define:
- **Objective**: Single, specific deliverable
- **Input files**: Which files to read
- **Output files**: Which files to modify
- **Success criteria**: Specific tests that must pass

### Step 4: Execute Plan
1. Start with implementation worktree
2. Once implementation is staged, activate reviewer worktree with fresh context
3. Reviewer must find at least one issue or confirm PASS explicitly
4. Merge only after reviewer PASS verdict

### Step 5: Cleanup
```bash
# After successful merge
git worktree prune
git branch -d feature/<task-name>
```

## CARBS Worktree Rules
- Each worktree operates on `crypto-arbitrage-system/` independently
- Shared config files (`config/config.yaml`) are read-only in worktrees
- Never enable `mode: live` in worktree branches
- Always rebase against main before opening PR: `git rebase origin/Main`

## Adversarial Review Protocol
The reviewer agent must check for:
1. Race conditions in async code
2. Unhandled exceptions from exchange API calls
3. Missing circuit breaker integration
4. Credential exposure risks
5. Performance regressions (benchmark if applicable)

Score: PASS (≥90%), WARN (75-89%), FAIL (<75% — requires rework)
