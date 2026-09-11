# Security Policy

This document describes how the Ketabdaneh project handles security:
what our CI enforces, how to report a vulnerability, and the rules for
secrets and dependencies. The operational side (deployment topology,
firewall, backups) is documented in [docs/12-DEPLOYMENT.md](docs/12-DEPLOYMENT.md);
the CI side in detail in [docs/13-CI.md](docs/13-CI.md).

## Supported Versions

This project is under active development on `main`. Security fixes are
applied to the latest `main` only — there are no maintained release
branches yet. When versioned releases exist, this section will list them.

## Reporting a Vulnerability

Please do **not** open a public GitHub issue for a security problem.

Report vulnerabilities privately through GitHub's private vulnerability
reporting on this repository (Security → Report a vulnerability). If
that is unavailable to you, open a minimal public issue saying "security
issue — please contact maintainers" with no details, and a maintainer
will provide a private channel.

Include what you can: affected component (API, worker, web, deployment
configuration), a description or proof of concept, and impact. We will
acknowledge reports and keep reporters updated on remediation progress.
Coordinated disclosure is appreciated — please give us reasonable time
to fix before publishing.

## Secret Handling Policy

- **No real credentials in the repository.** Not in code, not in
  workflow files, not in Dockerfiles, not in `package.json` /
  `pyproject.toml`, not in scripts, not in documentation examples, not
  in commit history. This is enforced by an automated secret scanner
  ([gitleaks](https://github.com/gitleaks/gitleaks), full git history)
  as a blocking CI check.
- **Templates use only obviously-fake values.** `.env.prod.example`
  and `apps/api/.env.example` carry placeholders; real values live in
  uncommitted `.env` files that are gitignored.
- **If a real secret is ever committed:** rotate it, then report the
  incident. We do not rewrite git history — once a secret is pushed it
  must be considered compromised and rotated, regardless of history
  rewriting.
- **Runtime configuration is fail-closed.** The API refuses to start in
  production with the development placeholder JWT secret, a secret
  shorter than 32 characters, the insecure-dev-secret flag enabled, a
  missing database/Redis URL, or a wildcard CORS origin
  (see `apps/api/app/core/config.py`).

## CI Security Gates

The CI workflow (`.github/workflows/ci.yml`) blocks a merge on any of:

- **Secret scanning** — gitleaks over the full git history.
- **Dependency vulnerabilities** — `pip-audit` on the resolved Python
  dependency closure and `npm audit --omit=dev --audit-level=critical`
  on production frontend dependencies. Known, evaluated exceptions are
  listed in [docs/13-CI.md §6](docs/13-CI.md); nothing is suppressed
  silently.
- **Static security analysis** — bandit on the API and worker
  (medium severity and above).
- **Configuration regression tests** — automated tests assert the
  deployment security posture: only the Caddy proxy publishes host
  ports (80/443), no privileged containers / host namespaces / Docker
  socket mounts, non-root images, read-only root filesystems, dropped
  capabilities (`apps/api/tests/test_compose_security.py`), plus the
  application-level fail-closed configuration and 401/403 contract
  tests.
- **Standard gates** — tests, lint, production build, and Docker image
  builds must all pass.

CI itself runs with `permissions: contents: read`, pins all third-party
actions to immutable commit SHAs, and requires **no secrets of any
kind** — so untrusted fork pull requests run the same pipeline without
access to anything sensitive.

## Production Secret Rules

- `AUTH_SECRET_KEY` must be a real, randomly generated secret of at
  least 32 characters (e.g. `secrets.token_urlsafe(48)`).
- Database and Redis credentials are set in the uncommitted `.env.prod`
  and flow only through Docker environment variables — never build
  arguments.
- Provider bot tokens (Telegram/Bale) are optional at runtime and are
  read from the environment, never stored.
- TLS is terminated by Caddy with automatic certificates; there is no
  mechanism to disable certificate validation in the application.
- Backups produced by `scripts/backup_db.sh` contain database contents
  and must be stored with the same care as the database itself.

## Dependency Update Expectations

- Dependencies are updated deliberately, in dedicated commits, with the
  test suite and audits run before merge — never as a side effect of
  "making CI green".
- Minor/patch updates that keep the full suite and audits passing are
  low-risk and encouraged. Major-version upgrades are evaluated
  individually (see the Next.js note in docs/13 §6).
- New runtime dependencies should justify their inclusion; CI-only
  tooling must stay out of the production Docker images.

## Prohibited Practices

- Committing real credentials or tokens of any kind.
- Disabling or skipping a failing security check to unblock a merge
  (fix the finding or document a specific, justified exception).
- Rewriting git history or force-pushing to shared branches.
- Running containers as root when a non-root image is available;
  mounting the Docker socket into application containers; publishing
  database/Redis ports in the production stack.
- Wildcard CORS origins in production; disabling authentication or
  authorization checks "temporarily".
- Bypassing TLS verification (`--insecure`-style flags) anywhere
  outside the explicitly documented local deployment simulation.

## Branch Protection Expectations

`main` is expected to be protected on the hosting platform with
(operators configure this in the repository settings — it is not
automated by this repository):

- pull requests required to merge (no direct pushes to `main`)
- the CI checks above required to pass before merge
- force pushes and history deletion disallowed
- branches deleted after merge (default)

Work happens on short-lived feature branches merged with `--no-ff`
merge commits, so each change is traceable to its branch history.
