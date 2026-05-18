# rgs-django-utils

A toolkit for the rgs stack of Django + Hasura + Postgres applications
(waterworks, urbanworks, drainworks, ...). Its goal is to remove the
boilerplate that otherwise has to be re-implemented in every app: model
metadata, per-role permissions, Hasura metadata generation, Postgres DDL
sync, JWT claims handling and runtime logging to a central database.

The package is organised around a small number of building blocks:

- **`dj_extended_models`** — drop-in replacement for
  `django.contrib.gis.db.models` that adds a `Config(...)` per field for
  documentation, Hasura permissions, presets, calculations and form-
  builder metadata. Ships the `FPerm`, `TPerm`, `FPresets`, `HasuraSet`
  classes plus section/calculation helpers.
- **`BaseEnum` / `BaseEnumExtended`** — abstract bases for enum tables
  that are compatible with Hasura's enum type and optionally split into a
  separate "extended" table for non-enum columns.
- **`PermissionHelper` + `HasuraPermissions`** — walk every installed
  model and emit the complete `hasura/metadata.json` payload (tables,
  permissions per role, functions, views) from Django model definitions.
- **`install_db_*` helpers** — push Django field defaults, `ON DELETE`
  cascade actions and Postgres functions/triggers into the database so
  mutations going through Hasura or raw SQL behave the same as the ORM.
- **`upsert_multiple_data` / `upsert_from_existing_data`** — set-based
  upserts for bulk imports, with geometry coercion and page-sized
  batching.
- **`Claims`, `JwtUserToken`, `JwtModuleToken`** — Django-Ninja auth
  backends that decode the Hasura-namespaced JWT and expose a read-only
  claims view to views and background workers.
- **`SettingsGetter`, `EmailTemplate`** — layered settings reader
  (module → env → default) and a small class hierarchy for transactional
  emails.
- **Runtime logging** — `TaskContext`, `RunContext`, `PostgresHandler`,
  `LogContextFilter` for writing structured, per-run logs to a
  dedicated `logging` database.

## Installation

The package is not on PyPI yet. Consumer apps wire it in through two
pixi features — editable local checkout for development, pinned git-tag
for CI / production builds:

```toml
# <your-app>/pixi.toml

# Dev: edits in ~/Documents/GitHub/rgs-django-utils/ show up immediately.
[feature.dev.pypi-dependencies]
rgs-django-utils = { path = "../rgs-django-utils", editable = true }

# Prod / CI: reproducible pinned build from GitHub.
[feature.prod.pypi-dependencies]
rgs-django-utils = { git = "https://github.com/GetThePointGit/rgs-django-utils.git", tag = "v0.1.0" }

[environments]
default = { features = ["dev"] }
prod    = { features = ["prod"] }
```

- `pixi install` → default (dev) environment, editable path.
- `pixi install -e prod` → pinned git-tag checkout, what Docker build runs.

For private consumer repos `path =` still points at the sibling
checkout; the git URL in `prod` stays `https://` and pixi picks up your
SSH / credential-helper / URL-rewrite setup from git. See
[`documentation/tooling-alignment-plan.md`](../../documentation/tooling-alignment-plan.md)
for the detailed auth-per-environment matrix.

## Quick start — declare a model with rgs metadata

```python
# myapp/models.py
import uuid

from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.base_models import (
    ModificationMetaMixin,
    ValidityPeriodMixin,
)

loc = models.FieldSection("loc", "Locatie", order=1)


class Waterway(ModificationMetaMixin, ValidityPeriodMixin, models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        config=models.Config(
            section=loc,
            permissions=models.FPerm("-s-"),
            hasura_set=models.HasuraSet(insert="x-hasura-user-id"),
        ),
    )
    code = models.TextStringField(
        "code",
        config=models.Config(
            section=loc,
            doc_short="Unique waterway code",
            permissions=models.FPerm("-s-", project_edit="isu"),
        ),
    )
    geometry = models.LineStringField(
        srid=28992,
        config=models.Config(
            section=loc,
            permissions=models.FPerm("-s-", project_edit="isu"),
        ),
    )

    class Meta:
        db_table = "waterway"

    class TableDescription:
        section = loc
        modules = "*"

    @classmethod
    def get_permissions(cls):
        return models.TPerm(
            public=None,
            project_read={"select": {}},
            project_edit={
                "insert": {},
                "select": {},
                "update": {},
                "delete": {},
            },
        )
```

The `Config(...)` fields drive the Hasura metadata generator, the
datamodel exporters (Excel / JSON-Schema) and the form builder. The
`HasuraSet` preset tells Hasura to stamp the creator on every insert.
`get_permissions()` returns a `TPerm` describing the per-role row
filters at the table level.

## Use case 1 — migrate the database and sync metadata

The `migrate_and_update` management command chains every
post-migration hook in the correct order (see
`rgs_django_utils/management/commands/migrate_and_update.py`):

```bash
python manage.py migrate_and_update
```

Steps performed:

1. `install_db_before_functions` — Postgres scripts that migrations
   rely on (default-value helpers).
2. `manage.py migrate` — Django schema migration.
3. `install_db_authorization_functions` — row-level-security helpers.
4. `install_db_defaults_and_relation_cascading` — pushes Django field
   defaults and FK cascade actions into Postgres DDL so Hasura and raw
   SQL behave consistently.
5. `add_default_records` — seeds enum tables and any model exposing
   `default_records()` or `custom_default_records()`.
6. `install_db_functions` + `install_db_last_functions` — remaining
   Postgres scripts.
7. `sync_db_meta_tables` — mirrors every model's rgs metadata into the
   `description_*` tables.
8. `export_datamodel_to_excel` + `export_datamodel_to_json_schema` —
   refreshes the documentation artefacts in `var/`.

For fine-grained control:

```bash
python manage.py migrate_and_update --skip_migration   # only post-hooks
python manage.py migrate_and_update --skip_before      # skip 01_before
python manage.py sync_db_description                   # just step 7
python manage.py write_models_to_json_schema           # just step 8 (JSON)
python manage.py write_models_to_xlsx                  # just step 8 (XLSX)
```

## Use case 2 — generate Hasura metadata from Django models

`generate_hasura_metadata` walks every installed model plus anything
registered via `HasuraConfig` (functions, views) and writes the
`hasura/metadata.json` payload Hasura's `replace_metadata` endpoint
expects.

```bash
# Write hasura_metadata_exported.json:
python manage.py generate_hasura_metadata

# Write and apply directly to Hasura (needs HASURA_GRAPHQL_URL and
# HASURA_GRAPHQL_ADMIN_SECRET in the environment):
python manage.py generate_hasura_metadata --apply

# Skip generation, apply an existing file (useful in CI):
python manage.py generate_hasura_metadata --apply-only
```

Register per-app SQL functions and views by subclassing `HasuraConfig`:

```python
from rgs_django_utils.commands.hasura_permissions import HasuraConfig


class MyAppHasuraConfig(HasuraConfig):
    pass


MyAppHasuraConfig.register_multiple_functions([
    {"function": "search_waterways", "configuration": {...}, "permissions": [...]},
])

MyAppHasuraConfig.register_multiple_views([
    {"view": "v_active_waterway_codes", "configuration": {...}, "permissions": [...]},
])
```

## Use case 3 — JWT auth with Django Ninja

Hasura signs JWTs with a Hasura-namespaced claim block. `JwtUserToken`
and `JwtModuleToken` plug those directly into Ninja routes:

```python
from ninja import Router

from rgs_django_utils.utils.authorization import JwtModuleToken, JwtUserToken

router = Router()


@router.get("/me", auth=JwtUserToken())
def me(request):
    # request.auth is a Claims instance — authenticated user guaranteed.
    return {
        "id": request.auth.user.id,
        "email": request.auth.email,
        "fullname": request.auth.fullname,
    }


@router.post("/admin/reload-config", auth=JwtModuleToken("admin"))
def reload_config(request):
    # Only requires the "admin" role in the token — no user lookup.
    return {"ok": True}
```

`decode_jwt` returns `None` on any verification failure (bad signature,
expired, malformed), so callers can treat "no token" and "bad token"
uniformly. Requires `settings.JWT_PUBLIC_KEY` to be set to the RSA
public key Hasura signs with.

## Use case 4 — bulk-upsert rows with geometry

```python
from rgs_django_utils.database.db_types import ImportMethod
from rgs_django_utils.database.upsert_multiple_data import upsert_multiple_data

upsert_multiple_data(
    model=Waterway,
    data=[
        {"code": "W-001", "geometry": "LINESTRING(0 0, 1 1)"},
        {"code": "W-002", "geometry": "LINESTRING(1 1, 2 2)"},
    ],
    data_fields=["code", "geometry"],
    update_field_names=["geometry"],
    identification_field_names=["code"],
    method=ImportMethod.OVERWRITE,
    page_size=1000,
)
```

Geometry columns are wrapped in `ST_GeomFromText` (or
`ST_TRANSFORM(..., 4326)` when the target SRID is `4326`). Rows are
uploaded in batches of `page_size` to avoid oversized SQL statements.
Use `upsert_from_existing_data` when the source is already a staging
table in Postgres.

## Runtime logging to Postgres

Wire the handler and filter in `LOGGING`:

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "context": {"()": "rgs_django_utils.logging.logging.LogContextFilter"},
    },
    "handlers": {
        "postgres": {
            "level": "DEBUG",
            "class": "rgs_django_utils.logging.logging.PostgresHandler",
            "filters": ["context"],
        },
    },
    "loggers": {
        "": {"handlers": ["postgres"], "level": "INFO"},
    },
}
```

Group a workflow's log lines under a named run with nested tasks:

```python
from rgs_django_utils.logging.logging import (
    RunContext, TaskContext, get_data_logger, log_counter,
)

data_log = get_data_logger("ingest")

with RunContext("nightly-import"):
    with TaskContext("load-waterways"):
        for row in rows:
            try:
                ingest(row)
                log_counter("imported")
            except ValueError as e:
                data_log.error("invalid row %s", row["code"], extra={"code": 12})
                log_counter("skipped")
```

`TaskContext.__exit__` emits a timing + summary line (duration,
max-severity, counters) that surfaces in the run overview, so failing
tasks are visible even when the Python call returns successfully.

## Important notes

- **Primary-key columns without `Config(...)` default to select-only**
  in the permission helper. That is almost always what you want, but
  surprised me once or twice — override by giving the pk an explicit
  `FPerm`.
- **`@cache` on `PermissionHelper` is per-instance-per-process.** Tests
  that swap `settings.PERMISSION_TREE` between cases must instantiate a
  fresh `PermissionHelper()`.
- **`install_db_defaults_and_relation_cascading` only handles static
  defaults**, `auto_now[_add]` (rewritten to `NOW()`), empty-list
  defaults on array columns (`array[]::integer[]`), and `ON DELETE` of
  `CASCADE` / `SET_NULL` / `SET_DEFAULT`. Callable defaults other than
  the listed ones, and `DateTimeField` defaults, must be installed as
  Postgres trigger functions separately.
- **`decode_jwt` swallows all exceptions** and returns `None`. If you
  need to distinguish "no token" from "bad token", inspect the claim
  shape returned by `Claims`, not the exception flow.
- **`LogRun` is a consumer-app model.** `rgs_django_utils` only provides
  the context + handler; each consuming app owns the concrete `LogRun`
  Django model that `set_run()` creates rows in.

## Development

### Install for local development

The recommended workflow uses [pixi](https://pixi.sh) — it provisions the
Python environment, installs the package editable, and exposes every
common action as a named task:

```bash
git clone https://github.com/GetThePointGit/rgs-django-utils.git
cd rgs-django-utils
pixi install                              # provisions .pixi/envs/default
                                          # and installs the pre-commit git hook
```

Prefer a plain virtualenv? That works too:

```bash
python -m venv venv
source venv/bin/activate
pip install -e .
pip install pytest pytest-cov pytest-django ruff build twine python-dotenv tox
```

### tip for PyCharm

The dev feature installs `pixi-pycharm`, so after `pixi install` add a
Python interpreter of type `conda` pointing at `.pixi/envs/default/libexec/conda`.
If packages are installed with `editable = true`, mark them as "source
root" so the IDE resolves cross-package imports.

### Run the tests

Single Python/Django combination (fast):

```bash
pixi run tests                            # pytest --cov=rgs_django_utils
pixi run tests-verbose                    # adds -v
pixi run -- pytest tests/testapp -v
pixi run -- pytest -k permission
```

The testapp requires a PostGIS database on port `5431` — bring one up
with `docker compose` or point `DATABASES` at an existing local
instance.

Full matrix (every supported Python × Django combination, via tox):

```bash
pixi run tox                              # every env in tox.ini
pixi run -- tox -e py3.12-django5.1       # one env
pixi run -- tox -e ruff                   # the lint-only env
```

### Style and lint

```bash
pixi run style                            # sort-imports + format
pixi run sort-imports                     # ruff check --select I --fix
pixi run format                           # ruff format
pixi run lint                             # ruff check ./rgs_django_utils
```

CI runs the `ruff` tox env on every push.

### Pre-commit hooks

A `.pre-commit-config.yaml` runs ruff (check + format), trailing-
whitespace, end-of-file, YAML/TOML validity and a large-file guard on
every commit. `pixi install` auto-wires the git hook via a
`postinstall` task; to run the full sweep manually:

```bash
pixi run pre-commit-run                   # run every hook on every file
pixi run pre-commit-install               # re-install the git hook
```

The hook runs inside the pre-commit-managed environment (not the pixi
env), so the ruff version is pinned via the `rev` in
`.pre-commit-config.yaml` — bump it with `pixi run -- pre-commit autoupdate`.

### Build an installable artifact

```bash
pixi run build                            # cleans dist/, builds wheel + sdist
pixi run build-check                      # twine check dist/*
```

## Publishing to PyPI

One-time setup:

1. Register an account on https://pypi.org and on
   https://test.pypi.org (separate accounts).
2. Enable 2FA on both.
3. Create an API token on each site (Account settings → API tokens,
   scope: "Entire account" for the first upload, later narrow to the
   project).

Test the release on Test PyPI first:

```bash
pixi run publish-test
# Username: __token__
# Password: <your Test PyPI token>

# In a clean venv, verify the install works:
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            rgs-django-utils
python -c "from rgs_django_utils.database import dj_extended_models; print('ok')"
```

Real release:

```bash
pixi run publish
# Username: __token__
# Password: <your PyPI token>
```

Confirm at https://pypi.org/project/rgs-django-utils/.

For subsequent releases, **Trusted Publishing** via GitHub Actions OIDC
is strongly recommended — no more tokens to rotate. See
<https://docs.pypi.org/trusted-publishers/> and add a
`.github/workflows/publish.yml` that runs on a release tag.

## Status

Alpha (`0.1.0`). Used in waterworks and urbanworks, so the core API surface (`Config`, `FPerm`, `TPerm`,
`FPresets`, `BaseEnum`, `PermissionHelper`, `install_db_*`,
`SettingsGetter`, `Claims`, `JwtUserToken`, `JwtModuleToken`) is
load-bearing. The roles list in `dj_extended_models.roles_list` is
still evolving — see `tests/testapp/models.py` for gaps that surfaced
during the tooling alignment pass.
