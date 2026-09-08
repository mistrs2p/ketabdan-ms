# 11 — Git Workflow & Repository Governance

**Project:** Ketabdaneh
**Document status:** Living document — update as the team's process matures.
**Last reviewed:** 2026-09-08
**Depends on:** [00-PROJECT-CONTEXT.md](00-PROJECT-CONTEXT.md)
**Companion rules:** [AGENTS.md](../AGENTS.md)

---

## 1. Branch Lifecycle

Every unit of work follows the same life cycle:

```
main
  ↓  (branch from latest main)
feature branch
  ↓
implement
  ↓
test / validate
  ↓
review diff (git status + git diff)
  ↓
commit (atomic, Conventional Commits)
  ↓
merge (back into main)
  ↓
delete branch
```

1. **Branch** — a dedicated branch is created from main for the task.
2. **Implement** — all work happens on the branch; main is untouched.
3. **Test/validate** — whatever validation the task allows (tests, build, review)
   runs before committing.
4. **Review diff** — the author inspects `git status` and `git diff` and confirms
   the changes are exactly the intended ones, nothing unrelated.
5. **Commit** — changes are committed in focused, atomic commits.
6. **Merge** — the finished branch is integrated back into main.
7. **Delete** — the branch is removed after merge (safe delete, not force).

## 2. Branch Naming

Format: `<type>/<short-kebab-case-description>`

| Prefix | Purpose | Example |
|---|---|---|
| `feat/` | New functionality | `feat/event-calendar` |
| `fix/` | Bug fixes | `fix/task-completion-state` |
| `refactor/` | Restructuring without behavior change | `refactor/split-api-routers` |
| `chore/` | Tooling, deps, config, cleanup | `chore/setup-pre-commit` |
| `docs/` | Documentation only | `docs/11-git-workflow` |
| `test/` | Test-related work | `test/event-model-tests` |
| `ci/` | CI/CD pipeline | `ci/github-actions` |

Rules:

- Lowercase, hyphen-separated, short but descriptive.
- One branch per task; don't reuse old branches for new tasks.

## 3. Commit Conventions (Conventional Commits)

Format: `type: imperative summary`

- Lowercase type, colon, space, one-line imperative summary, no trailing period.
- Allowed types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`.

Examples:

```
feat: add event creation form
fix: correct task assignee validation
docs: add git workflow document
refactor: extract assignment logic into service
test: cover event completion transitions
chore: configure linting rules
build: add docker setup for local dev
ci: add pipeline for backend tests
```

A longer body is allowed when the *why* of a change isn't obvious from the
subject; keep it the exception, not the rule.

## 4. Atomic Commits

- **One commit = one logical change.** A commit should be describable in a
  single subject line that is completely true.
- Never mix unrelated changes in one commit — e.g., a bug fix plus an unrelated
  refactor, or a feature plus stray formatting of other files.
- A single task may legitimately produce several commits
  (e.g., `docs: ...` then `chore: ...`), each focused.
- Before every commit: run `git status` and `git diff` and confirm the staged
  content is exactly the intended change.

## 5. Pre-Commit Validation

Before committing, the author must:

1. Run the validation the task makes possible (tests, build, linters) — for
   documentation-only tasks, validation is a careful re-read of the files.
2. Review `git status` — no unexpected files, no leftovers from other work.
3. Review `git diff` — the change is what was asked, complete, and nothing more.
4. Confirm no secrets or environment-specific values are being committed.

> **TBD (human decision):** whether to add automated checks (pre-commit hooks,
> CI) once application code exists. Not applicable yet — repo is
> documentation-only at this point.

## 6. Pull / Merge / Rebase Policy (high level)

| Situation | Policy |
|---|---|
| Starting a task | Branch from latest main |
| Main has moved while working | Bring the branch up to date with main via merge (default) **or** rebase — see TBD below |
| Integrating finished work | Merge the branch into main |
| Local commits not yet pushed | Rebase locally is safe and allowed |
| Pushed/shared commits | Do not rebase; do not rewrite history |

- The default integration method is a **merge into main**. Direct pushes of
  feature work to main are not the workflow (see §7).
- Rebase is allowed only on commits that exist nowhere but locally.
- **TBD (human decision):** merge vs. rebase as the preferred update strategy;
  fast-forward-only or merge commits on main; PR-based review vs. direct merge
  (depends on team size and whether a remote/review process is set up — see §12).

## 7. Main Branch Policy

- **main is the integration branch and the source of truth.**
- No one — human or agent — commits directly on main as part of normal work.
  Everything arrives via a branch merge (§1).
- Main should always be in a coherent state: after any merge, the project should
  validate (build/tests/docs consistent).
- No force-push to main, ever. No history rewrite on main, ever.
- Tagging releases on main is expected once there is something to release.
  **TBD (human decision):** tagging/versioning scheme.

## 8. Feature Branch Lifecycle (detailed)

1. `git switch main` → ensure main is current (`git pull` if a remote exists).
2. `git switch -c feat/<description>` — the task now has its dedicated branch.
3. Implement the task; validate; review `git status` / `git diff`.
4. Commit atomically with Conventional Commits messages.
5. `git switch main` → `git merge --no-ff feat/<description>`
   (merge-commit integration; see §6 TBD for alternatives).
6. Validate main still holds together after the merge.
7. `git branch -d feat/<description>` — safe delete (only works if merged).
8. Report: branch, changed files, status, validation performed (per AGENTS.md §5).

## 9. Handling Failed Work

- A task that turns out wrong or abandoned is **not merged**; the branch is
  simply left unmerged.
- Deleting an unmerged branch requires `git branch -D` — a destructive command:
  **only with explicit authorization.** Default: keep the branch and report.
- Never "fix" a failed direction by force-pushing or rewriting history.
- If a commit on the branch itself is bad (typo, wrong content) and **not yet
  shared**, amend or rebase locally — that is allowed (§6).
- Partial value in a failed task → extract the good part as a new, smaller task
  on a new branch; don't merge the failed whole.

## 10. Conflict Resolution Principles

- Conflicts are resolved on the **feature branch** (merge main *into* the
  branch), never by overwriting main's work blindly.
- Resolve by understanding both sides: what main now says, what the branch was
  trying to do, and which outcome the *task requirement* implies.
- After resolving: re-run the task's validation before committing the merge.
- Never resolve a conflict by deleting the other side's changes wholesale unless
  the task explicitly says so.
- **TBD (human decision):** a conflict-escalation path (when unsure, ask a
  human — this is always allowed and encouraged).

## 11. The Agent Must / Must Not Do

### Must

- Work on a dedicated, correctly named branch for every task.
- Inspect `git status` and `git diff` before every commit.
- Keep commits atomic, focused, Conventional-Commits-formatted.
- Commit only when the task explicitly requires a commit.
- Report branch, changed files, `git status`, and validation performed.
- Resolve conflicts on the branch, understanding both sides.
- Ask a human when unsure about history-affecting operations.

### Must not

- Work directly on main.
- Force-push (anywhere, by default).
- Rewrite shared branch history.
- Use destructive commands (`reset --hard`, `clean -fd`, `branch -D`,
  `push --delete`, …) without explicit authorization.
- Mix unrelated changes in one commit.
- Commit secrets or environment-specific configuration.
- Commit when the task didn't ask for a commit.

## 12. Example Workflow — a Typical Task

Task: *"Implement the event creation form"* (hypothetical future task).

```bash
# 1. Start from latest main
git switch main
git pull                      # if a remote exists
git status                    # confirm clean

# 2. Create the dedicated branch
git switch -c feat/event-creation-form

# 3. Implement (files created/edited)
#    ...work...

# 4. Test / validate
#    run tests, build, lint — whatever exists at this stage

# 5. Review the diff before committing
git status                    # exactly the intended files?
git diff                      # exactly the intended changes?

# 6. Commit atomically
git add src/components/EventForm.tsx
git commit -m "feat: add event creation form"

# 7. Merge back into main
git switch main
git merge --no-ff feat/event-creation-form

# 8. Validate main, then delete the branch (safe delete)
git branch -d feat/event-creation-form

# 9. Report
#    branch: feat/event-creation-form (merged & deleted)
#    changed files, git status, tests run & results
```

## 13. TBD — Requires Human Decision

| # | Open Policy Question |
|---|---|
| G1 | Merge vs. rebase as preferred branch-update strategy |
| G2 | Merge commits (`--no-ff`) vs. fast-forward on main |
| G3 | PR-based review vs. direct local merge (depends on remote hosting & team) |
| G4 | Remote hosting choice (GitHub/GitLab/self-hosted) and remote setup |
| G5 | Tagging/versioning scheme for main |
| G6 | Automated pre-commit hooks / CI gates (once code exists) |
| G7 | Branch protection rules on the remote (once G4 is decided) |
| G8 | Long-lived vs. short-lived branch policy beyond "one task, one branch" |

---

## 14. Out of Scope for This Document

- CI pipeline definitions.
- Application code, schemas, or API design.
- Telegram/Bale integration concerns.

These belong to later documents/tasks.
