# Changelog

All notable changes to rgs-django-utils will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed
- **De library registreert de waterworks-objecten `vw_auth_uman_roles_summary_type`
  (view) en `auth_uman_get_roles_summary` (functie) niet meer in de
  Hasura-metadata** (#37). Ze stonden hardgecodeerd in
  `commands/hasura_permissions.py` en kwamen daardoor in de metadata van élk
  project. Een project zonder die objecten (urbanworks) kreeg twee permanente
  inconsistenties, en sinds 0.10.0 faalt `--apply` daarop. Waterworks gebruikt
  ze ook niet meer. Waterworks moet na deze versie de view en functie zelf
  droppen (`postgres/install/99_last/auth_roles_summary.sql`) en de metadata
  opnieuw genereren.

## [0.10.0] - 2026-09-18

### Changed
- **`generate_hasura_metadata --apply` faalt nu hard als de metadata niet is
  toegepast.** Vijf paden eindigden met exit 0 zonder iets toe te passen: een
  ontbrekend metadatabestand (`--apply-only`), een ontbrekende
  `HASURA_GRAPHQL_URL`, een ontbrekend `HASURA_GRAPHQL_ADMIN_SECRET`, een
  `HTTPError` en een `URLError`. In een deploy-job onder `set -e` betekende dat:
  job `Complete`, groen dashboard, en de rechten in Hasura ongewijzigd. Alle
  vijf geven nu een `CommandError`
  (`management/commands/generate_hasura_metadata.py`).
- De succesmelding `Successfully ran generate_hasura_metadata` stond *boven* de
  apply en staat nu erna. Het log eindigde daardoor altijd op "succes",
  ongeacht wat de apply deed.
- Een inconsistente apply is standaard een fout. Hasura neemt de metadata aan
  (`allow_inconsistent_metadata`) maar laat de objecten vallen die het niet kon
  plaatsen -- precies de plek waar permissies ongemerkt verdwijnen. Dat gaf
  eerder alleen een waarschuwing.

### Added
- `--allow-inconsistent` op `generate_hasura_metadata`: laat een inconsistente
  apply bewust door als waarschuwing in plaats van als fout.

### Fixed
- De URL en het admin-secret worden weer uit de omgeving gelezen als de
  Django-settings ze niet hebben. De bestaande `if settings is None`-tak liep
  nooit (`settings` is een `LazySettings` en is nooit `None`), waardoor een
  ontbrekende instelling een kale `AttributeError` gaf in plaats van een
  bruikbare melding.

### Upgrade
Deploys worden hiermee strenger. Een omgeving waar de apply vandaag stil
mislukt, krijgt nu een rode job -- dat is de bedoeling, maar reken erop bij de
eerste uitrol. Wie bewust wil doorgaan bij inconsistenties zet
`--allow-inconsistent` in de job. De aanroep zonder `--apply` verandert niet.

## [0.9.1] - 2026-09-18

### Fixed
- **Beveiliging.** `JwtUserToken.authenticate` toetste `claims.is_authenticated`
  zonder haakjes, terwijl dat een methode is. Een gebonden methode is altijd
  waar, dus de controle was een no-op: elk bearer-token kwam door de
  authenticatielaag heen -- ook een token waarvan `decode_jwt` de handtekening
  al had afgekeurd (die geeft bij een ongeldige handtekening bewust `None`
  terug in plaats van te raisen). Consumenten die hun autorisatie op `user_id`
  of een rolcheck bouwen vielen bij toeval alsnog dicht, maar een endpoint dat
  alleen "is er iemand ingelogd" nodig heeft had geen slot.
  `JwtModuleToken` was niet geraakt: die roept `has_allowed_role()` wel aan
  (`utils/authorization.py`).
- `Claims.is_authenticated()` geeft een echte `bool` terug in plaats van de
  user of de rollenlijst, en `Claims.__getitem__` roept de methode aan voor die
  ene sleutel -- `{**claims}` gaf eerder de gebonden methode door, dus een
  template die daarop gate't liet iedereen door (`permissions/claims.py`).

### Upgrade
Geen actie nodig naast de versiebump. Tokens die eerder ten onrechte werden
geaccepteerd, worden nu geweigerd; dat is de fix.

## [0.9.0] - 2026-09-16

### Added
- `Presentation` op `Config`: veldlaag voor tabellen, groepedit en kaartlabels
  (`width`, `bulk_edit`, `map_label`, `kind`, `thousands_separator`). Wordt als
  `presentation` (camelCase) per property in `datamodel.schema.json`
  geëxporteerd, naast `unit`/`precision`. Velden zonder `Presentation` krijgen
  geen sleutel, dus bestaande consumers merken niets
  (`database/dj_extended_models.py`, `commands/export_datamodel_to_json_schema.py`).
- `ValidityPeriodMixin.start_date`/`end_date` dragen `Presentation(width=110, bulk_edit=True)`
  (`database/base_models/validity_period.py`).

## [0.8.0] - 2026-09-14

### Changed
- Rolnamen worden gevalideerd tegen `settings.PERMISSION_TREE` in plaats van
  tegen de handgeschreven `roles_list`. Elk project heeft die boom al; de lijst
  ernaast liep uit de pas. Zonder die setting geldt de oude lijst, dus bestaande
  consumers merken niets (`database/dj_extended_models.py`).
- `Roles` verbreedt van `Literal[...]` naar `str`: autocomplete op de
  `FPerm`/`TPerm`-kwargs verdwijnt, de runtime-controle wordt juist strenger
  (`database/dj_extended_models.py`).

### Added
- `build_claim_function_sql()` genereert de plpgsql-functie die rol-id's naar
  `x-hasura-allowed-roles` vertaalt uit diezelfde `PERMISSION_TREE`. Die
  overervingsgraaf stond voorheen een tweede keer met de hand in een migratie.
  De functie is `IMMUTABLE` en `PARALLEL SAFE`, zodat hij bruikbaar is in een
  `GENERATED ... STORED`-kolom (`database/claim_sql.py`).
- `BASE_MODEL_ROLES` vertaalt de rolnamen die de abstracte basismodellen
  hardcoderen (`project_read`, `project_edit`, `proj_read`) naar het
  vocabulaire van het eigen project. Nodig omdat rolnamen sinds deze release
  tegen `PERMISSION_TREE` gevalideerd worden: zonder vertaling kon een project
  met een ander vocabulaire de mixins niet meer importeren. Zonder de setting
  blijft elke naam zichzelf, dus bestaande consumers merken niets
  (`database/base_models/roles.py`).

## [0.7.1] - 2026-09-13

### Fixed
- `PolygonField`/`MultiPolygonField.pd_type_func` decodeerden geen WKB: een kolom
  met hex-EWKB-tekst (zoals `pd.read_sql` PostGIS-geometrie teruggeeft) crashte
  met "Non geometry data passed to GeoSeries constructor". Alle geometrie-velden
  gaan nu door één helper (`_to_geoseries`) die hex-EWKB, WKB-bytes, al
  gedecodeerde shapely-objecten, een bestaande `GeoSeries` en alleen-NULL
  kolommen accepteert — de `from_wkb`-velden crashten voorheen juist op al
  gedecodeerde objecten en op NaN (`database/dj_extended_models.py`).

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
