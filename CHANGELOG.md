# Changelog

All notable changes to rgs-django-utils will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-09-10

### Added
- `Field.placeholder` — optioneel placeholder-hint, getoond in een leeg
  invoerveld/select vóórdat een waarde gekozen is (bv. terwijl een
  `SelectField`'s server-gedreven opties nog laden). Puur een UI-hint, geen
  default-waarde (`forms/fields/Field.py`).

## [0.6.0] - 2026-09-09

### Added
- `OrderedListField` — formulierveld voor een herordenbare lijst die een vaste
  set verplichte velden combineert met vrij toe te voegen/verwijderen/
  verplaatsen "literal"-slots (een lege string voor een verplichte lege kolom,
  of tekst voor een vaste letterlijke waarde op een vaste positie)
  (`forms/fields/OrderedListField.py`). Bedoeld voor exportformaten met een
  per-organisatie configureerbare veldvolgorde, zoals de metfile-export.

## [0.5.2] - 2026-09-09

### Fixed
- `upsert_multiple_data` kan weer json-waarden wegschrijven. psycopg3 heeft geen
  dumper voor `dict`/`list`, dus `cursor.mogrify` viel om met
  "cannot adapt type 'dict' using placeholder '%t' (format: TEXT)" zodra een rij
  een `json`/`jsonb`-kolom vulde (raakt o.a. `install_db_default_records` met een
  `default_records()` die een configuratie-dict teruggeeft). De waarden van
  kolommen die in Postgres echt `json`/`jsonb` zijn worden nu in
  `psycopg.types.json.Json`/`Jsonb` gewikkeld. Bewust géén procesbrede
  `register_adapter(dict, Json)` zoals in psycopg2: die zou ook queries raken
  waar een dict juist geen JSON is. `None` blijft NULL en een al met
  `json.dumps` geserialiseerde `str` gaat ongewijzigd mee, dus bestaande
  aanroepen blijven werken.

## [0.4.0] - 2026-08-18

### Added
- `CsvFileParserField` — formulierveld dat een geüpload CSV-bestand parseert en
  een kolom-preview + parser-configuratie (delimiter, header, kolomtoewijzing)
  naar de wizard-UI stuurt (`forms/fields/CsvFileParserField.py`).
- `DateField` — datum-formulierveld met ISO-8601-validatie (`YYYY-MM-DD`).
- `forms/file_mixin.py` — gedeelde upload/bestandsafhandeling voor
  formuliervelden.
- `export_datamodel_to_json_schema` exporteert nu ook `_short`-velden.
- `SelectField(display="radio")` — render-hint zodat een (kleine, inline) optie-set
  als radiogroep i.p.v. dropdown getoond kan worden. Default (`None`) blijft dropdown.

### Fixed
- `OneToOneField` krijgt nu dezelfde `pd_type` / `pd_type_func` /
  `sql_alchemy_type` als `ForeignKey` (afgeleid via `foreign_related_fields`).
  Voorheen gaf een OneToOne back-reference (bv. `ww_data.waterway`) een
  `AttributeError` zodra de data_frames/pandas-laag de kolom castte.
- `export_datamodel_to_json_schema`: het `id`-veld van een `BaseEnumExtended`-
  model (de `OneToOneField` die het extended-enum-model aan zijn eigen base
  enum koppelt) werd geëxporteerd als `$ref` naar zichzelf, omdat de
  generieke "FK naar enum"-tak dat veld behandelde als een gewone verwijzing
  naar een los enum-model. Dat gaf een genuine self-reference in de JSON
  Schema (`enum_..._ext.properties.id.$ref == "#/$defs/enum_..._ext"`), die
  consumers als `GraphQueryBuilder` (waterworks-ui) terecht afwijzen als
  "Circular $ref detected". `id` wordt nu geëxporteerd als plain scalar
  primary key i.p.v. als relatie om te expanderen.

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
