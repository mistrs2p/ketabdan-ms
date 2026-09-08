# AGENTS.md — Agent Git Rules for Ketabdaneh

These rules govern how any AI agent (or developer acting through one) works with
Git in this repository. They apply to every task, without exception.

**Project context:** [docs/00-PROJECT-CONTEXT.md](docs/00-PROJECT-CONTEXT.md)
**Full workflow document:** [docs/11-GIT-WORKFLOW.md](docs/11-GIT-WORKFLOW.md)

---

## 1. Git Is Required

- Git is a **required** part of the development workflow. All project work is
  tracked in this repository; nothing of substance lives only on a local disk.
- **main is the integration branch and the source of truth.** It must always
  represent a state the project can build on.

## 2. Branch Rules

- **Never work directly on main.** No commits, no experiments, no "small fixes."
- **Every implementation task gets its own dedicated branch**, created from main
  (or from the branch it builds upon, when a task explicitly continues prior
  work).
- Branch naming convention: `<type>/<short-kebab-case-description>`

  | Prefix | Used for |
  |---|---|
  | `feat/` | New functionality |
  | `fix/` | Bug fixes |
  | `refactor/` | Restructuring without behavior change |
  | `chore/` | Tooling, dependencies, config, cleanup |
  | `docs/` | Documentation only |
  | `test/` | Test-related work |
  | `ci/` | CI/CD pipeline work |

  Examples: `feat/event-calendar`, `fix/task-completion-state`,
  `docs/02-domain-model`.

## 3. Commit Rules

- Commit messages follow **Conventional Commits**: `type: imperative summary`
  (lowercase, no trailing period). Types: `feat`, `fix`, `docs`, `refactor`,
  `test`, `chore`, `build`, `ci`.
  Examples: `feat: add event creation form`, `fix: correct task assignee
  validation`, `docs: add domain model document`.
- **Commits must be focused and atomic** — one logical change per commit.
- **Never mix unrelated changes in one commit.** If the working tree contains
  unrelated changes, split them into separate commits (or leave unrelated files
  untouched and report them).
- **Inspect before committing:** run `git status` and `git diff` (and
  `git diff --staged` for staged work) and actually review the output before
  every commit.
- **Do not commit unless the task explicitly requires a commit.** Creating
  files or editing them is not, by itself, a request to commit.

## 4. Safety Rules (hard prohibitions)

- **No force-push.** Not to main, not to shared branches, not anywhere by
  default; explicit human authorization is required for any exception.
- **No rewriting shared branch history.** No history rewrites, no rebase
  of branches others may have based work on, by default.
- **No destructive Git commands** (`reset --hard`, `clean -fd`, branch `-D`,
  `push --delete`, filter-branch, etc.) **unless explicitly authorized** by the
  user for that specific action.
- If a safe, non-destructive alternative exists, use it.

## 5. Reporting Requirements

At the end of any task that touches the repository, report:

1. **Current branch** (the branch name you worked on).
2. **Changed files** (created/modified/deleted, with paths).
3. **`git status` output** (verbatim or faithfully summarized).
4. **Tests/validation performed** — what was run, what passed; if nothing was
   run (e.g., documentation-only task), say so explicitly.

## 6. Definition of Done (Git-related work)

A task is done, Git-wise, only when **all** of the following hold:

- [ ] Work happened on a dedicated branch (never directly on main).
- [ ] Branch name follows the naming convention.
- [ ] Commits are atomic, focused, and follow Conventional Commits — or the task
      explicitly required no commit and none was made.
- [ ] `git status` / `git diff` were reviewed before each commit.
- [ ] No force-push, no history rewrite, no destructive commands were used
      (without explicit authorization).
- [ ] The end-of-task report (§5) is complete and truthful.
- [ ] The result of the task is reflected in the repository state exactly as
      described in the report.
