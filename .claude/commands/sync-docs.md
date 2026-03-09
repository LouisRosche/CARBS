# /sync-docs — Documentation Synchronization

Synchronize project documentation with the current codebase state.

## Instructions

Perform the following documentation sync workflow:

### Step 1: Audit Current State
1. Read `git log --oneline -20` to identify recent changes
2. Read `git diff HEAD~10..HEAD --name-only` to list modified files
3. Cross-reference changes against docs in `crypto-arbitrage-system/docs/`

### Step 2: Identify Drift
Check for documentation drift in:
- `docs/ARCHITECTURE.md` — does it reflect current `src/` module structure?
- `docs/DEVELOPER_GUIDE.md` — are commands/APIs still accurate?
- `docs/DEPLOYMENT.md` — does it match `docker-compose.yml` and `Dockerfile`?
- `CLAUDE.md` — are build commands and conventions still current?
- `AGENTS.md` — do rules reflect current codebase patterns?
- `README.md` — does the feature list match implementation?

### Step 3: Update Documentation
For each file with detected drift:
1. Read the current doc file
2. Identify specific outdated sections
3. Update with accurate information from source code
4. Do NOT remove safety warnings or risk disclaimers

### Step 4: Validate Links
- Check that internal links between docs resolve correctly
- Flag broken references to source files that no longer exist

### Step 5: Report
Output a summary:
```
## Documentation Sync Report
- Files reviewed: N
- Files updated: N
- Broken links fixed: N
- Outdated sections updated: [list]
```

## Constraints
- Preserve all risk disclaimers and safety warnings verbatim
- Do not alter LICENSE or CODE_OF_CONDUCT.md
- Keep changes minimal — only update what is factually incorrect
