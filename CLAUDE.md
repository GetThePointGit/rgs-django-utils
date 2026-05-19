# rgs-django-utils — Claude notes

This file is loaded when Claude works inside this repository. It captures
conventions that aren't obvious from the code alone. Downstream consumer
projects (`waterworks`, `urbanworks`, …) get their own `CLAUDE.md`.

## Workflow

- **Branch first.** Never edit on `main`. Use `git switch -c <name>`
  (or the `using-git-worktrees` skill) before making changes.
- **Don't push autonomously.** Local commits only; `git push`,
  `gh pr create`, and tag pushes need explicit user confirmation.
- **Quality gate = `pixi run quality`.** Runs `pre-commit run
  --all-files`, which is the exact set of checks CI runs via
  `tox -e quality`. Don't invoke raw `ruff` for "is this clean?" —
  use the task so pixi / pre-commit / CI stay aligned.
- **Tests need PostGIS on port 5431.** `pixi run tests` will fail
  loudly if no database is reachable.

## Codebase patterns

- **`Config(...)` per field is the public API.** The
  `dj_extended_models` module wraps `django.contrib.gis.db.models` so
  every field can carry Hasura permissions, presets, documentation and
  form metadata in one place. New models should use this, not the raw
  Django field classes.
- **`setup_django()` is only for *script-mode* command files.** Modules
  in `rgs_django_utils/commands/` and `rgs_django_utils/management/commands/`
  are sometimes run as `python -m` — they call `setup_django()` inside
  `if __name__ == "__main__":` and have an E402 exemption in
  `pyproject.toml`. Regular library modules (under `database/`,
  `models/`, `utils/`, …) must keep imports at the top.
- **Numpy-style docstrings.** Ruff lint enforces `pydocstyle` (`D`)
  with the numpy convention. Class-level docstrings on tiny helpers
  can be skipped (`D1` is ignored), but public callables get a short
  summary plus `Parameters` / `Returns`.
- **Tests don't get adapted to make them pass.** If a test fails,
  investigate the root cause first, propose a fix, then change either
  the test or the code — never silently flip the expected value.

## Release flow

1. Bump `__version__` in `rgs_django_utils/__init__.py`.
2. Add a section to `CHANGELOG.md` (rename `[Unreleased]` →
   `[x.y.z] - YYYY-MM-DD` on release).
3. Commit on a feature branch, open a PR, get CI green.
4. After merge to `main`, tag with `git tag vX.Y.Z` (only push the
   tag on explicit instruction).
5. `pixi run publish-test` → smoke-test from Test PyPI →
   `pixi run publish`.

## Useful entry points for investigation

- Datamodel + Hasura metadata —
  `rgs_django_utils/database/dj_extended_models.py`,
  `rgs_django_utils/database/permission_helper.py`,
  `rgs_django_utils/commands/hasura_permissions.py`
- Migration + DB sync chain —
  `rgs_django_utils/management/commands/migrate_and_update.py`
- JWT auth — `rgs_django_utils/utils/authorization.py`
- Runtime logging to Postgres —
  `rgs_django_utils/logging/logging/`
- Bulk upserts —
  `rgs_django_utils/database/upsert_multiple_data.py`

See the **Module map** section in `README.md` for the full path index.
