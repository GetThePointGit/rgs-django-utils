
import logging

from django.apps import apps
from django.db import models as dj_models

log = logging.getLogger(__name__)

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django(log=log)

from thissite import settings

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


_META_MODEL_BY_ROOT = {
    "Waterway": frozenset({"ProfileLocation", "DredgingCluster"}),
}

# FK relations (forward and reverse) whose related model is a subclass of any of these
# base classes are excluded from schema expansion.
# Key: base class name (for documentation / lookup); Value: (module_path, class_name).
_SKIP_FK_CLASSES: dict[str, tuple[str, str]] = {
    "Waterway": ["ProjectConfig", "ProfileMeasurement", "Project", "Organization", "User", "Task", "Job", "WaterwayData"],
}

log = logging.getLogger(__name__)

# ── Management command ────────────────────────────────────────────────────────

def export_datamodel_to_json_schema(export_path=None):
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
        "$defs": {}
    }

    for model in app_models:
        (props, required) = schema_generator.model_properties(model)
        result["oneOf"].append({"$ref": f"#/$defs/{model.__name__}"})
        result["$defs"][model.__name__] = {
            "type": "object",
            "title": str(model._meta.verbose_name).capitalize(),
            "description": _td_attr(model, "description", ""),
            "properties": props,
        }

    with open(export_path, "w") as f:
        import json

        json.dump(result, f, indent=2, ensure_ascii=False)
        log.info(f"Exported datamodel JSON Schema to {export_path}")

# ── Schema generator ──────────────────────────────────────────────────────────

class SchemaGenerator:
    """Converts a Django model graph to a JSON Schema 2020-12 document."""

    def __init__(self, models: list):
        self.models = models
        self.defs: dict[str, dict] = {}
        self._in_progress: set[str] = set()  # circular-reference guard

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
        name = model_class.__name__
        if name in self.defs or name in self._in_progress:
            return f"#/$defs/{name}"

        self._in_progress.add(name)

        if name in self.models:
            self.defs[name] = self._metadata_def(model_class)
        elif _is_base_enum(model_class):
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
            if props:
                defn["properties"] = props
            if required:
                defn["required"] = required
            self.defs[name] = defn

        self._in_progress.discard(name)
        return f"#/$defs/{name}"

    def _metadata_def(self, model_class) -> dict:
        """Rule 46 – Project / Organisation / User: id, ids, name only."""
        meta = model_class._meta
        return {
            "type": "object",
            "title": str(meta.verbose_name).capitalize(),
            "description": "Metadata object. Alle velden zijn alleen-lezen.",
            "properties": {
                "id": {"type": "integer", "title": "ID", "readOnly": True},
                "ids": {"type": "string", "title": "Code", "readOnly": True},
                "name": {"type": "string", "title": "Naam", "readOnly": True},
            },
            "required": ["id", "ids", "name"],
        }

    def _enum_def(self, model_class) -> dict:
        """Rule 25 – BaseEnum subclasses: oneOf with const / title entries."""
        meta = model_class._meta
        title = str(meta.verbose_name).capitalize()
        desc = _td_attr(model_class, "description", "")
        oneofs = _enum_oneofs(model_class)
        defn: dict = {"type": "string", "title": title}
        if desc:
            defn["description"] = desc
        if oneofs:
            defn["oneOf"] = oneofs
        return defn

    # ── property collection ───────────────────────────────────────────────────

    def model_properties(
        self, model_class, *, parent_model=None
    ) -> tuple[dict, list]:
        """Return (properties dict, required list) for *model_class*."""
        from django.db.models.fields.related import ForeignKey, OneToOneField
        from django.db.models.fields.reverse_related import ManyToManyRel, ManyToOneRel, OneToOneRel

        props: dict = {}
        required: list = []

        # Mixin fields are grouped into sub-objects instead of being emitted flat.
        mixin_groups = _get_mixin_groups(model_class)
        mixin_field_names: frozenset[str] = frozenset(
            name for _, _, names in mixin_groups for name in names
        )

        for field in model_class._meta.get_fields():
            prop = {}

            # ── reverse relations (rule 44: parent includes array, child skips back-FK)
            if isinstance(field, (ManyToOneRel, ManyToManyRel)):
                rn = getattr(field, "related_name", None)
                # if not rn or rn.endswith("+"):
                #     continue
                # field.related_model == the model that declares the FK to us
                sub_model = field.related_model
                # if self._is_skipped_fk_target(model_class=sub_model):
                #     continue
                ref = self._ensure_def(model_class=sub_model, parent_model=model_class)
                sub_meta = sub_model._meta
                prop: dict = {
                    "type": "array",
                    "title": str(sub_meta.verbose_name_plural or sub_meta.verbose_name).capitalize(),
                    "items": {"$ref": ref},
                }
                desc = _td_attr(sub_model, "description", "")
                if desc:
                    prop["description"] = desc
                props[rn] = prop
                continue

            if isinstance(field, OneToOneRel):
                rn = getattr(field, "related_name", None)
                # if not rn or rn.endswith("+"):
                #     continue
                sub_model = field.related_model
                # if self._is_skipped_fk_target(model_class=sub_model):
                #     continue
                ref = self._ensure_def(model_class=sub_model, parent_model=model_class)
                props[rn] = {"$ref": ref}
                continue

            # ── skip non-concrete fields (no DB column)
            if not hasattr(field, "column"):
                continue

            # ── rule 44: skip the FK that points back to the parent model
            # if parent_model and isinstance(field, (ForeignKey, OneToOneField)):
            #     if field.related_model is parent_model:
            #         continue

            if field.name in mixin_field_names:
                prop["readOnly"] = True  # rule 45: mixin fields are readOnly in root model

            # ── skip meta models; they are emitted in simplified form when referenced, but not expanded inline
            is_foreign_key = isinstance(field, ForeignKey)
            if is_foreign_key and field.related_model._meta.object_name in self.models:
                continue
            if is_foreign_key and self._is_skipped_fk_target(model_class=field.related_model):
                continue

            prop = self._field_to_property(field=field)
            if prop is None:
                continue

            props[field.name] = prop
            if _is_required(field):
                required.append(field.name)

        return props, required

    # ── field → property ──────────────────────────────────────────────────────

    def _field_to_property(self, field) -> dict | None:
        """Convert a single Django field to a JSON Schema property dict."""
        from django.db.models.fields.related import ForeignKey, ManyToManyField, OneToOneField

        field_type = type(field).__name__
        field_name = field.name
        nullable = getattr(field, "null", False)

        prop: dict = {}

        # title (rule 24)
        if title := _verbose_title(field):
            prop["title"] = title

        # description from config.doc_short (rule 23)
        if doc := _config_attr(field, "doc_short"):
            prop["description"] = doc

        # readOnly (rules 26-28)
        readonly = (
            field_name.startswith("c_")  # rule 27: calculated fields
            or getattr(field, "primary_key", False)  # rule 26
            or field_type in _AUTO_PK_TYPES  # rule 26
            or not getattr(field, "editable", True)  # rule 28
            or getattr(field, "auto_now", False)  # rule 28
            or getattr(field, "auto_now_add", False)  # rule 28
        )
        if readonly:
            prop["readOnly"] = True

        # ── FK / OneToOne (rules 20, 21, 25) ──────────────────────────────────
        if isinstance(field, (ForeignKey, OneToOneField)):
            ref = self._ensure_def(model_class=field.related_model)
            if nullable:
                prop["anyOf"] = [{"$ref": ref}, {"type": "null"}]
            else:
                prop["$ref"] = ref
            return prop

        # ── ManyToMany (rule 22) ───────────────────────────────────────────────
        if isinstance(field, ManyToManyField):
            ref = self._ensure_def(model_class=field.related_model)
            prop["type"] = "array"
            prop["items"] = {"$ref": ref}
            return prop

        # ── GIS geometry ──────────────────────────────────────────────────────
        if field_type in _GIS_FIELDS:
            prop["type"] = ["object", "null"] if nullable else "object"
            if not prop.get("description"):
                prop["description"] = "GeoJSON geometrie object."
            return prop

        # ── ArrayField (rule 36) ──────────────────────────────────────────────
        if field_type == "ArrayField":
            prop["type"] = "array"
            base = getattr(field, "base_field", None)
            if base:
                inner = self._field_to_property(field=base)
                if inner:
                    prop["items"] = inner
            return prop

        # ── JSONField (rule 39) ───────────────────────────────────────────────
        if field_type == "JSONField":
            prop["type"] = ["object", "null"] if nullable else "object"
            prop["additionalProperties"] = True
            return prop

        # ── Scalar fields ─────────────────────────────────────────────────────
        json_type = _TYPE_MAP.get(field_type)
        if json_type is None:
            # Walk MRO to handle custom subclasses (e.g. TextStringField → CharField)
            for base_cls in type(field).__mro__[1:]:
                json_type = _TYPE_MAP.get(base_cls.__name__)
                if json_type:
                    break
            else:
                json_type = "string"  # safe fallback

        prop["type"] = [json_type, "null"] if nullable else json_type

        if fmt := _FORMAT_MAP.get(field_type):
            prop["format"] = fmt

        # maxLength for string fields (rule 33)
        if json_type == "string":
            if ml := getattr(field, "max_length", None):
                prop["maxLength"] = ml

        # minimum for positive integer fields (rule 32)
        if json_type in ("integer", "number") and "Positive" in field_type:
            prop["minimum"] = 0

        return prop
    
    def _is_skipped_fk_target(self, model_class) -> bool:
        """Return True if *model_class* not in models"""
        return model_class._meta.object_name not in self.models

# ── Mixin grouping ────────────────────────────────────────────────────────────

# Each entry: (mixin_import_path, mixin_name, property_name, title)
# Ordered from most specific to least specific so issubclass short-circuits correctly.
_MIXIN_GROUP_DEFS = [
    (
        "rgs_django_utils.database.base_models.modification_mixin",
        ("ModificationSourceMixin", "ModificationMetaMixin"),
        "modification_source",
        "Bron metadata",
    ),
    (
        "rgs_django_utils.database.base_models.validity_period",
        ("ValidityPeriodMixin",),
        "validity_period",
        "Geldigheidsperiode",
    ),
]


def _get_mixin_groups(model_class) -> list[tuple[str, str, frozenset[str]]]:
    """Return [(property_name, title, field_names), …] for each mixin that *model_class* inherits."""
    groups: list[tuple[str, str, frozenset[str]]] = []
    for module_path, class_names, prop_name, title in _MIXIN_GROUP_DEFS:
        try:
            import importlib

            mod = importlib.import_module(module_path)
            mixin_classes = [getattr(mod, n) for n in class_names if hasattr(mod, n)]
        except ImportError:
            continue

        primary = mixin_classes[0]
        if not (isinstance(model_class, type) and issubclass(model_class, primary)):
            continue

        field_names: set[str] = set()
        for cls in mixin_classes:
            for f in cls._meta.local_fields:
                field_names.add(f.name)
            for f in cls._meta.local_many_to_many:
                field_names.add(f.name)
        groups.append((prop_name, title, frozenset(field_names)))

    return groups



# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _enum_oneofs(model_class) -> list[dict]:
    """Return [{const, title}, …] from a BaseEnum model's default_records()."""
    try:
        records = model_class.default_records()
        fields = records["fields"]
        data = records["data"]
        id_idx = fields.index("id")
        name_idx = fields.index("name")
        return [{"const": row[id_idx], "title": row[name_idx]} for row in data]
    except Exception:
        return []


def _config_attr(field, attr: str, default=None):
    """Read *attr* from a field's .config object (rgs_django_utils Config)."""
    config = getattr(field, "config", None)
    return getattr(config, attr, default) if config else default


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