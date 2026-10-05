import logging
import os

log = logging.getLogger(__name__)

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thissite.settings")
    setup_django(log=log)

from django.apps import apps
from django.conf import settings
from django.db import models as dj_models

from rgs_django_utils.database.dj_settings_helper import TableDescriptionGetter
from rgs_django_utils.models.views.abstract import HasuraTrackedView

# Django field type name → JSON Schema "type"
_TYPE_MAP: dict[str, str] = {
    "AutoField": "integer",
    "BigAutoField": "integer",
    "SmallAutoField": "integer",
    "IntegerField": "integer",
    "BigIntegerField": "integer",
    "SmallIntegerField": "integer",
    "PositiveIntegerField": "integer",
    "PositiveBigIntegerField": "integer",
    "PositiveSmallIntegerField": "integer",
    "FloatField": "number",
    "DecimalField": "number",
    "BooleanField": "boolean",
    "NullBooleanField": "boolean",
    "UUIDField": "string",
    "CharField": "string",
    "TextField": "string",
    "TextStringField": "string",  # rgs_django_utils custom field
    "SlugField": "string",
    "EmailField": "string",
    "URLField": "string",
    "IPAddressField": "string",
    "GenericIPAddressField": "string",
    "DateField": "string",
    "DateTimeField": "string",
    "TimeField": "string",
    "DurationField": "string",
    "FileField": "string",
    "ImageField": "string",
}

# Django field type name → JSON Schema "format"
_FORMAT_MAP: dict[str, str] = {
    "UUIDField": "uuid",
    "DateField": "date",
    "DateTimeField": "date-time",
    "TimeField": "time",
    "EmailField": "email",
    "URLField": "uri",
    "FileField": "uri",
    "ImageField": "uri",
}

# GIS geometry field type names → represented as GeoJSON objects
_GIS_FIELDS = frozenset(
    {
        "PointField",
        "LineStringField",
        "PolygonField",
        "MultiPointField",
        "MultiLineStringField",
        "MultiPolygonField",
        "GeometryCollectionField",
        "GeometryField",
        "RasterField",
    }
)

# Auto-generated PK types – always readOnly
_AUTO_PK_TYPES = frozenset({"AutoField", "BigAutoField", "SmallAutoField"})


log = logging.getLogger(__name__)

# ── Management command ────────────────────────────────────────────────────────


def export_datamodel_to_json_schema(export_path=None):
    """Dump the full datamodel as a JSON Schema 2020-12 document.

    Walks every installed Django model, converts it to a JSON Schema
    definition via :class:`SchemaGenerator` and writes the combined
    ``oneOf`` / ``$defs`` document. The output is used as input for the
    form builder, for client-side validation and as source for parts of
    the Hasura metadata.

    Parameters
    ----------
    export_path : str, optional
        Target ``.json`` path. Defaults to
        ``<BASE_DIR>/../var/template.schema.json``. Parent directories are
        created on demand.
    """
    if export_path is None:
        export_path = os.path.join(settings.BASE_DIR, os.pardir, "var", "template.schema.json")
        os.makedirs(os.path.dirname(export_path), exist_ok=True)

    app_models = [model for model in apps.get_models() if callable(model) and issubclass(model, dj_models.Model)]  # NOQA
    schema_generator = SchemaGenerator(models=app_models)
    result: dict[str, dict | str] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Template datamodel",
        "type": "object",
        "description": "JSON Schema representation of the datamodel. Deze schema's worden gebruikt als basis voor de Hasura metadata, en kunnen ook worden gebruikt voor documentatie en client-side validatie.",
        "oneOf": [],
        "$defs": {},
    }

    for model in app_models:
        result["oneOf"].append({"$ref": f"#/$defs/{model._meta.db_table}"})
        if _is_base_enum(model) and not _is_base_enum_extended(model):
            result["$defs"][model._meta.db_table] = schema_generator._enum_def(model)
        else:
            (props, required) = schema_generator.model_properties(model)
            table_def: dict = {
                "type": "object",
                "title": str(model._meta.verbose_name).capitalize(),
                "description": _td_attr(model, "description", ""),
                "properties": props,
                "required": required,
            }
            if modules := _modules_to_list(_td_attr(model, "modules", None)):
                table_def["modules"] = modules
            result["$defs"][model._meta.db_table] = table_def

    _merge_view_defs(result, app_models)

    with open(export_path, "w") as f:
        import json

        json.dump(result, f, indent=2, ensure_ascii=False)
        log.info(f"Exported datamodel JSON Schema to {export_path}")


def _merge_view_defs(result: dict, app_models: list) -> None:
    """Merge the JSON Schema parts of all Hasura-tracked views into *result*.

    Adds every view definition that is not yet present to ``$defs`` and
    ``oneOf``, and gives each referencing table a ``<field>_short`` property
    (``$ref`` to the view) plus the scalar FK column, unless already present.

    Parameters
    ----------
    result : dict
        The schema document under construction; mutated in place.
    app_models : list of type[django.db.models.Model]
        Models in scope, passed on to ``get_all_views``.
    """
    for view_cls in HasuraTrackedView.all():
        for view in view_cls.get_all_views(app_models=app_models):
            view: HasuraTrackedView
            parts = view.get_json_schema_parts()
            fields = view.fields_referencing_original_table
            definitions = parts["defs"]
            referenced_by = parts["referenced_by"]
            for defn in definitions:
                # do not overwrite an existing definition, to prevent conflicts between views that reference the same model
                if result["$defs"].get(defn) is None:
                    result["$defs"][defn] = definitions[defn]
                    result["oneOf"].append({"$ref": f"#/$defs/{defn}"})
            for ref in referenced_by:
                _add_view_reference_props(result["$defs"], ref, fields, referenced_by[ref])


def _add_view_reference_props(defs: dict, ref: str, fields, view_def_name: str) -> None:
    """Add the ``<field>_short`` and FK-column properties for one referencing table.

    Existing properties are never overwritten.

    Parameters
    ----------
    defs : dict
        The ``$defs`` mapping of the schema document; mutated in place.
    ref : str
        Name of the table definition that references the view.
    fields : iterable of django.db.models.ForeignKey
        The FK fields that point at the view's original table.
    view_def_name : str
        Name of the view definition in ``$defs``.
    """
    for field in fields:
        props = defs[ref]["properties"]
        if props.get(f"{field.name}_short") is None:
            short_prop: dict = {"$ref": f"#/$defs/{view_def_name}"}
            short_prop["title"] = props.get(field.name, {}).get("title") or str(field.verbose_name).capitalize()
            props[f"{field.name}_short"] = short_prop
        if props.get(field.attname) is None:
            props[field.attname] = _fk_attname_prop(field, with_title=True)


# ── Schema generator ──────────────────────────────────────────────────────────


class SchemaGenerator:
    """Converts a Django model graph into a JSON Schema 2020-12 document.

    Maintains a ``$defs`` cache so shared models are emitted once and
    referenced by ``$ref``. Circular references are broken by the
    ``_in_progress`` guard set.

    Parameters
    ----------
    models : list of type[django.db.models.Model]
        Models that should be considered in scope.
    """

    def __init__(self, models: list):
        self.models = models
        self.defs: dict[str, dict] = {}
        self._in_progress: set[str] = set()  # circular-reference guard

        self.views_by_table: dict[str, dict] = {}
        for hasuraTrackedView in HasuraTrackedView.all():
            hasuraTrackedView: type[HasuraTrackedView]
            for view in hasuraTrackedView.get_all_views(app_models=self.models):
                if view._meta.db_table is not None:
                    self.views_by_table[view._meta.db_table] = view

    # ── public API ────────────────────────────────────────────────────────────

    def generate(self, root_model) -> dict:
        meta = root_model._meta
        title = str(meta.verbose_name).capitalize()
        description = _td_attr(root_model, "description", "")

        props, required = self.model_properties(model_class=root_model)

        schema: dict = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": title,
            "type": "object",
        }
        if description:
            schema["description"] = description
        display_field = TableDescriptionGetter(root_model).display_field
        if display_field:
            schema["x-displayField"] = display_field
        if props:
            schema["properties"] = props
        if required:
            schema["required"] = required
        if self.defs:
            schema["$defs"] = self.defs

        return schema

    # ── $defs management ──────────────────────────────────────────────────────

    def _ensure_def(self, model_class, *, parent_model=None) -> str:
        """Ensure *model_class* has an entry in $defs and return its $ref."""
        name = model_class._meta.db_table
        if name in self.defs or name in self._in_progress:
            return f"#/$defs/{name}"

        self._in_progress.add(name)

        if _is_base_enum(model_class) and not _is_base_enum_extended(model_class):
            self.defs[name] = self._enum_def(model_class)
        else:
            props, required = self.model_properties(model_class=model_class, parent_model=parent_model)
            meta = model_class._meta
            defn: dict = {
                "type": "object",
                "title": str(meta.verbose_name).capitalize(),
            }
            desc = _td_attr(model_class, "description", "")
            if desc:
                defn["description"] = desc
            display_field = TableDescriptionGetter(model_class).display_field
            if display_field:
                defn["x-displayField"] = display_field
            if props:
                defn["properties"] = props
            if required:
                defn["required"] = required
            self.defs[name] = defn

        self._in_progress.discard(name)
        return f"#/$defs/{name}"

    def _enum_def(self, model_class, *, field=None) -> dict:
        """Rule 23 – BaseEnum subclasses: oneOf with entries consisting of objects containing const, type, readonly and title properties."""
        meta = model_class._meta
        title = str(meta.verbose_name).capitalize()
        desc = _td_attr(model_class, "description", "")
        oneofs = _enum_oneofs(model_class, enum_filter=_config_attr(field, "enum_filter") if field else None)
        defn: dict = {"type": "string", "title": title}
        if desc:
            defn["description"] = desc
        if oneofs:
            defn["oneOf"] = oneofs
        return defn

    # ── property collection ───────────────────────────────────────────────────

    def model_properties(self, model_class, *, parent_model=None) -> tuple[dict, list]:
        """Return (properties dict, required list) for *model_class*."""
        from django.db.models.fields.related import ForeignKey
        from django.db.models.fields.reverse_related import ManyToManyRel, ManyToOneRel

        props: dict = {}
        required: list = []

        # # No longer need to mark mixin fields as readOnly, since we can do that in the form schema builder.
        # # Mixin fields are grouped into sub-objects instead of being emitted flat.
        # mixin_groups = _get_mixin_groups(model_class)
        # mixin_field_names: frozenset[str] = frozenset(name for _, _, names in mixin_groups for name in names)

        for field in model_class._meta.get_fields():
            # ── reverse relations (OneToOneRel is a subclass of ManyToOneRel)
            if isinstance(field, (ManyToOneRel, ManyToManyRel)):
                props[getattr(field, "related_name", None)] = self._reverse_relation_prop(field, model_class)
                continue

            # ── skip non-concrete fields (no DB column)
            if not hasattr(field, "column"):
                continue

            # # No longer need to mark mixin fields as readOnly, since we can do that in the form schema builder.
            # if field.name in mixin_field_names:
            #     prop["readOnly"] = True

            is_foreign_key = isinstance(field, ForeignKey)
            if (
                is_foreign_key
                and self._is_skipped_fk_target(model_class=field.related_model)
                and not _is_base_enum(field.related_model)
            ):
                continue

            if _is_base_enum(field.related_model):
                props.update(self._enum_fk_props(field, model_class))
                continue

            prop = self._field_to_property(field=field)
            if prop is None:
                continue

            props[field.name] = prop
            if _is_required(field):
                required.append(field.name)

            # For FK fields, also emit the scalar attname column (e.g. project_id).
            # The relation field (e.g. project) gives the $ref, but Hasura mutations
            # accept the raw integer FK column, so the form schema needs it too.
            if is_foreign_key and field.attname != field.name and field.attname not in props:
                props[field.attname] = _fk_attname_prop(field, with_readonly=True)

        return props, required

    def _reverse_relation_prop(self, field, model_class) -> dict:
        """Return the property for a reverse relation of *model_class*.

        A reverse ``OneToOneRel`` becomes a plain ``$ref`` (object relation);
        other reverse relations become an array of ``$ref`` items.

        Parameters
        ----------
        field : django.db.models.ForeignObjectRel
            The reverse relation (``OneToOneRel``, ``ManyToOneRel`` or
            ``ManyToManyRel``).
        model_class : type[django.db.models.Model]
            The model that owns the reverse relation.

        Returns
        -------
        dict
            The JSON Schema property.
        """
        from django.db.models.fields.reverse_related import OneToOneRel

        sub_model = field.related_model
        ref = self._ensure_def(model_class=sub_model, parent_model=model_class)
        # OneToOneRel MUST be checked before the generic (ManyToOneRel,
        # ManyToManyRel) case: Django's OneToOneRel is a *subclass* of
        # ManyToOneRel. Treating it as generic emitted every reverse
        # OneToOneField (e.g. ProfileMeasurementData.profile_measurement ->
        # pm.data) as `type: array` even though Hasura — which infers
        # object- vs array-relationship from the DB-level unique
        # constraint the OneToOneField creates — exposes it as a plain
        # object relation. That mismatch made the frontend build
        # `{data: [...], on_conflict}` for a field where Hasura expects
        # `{data: {...}, on_conflict}` (`*_obj_rel_insert_input`),
        # producing "expected an object ... but found a list" on save.
        if isinstance(field, OneToOneRel):
            return {"$ref": ref}

        sub_meta = sub_model._meta
        prop: dict = {
            "type": "array",
            "title": str(sub_meta.verbose_name_plural or sub_meta.verbose_name).capitalize(),
            "items": {"$ref": ref},
        }
        desc = _td_attr(sub_model, "description", "")
        if desc:
            prop["description"] = desc
        return prop

    def _enum_fk_props(self, field, model_class) -> dict:
        """Return the properties for a FK/OneToOne to a ``BaseEnum``.

        Always emits ``<veld>_id`` with the enum codes. For an extended enum
        the expanded record is added as a readOnly ``$ref`` under the field
        name; on the extended-enum table itself the ``id`` link is emitted as
        a plain scalar instead.

        Parameters
        ----------
        field : django.db.models.ForeignKey
            The FK or OneToOne field pointing at the enum.
        model_class : type[django.db.models.Model]
            The model that owns *field*.

        Returns
        -------
        dict
            Property name → JSON Schema property, in emission order.
        """
        field_name = field.name
        enum_schema = self._enum_def(field.related_model, field=field)
        # type array for nullable, so sanitizeObject treats it as nullable
        out: dict = {f"{field_name}_id": _nullable(enum_schema, getattr(field, "null", False))}

        # `id` on the extended-enum table itself is the OneToOneField that
        # BaseEnumExtendedMetaClass creates to link back to its own base enum
        # (field.related_model.ExtendedClass is this very model). Expanding
        # it as an "extended object" $ref below would point the $defs entry
        # at itself - an unresolvable cycle that GraphQueryBuilder rightly
        # rejects. It's the table's own primary key here, not a relation to
        # expand, so emit it as a plain scalar instead.
        if field.primary_key and getattr(field.related_model, "ExtendedClass", None) is model_class:
            id_prop: dict = {"type": enum_schema["type"], "readOnly": True}
            if title := _verbose_title(field):
                id_prop["title"] = title
            out[field_name] = id_prop
            return out

        if not hasattr(field.related_model, "extended") or not _is_base_enum_extended(
            field.related_model.extended.related.model
        ):
            return out
        extended_model = field.related_model.extended.related.related_model  # ExtendedEnum
        ref = self._ensure_def(model_class=extended_model)
        # Altijd readOnly: het uitgeklapte enum-record is referentiedata
        # (alleen om te tonen). De keuze zelf gaat via `<veld>_id`; een
        # schrijfbare relatie laat de formulierbouwer 'm als geneste
        # insert meesturen, en die bestaat niet in Hasura ("field
        # '<veld>' not found in type: '<model>_insert_input'").
        out[field_name] = {"$ref": ref, "readOnly": True}
        return out

    # ── field → property ──────────────────────────────────────────────────────

    def _field_to_property(self, field) -> dict | None:
        """Convert a single Django field to a JSON Schema property dict."""
        from django.db.models.fields.related import ForeignKey, ManyToManyField, OneToOneField

        field_type = type(field).__name__
        nullable = getattr(field, "null", False)

        # title, description, docFull, unit, precision, modules, presentation (rules 21, 22)
        prop: dict = _metadata_props(field)

        # readOnly (rules 24-26)
        if _is_readonly(field):
            prop["readOnly"] = True

        # ── FK / OneToOne (rules 19, 23) ──────────────────────────────────
        if isinstance(field, (ForeignKey, OneToOneField)):
            prop.update(self._relation_schema(field, nullable))
            return prop

        # ── ManyToMany (rule 20) ───────────────────────────────────────────────
        if isinstance(field, ManyToManyField):
            ref = self._ensure_def(model_class=field.related_model)
            prop["type"] = "array"
            prop["items"] = {"$ref": ref}
            return prop

        # ── GIS geometry ──────────────────────────────────────────────────────
        if field_type in _GIS_FIELDS:
            prop.update(_nullable({"type": "object"}, nullable))
            if not prop.get("description"):
                prop["description"] = "GeoJSON geometrie object."
            return prop

        # ── ArrayField (rule 34) ──────────────────────────────────────────────
        if field_type == "ArrayField":
            prop["type"] = "array"
            base = getattr(field, "base_field", None)
            if base and (inner := self._field_to_property(field=base)):
                prop["items"] = inner
            return prop

        # ── JSONField (rule 38) ───────────────────────────────────────────────
        if field_type == "JSONField":
            prop.update(_nullable({"type": "object"}, nullable))
            prop["additionalProperties"] = True
            return prop

        # ── Scalar fields ─────────────────────────────────────────────────────
        prop.update(_scalar_props(field, field_type, nullable))
        return prop

    def _relation_schema(self, field, nullable: bool) -> dict:
        """Return the type part of a FK/OneToOne property.

        A relation to a ``BaseEnum`` gives the enum's ``type`` and ``oneOf``;
        any other relation a ``$ref`` to the related model. Both are wrapped
        in ``anyOf [..., null]`` when nullable.

        Parameters
        ----------
        field : django.db.models.ForeignKey
            The FK or OneToOne field.
        nullable : bool
            Whether the column accepts NULL.

        Returns
        -------
        dict
            Keys to merge into the property.
        """
        if _is_base_enum(field.related_model):
            enum_schema = self._enum_def(field.related_model, field=field)
            enum_type_part: dict = {"type": enum_schema["type"]}
            if "oneOf" in enum_schema:
                enum_type_part["oneOf"] = enum_schema["oneOf"]
            return _nullable(enum_type_part, nullable, wrap=True)
        ref = self._ensure_def(model_class=field.related_model)
        return _nullable({"$ref": ref}, nullable, wrap=True)

    def _is_skipped_fk_target(self, model_class) -> bool:
        """Return True if *model_class* not in models."""
        return model_class not in self.models


# # ── Mixin grouping ────────────────────────────────────────────────────────────
# # No longer need to mark mixin fields as readOnly, since we can do that in the form schema builder.

# # Each entry: (mixin_import_path, mixin_name, property_name, title)
# # Ordered from most specific to least specific so issubclass short-circuits correctly.
# _MIXIN_GROUP_DEFS = [
#     (
#         "rgs_django_utils.database.base_models.modification_mixin",
#         ("ModificationSourceMixin", "ModificationMetaMixin"),
#         "modification_source",
#         "Bron metadata",
#     ),
#     (
#         "rgs_django_utils.database.base_models.validity_period",
#         ("ValidityPeriodMixin",),
#         "validity_period",
#         "Geldigheidsperiode",
#     ),
# ]

# # No longer need to mark mixin fields as readOnly, since we can do that in the form schema builder.
# def _get_mixin_groups(model_class) -> list[tuple[str, str, frozenset[str]]]:
#     """Return [(property_name, title, field_names), …] for each mixin that *model_class* inherits."""
#     groups: list[tuple[str, str, frozenset[str]]] = []
#     for module_path, class_names, prop_name, title in _MIXIN_GROUP_DEFS:
#         try:
#             import importlib

#             mod = importlib.import_module(module_path)
#             mixin_classes = [getattr(mod, n) for n in class_names if hasattr(mod, n)]
#         except ImportError:
#             continue

#         primary = mixin_classes[0]
#         if not (isinstance(model_class, type) and issubclass(model_class, primary)):
#             continue

#         field_names: set[str] = set()
#         for cls in mixin_classes:
#             for f in cls._meta.local_fields:
#                 field_names.add(f.name)
#             for f in cls._meta.local_many_to_many:
#                 field_names.add(f.name)
#         groups.append((prop_name, title, frozenset(field_names)))

#     return groups


# ── Helpers ───────────────────────────────────────────────────────────────────


def _nullable(schema: dict, nullable: bool, *, wrap: bool = False) -> dict:
    """Make *schema* accept ``null`` when *nullable*.

    Parameters
    ----------
    schema : dict
        The (partial) JSON Schema to make nullable.
    nullable : bool
        Whether the column accepts NULL; when False *schema* is returned as is.
    wrap : bool, optional
        True wraps the schema as ``{"anyOf": [schema, {"type": "null"}]}``
        (for ``$ref`` and enum parts); False (default) returns a copy with
        ``type`` turned into ``[type, "null"]``, keeping the key order.

    Returns
    -------
    dict
        The nullable schema, or *schema* itself when not nullable.
    """
    if not nullable:
        return schema
    if wrap:
        return {"anyOf": [schema, {"type": "null"}]}
    return {**schema, "type": [schema["type"], "null"]}


def _metadata_props(field) -> dict:
    """Return the descriptive keywords of a field property.

    Collects, in this order, ``title`` (verbose name, rule 22),
    ``description`` (``doc_short``, rule 21), ``docFull``, ``unit``
    (``doc_unit``), ``precision``, ``modules`` and ``presentation`` from the
    field and its ``Config``. Keywords without a value are left out.

    Parameters
    ----------
    field : django.db.models.Field
        The field to describe.

    Returns
    -------
    dict
        The keywords that have a value.
    """
    prop: dict = {}
    if title := _verbose_title(field):
        prop["title"] = title
    if doc := _config_attr(field, "doc_short"):
        prop["description"] = doc
    # background information
    if doc_full := _config_attr(field, "doc_full"):
        prop["docFull"] = doc_full
    # e.g. "m", "°C" – aansluitend op rgs-schema custom keyword
    if unit := _config_attr(field, "doc_unit"):
        prop["unit"] = unit
    if (precision := _config_attr(field, "precision")) is not None:
        prop["precision"] = precision
    # None = niet beperkt
    if modules := _modules_to_list(_config_attr(field, "modules")):
        prop["modules"] = modules
    # field-layer hints for tables, bulk edit, map labels
    if (presentation := _config_attr(field, "presentation")) is not None:
        prop["presentation"] = _presentation_to_dict(presentation)
    return prop


def _is_readonly(field) -> bool:
    """Return True when the field is read-only in forms (rules 24-26).

    Parameters
    ----------
    field : django.db.models.Field
        The field to check.

    Returns
    -------
    bool
        True for calculated (``c_``-prefixed) fields, primary keys,
        auto-generated PKs, non-editable fields and ``auto_now(_add)`` fields.
    """
    return (
        field.name.startswith("c_")  # rule 25: calculated fields
        or getattr(field, "primary_key", False)  # rule 24
        or type(field).__name__ in _AUTO_PK_TYPES  # rule 24
        or not getattr(field, "editable", True)  # rule 26
        or getattr(field, "auto_now", False)  # rule 26
        or getattr(field, "auto_now_add", False)  # rule 26
    )


def _scalar_json_type(field, field_type: str) -> str:
    """Return the JSON Schema ``type`` of a scalar field.

    Parameters
    ----------
    field : django.db.models.Field
        The scalar field.
    field_type : str
        ``type(field).__name__``.

    Returns
    -------
    str
        The mapped type; custom subclasses (e.g. ``TextStringField`` →
        ``CharField``) are resolved via the MRO, with ``"string"`` as fallback.
    """
    json_type = _TYPE_MAP.get(field_type)
    if json_type is not None:
        return json_type
    for base_cls in type(field).__mro__[1:]:
        if json_type := _TYPE_MAP.get(base_cls.__name__):
            return json_type
    return "string"  # safe fallback


def _scalar_props(field, field_type: str, nullable: bool) -> dict:
    """Return the type keywords of a scalar field property.

    Parameters
    ----------
    field : django.db.models.Field
        The scalar field.
    field_type : str
        ``type(field).__name__``.
    nullable : bool
        Whether the column accepts NULL.

    Returns
    -------
    dict
        ``type`` plus, when applicable, ``format``, ``maxLength`` (rule 31)
        and ``minimum`` (rule 30).
    """
    json_type = _scalar_json_type(field, field_type)
    prop = _nullable({"type": json_type}, nullable)
    if fmt := _FORMAT_MAP.get(field_type):
        prop["format"] = fmt
    if json_type == "string" and (ml := getattr(field, "max_length", None)):
        prop["maxLength"] = ml
    if json_type in ("integer", "number") and "Positive" in field_type:
        prop["minimum"] = 0
    return prop


def _fk_attname_prop(field, *, with_title: bool = False, with_readonly: bool = False) -> dict:
    """Return the property for the scalar FK column (``field.attname``, e.g. ``project_id``).

    Parameters
    ----------
    field : django.db.models.ForeignKey
        The FK field.
    with_title : bool, optional
        Add the verbose name as ``title``.
    with_readonly : bool, optional
        Add ``readOnly`` when the field is not editable or a primary key.

    Returns
    -------
    dict
        ``type`` and, when applicable, ``format``, ``readOnly``, ``title``
        and ``description`` (``doc_short``).
    """
    pk_type, pk_fmt = _fk_pk_json_type(field)
    prop: dict = {"type": pk_type}
    if pk_fmt:
        prop["format"] = pk_fmt
    if with_readonly and (not getattr(field, "editable", True) or getattr(field, "primary_key", False)):
        prop["readOnly"] = True
    if with_title and (title := str(field.verbose_name).capitalize()):
        prop["title"] = title
    if doc := _config_attr(field, "doc_short"):
        prop["description"] = doc
    return prop


def _fk_pk_json_type(field) -> tuple[str, str | None]:
    """Return (json_type, format_or_none) for the PK column of a FK's related model."""
    pk_field = field.related_model._meta.pk
    if pk_field is None:
        return "integer", None
    pk_type_name = type(pk_field).__name__
    json_type = _TYPE_MAP.get(pk_type_name, "integer")
    return json_type, _FORMAT_MAP.get(pk_type_name)


def _is_base_enum(model_class) -> bool:
    """Return True if *model_class* is a concrete subclass of BaseEnum."""
    try:
        from rgs_django_utils.database.base_models.enums import BaseEnum

        return (
            isinstance(model_class, type)
            and issubclass(model_class, BaseEnum)
            and not getattr(model_class._meta, "abstract", True)
        )
    except ImportError:
        return False


def _is_base_enum_extended(model_class) -> bool:
    """Return True if *model_class* is a concrete subclass of BaseEnumExtended (base or _ext table)."""
    try:
        from rgs_django_utils.database.base_models.enums import BaseEnumExtended

        return (
            isinstance(model_class, type)
            and issubclass(model_class, BaseEnumExtended)
            and not getattr(model_class._meta, "abstract", True)
        )
    except ImportError:
        return False


def _enum_oneofs(model_class, *, enum_filter: dict | None = None) -> list[dict]:
    """Return [{const, title, standards?}, …] from a BaseEnum model's default_records().

    Parameters
    ----------
    model_class : type
        Het enum-model.
    enum_filter : dict, optional
        Sleutel/waarde-paren waaraan een rij moet voldoen om mee te gaan.
        De sleutel wordt gezocht in ``fields``; staat hij daar niet, dan wordt
        ook ``<sleutel>_id`` en, andersom, ``<sleutel>`` zonder een ``_id``-staart
        geprobeerd - FK-kolommen staan in ``default_records`` soms met en soms
        zonder die staart. Een onbekende sleutel laat het filter vallen - beter
        het volledige ``oneOf`` dan een leeg formulier.

    Returns
    -------
    list of dict
        Eén dict per rij, met ``standards`` erbij als de enum die kolom heeft.
    """
    try:
        records = model_class.default_records()
        fields = records["fields"]
        data = records["data"]
        id_idx = fields.index("id")
        name_idx = fields.index("name")
        standards_idx = fields.index("standards") if "standards" in fields else None

        def _value(row, idx):
            return row[idx] if isinstance(row, tuple) else row[fields[idx]]

        rows = list(data)
        for key, expected in (enum_filter or {}).items():
            if key in fields:
                idx = fields.index(key)
            elif f"{key}_id" in fields:
                idx = fields.index(f"{key}_id")
            elif key.endswith("_id") and key[:-3] in fields:
                idx = fields.index(key[:-3])
            else:
                continue
            rows = [row for row in rows if _value(row, idx) == expected]

        oneofs = []
        for row in rows:
            option = {"const": _value(row, id_idx), "title": _value(row, name_idx)}
            if standards_idx is not None:
                option["standards"] = list(_value(row, standards_idx) or [])
            oneofs.append(option)
        return oneofs
    except Exception:
        return []


def _config_attr(field, attr: str, default=None):
    """Read *attr* from a field's ``Config`` object.

    ``rgs_django_utils.database.dj_extended_models.FieldConfig._init_extras``
    stores the ``Config`` instance as ``field.r_config`` (not ``field.config``,
    which is reserved on some related-field types). Fall back to ``field.config``
    so plain Django models without ``r_config`` still work.
    """
    config = getattr(field, "r_config", None) or getattr(field, "config", None)
    return getattr(config, attr, default) if config else default


def _presentation_to_dict(presentation) -> dict:
    """Serialise a ``Presentation`` to its camelCase JSON Schema form.

    Parameters
    ----------
    presentation : rgs_django_utils.database.dj_extended_models.Presentation
        The field-layer object from ``Config.presentation``.

    Returns
    -------
    dict
        ``width`` and ``kind`` only when set; ``bulkEdit``, ``mapLabel`` and
        ``thousandsSeparator`` always, so consumers need no defaults.
    """
    out: dict = {}
    if presentation.width is not None:
        out["width"] = presentation.width
    out["bulkEdit"] = bool(presentation.bulk_edit)
    out["mapLabel"] = bool(presentation.map_label)
    if presentation.kind is not None:
        out["kind"] = presentation.kind
    out["thousandsSeparator"] = bool(presentation.thousands_separator)
    return out


def _verbose_title(field) -> str | None:
    """Return the field verbose_name as a capitalised title, or None."""
    vn = getattr(field, "verbose_name", None)
    if vn and str(vn) != field.name:
        return str(vn).capitalize()
    return None


def _td_attr(model_class, attr: str, default=None):
    """Read *attr* from a model's inner TableDescription class."""
    td = getattr(model_class, "TableDescription", None)
    return getattr(td, attr, default) if td else default


def _modules_to_list(modules) -> list[str] | None:
    """Normalise a ``modules`` value to a list of strings, or ``None``.

    ``modules`` can be:

    - ``None`` – not restricted, returns ``None`` so the caller skips the keyword.
    - ``"*"`` – all modules, treated as not restricted, returns ``None``.
    - a string – single module name, returns ``[modules]``.
    - an iterable – returns ``[str(m) for m in modules]``.
    """
    if modules is None or modules == "*":
        return None
    if isinstance(modules, str):
        return [modules]
    try:
        result = [str(m) for m in modules]
    except TypeError:
        return None
    return result or None


def _is_required(field) -> bool:
    """Return True when a field must appear in the schema's required array.

    A field is required when it cannot be NULL and cannot be blank – i.e. it is
    always present in a complete data record, even if auto-generated (readOnly).
    """
    if getattr(field, "null", False):
        return False
    if getattr(field, "blank", False):
        return False
    return True


if __name__ == "__main__":
    import os

    export_datamodel_to_json_schema(os.path.join(os.path.dirname(__file__), "datamodel2.schema.json"))
