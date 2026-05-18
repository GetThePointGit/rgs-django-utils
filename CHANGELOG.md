# Changelog

All notable changes to rgs-django-utils will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-05-18

### Added
- Hasura GraphQL permissions generator
  (`commands/hasura_permissions.py`, `database/permission_helper.py`)
  derives select/insert/update/delete permissions from Django model and
  field metadata.
- View-backed model classes under `rgs_django_utils/models/views/`:
  `HasuraTrackedView` (abstract) and `UserView` for exposing SQL views
  through Django + Hasura.
- Extra DB function/trigger installers in
  `database/install_db_functions_and_triggers.py`.
- Schema export now emits the JSON Schema keywords `unit`, `precision`,
  `docFull` and `modules` (read from `Config` / `TableDescription`),
  aligning with the `rgs-schema` custom-keyword conventions.
- `setup_django` honors the `PATH_TO_THISSITE_ENV` env var to locate
  the host project's settings file (e.g. `waterworks`).
- VSCode `launch.json` / `settings.json` for debugging the test app.
- `xlsxwriter`, `sqlalchemy` and `geoalchemy2` added as dependencies
  in `pixi.toml`.

### Changed
- Code-quality gate aligned across pre-commit, pixi and GitHub Actions:
  `tox -e ruff` was replaced by `tox -e quality`, which delegates to
  `pre-commit run --all-files`. The pixi task `quality` and the CI
  job now run the exact same checks as the local git hook (full ruff
  lint with the project's selected rules + ruff format + file-hygiene
  hooks), instead of CI only validating import order and format.
- `forms.api.GlobalError` is now defined locally as a Pydantic model
  instead of imported from `core.rgs_django_workflow`, removing a
  hidden dependency on the host project.
- Hasura presets are only emitted when at least one other column is
  writable for that role.
- Hasura `claims` no longer receive insert/update permissions.
- `setup_django.py` reworked: settings import path and host-project
  lookup via env file.
- `pixi.toml` switched to the newer `[workspace]` table; dev/prod
  split documented in the README.

### Fixed
- `profile_measurements` handling.
- Several Hasura preset generation issues.
- Various `ruff` format/lint findings.

## [0.1.0] - Initial

- Initial extracted version used by `waterworks` and `urbanworks` backends.
- Tooling baseline inherited from the `django-fsspec` gold-standard:
  pre-commit hooks (`ruff`, whitespace, yaml/toml), tox matrix covering
  Python 3.12/3.13 × Django 5.0/5.1/main, GitHub Actions CI with unit
  + quality jobs, dynamic version sourced from
  `rgs_django_utils.__version__`, and this `CHANGELOG.md`.
