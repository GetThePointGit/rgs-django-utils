# Changelog

All notable changes to rgs-django-utils will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Tooling upgrade to match `django-fsspec` gold-standard:
  - Pre-commit hooks (`ruff`, whitespace, yaml/toml checks).
  - Tox matrix covering Python 3.12/3.13 × Django 5.0/5.1/main.
  - GitHub Actions CI with unit + quality jobs.
  - Dynamic version sourced from `rgs_django_utils.__version__`.
  - `CHANGELOG.md`.

## [0.1.0] - Initial

- Initial extracted version used by `waterworks` and `urbanworks` backends.
