import typing
from abc import ABC
from typing import TYPE_CHECKING, Any, Generic, List, Literal, TypeVar

import numpy as np
import pandas as pd
from django.contrib.gis.db import models as base_models

from django.contrib.gis.db.models import *  # NOQA isort:skip
import geopandas as gpd
from django.contrib.gis.db.models import __all__ as base_all
from django.contrib.postgres import fields as pg_fields
from geoalchemy2 import types as geo_types
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from sqlalchemy import types as sql_types
from sqlalchemy.dialects import postgresql

__all__ = base_all + [
    "ArrayField",
    "TableSection",
    "FieldSection",
    "Calculation",
    "Config",
    "Permission",
    "Validation",
]

from sqlalchemy.sql.type_api import TypeEngineMixin

from rgs_django_utils.database.custom_fields import TextStringField

# for type
if TYPE_CHECKING:
    from rgs_django_utils.models import EnumModuleBase


##  postgres see https://pgxn.org/dist/pg_uuidv7/


# no_decimals


# BigInteger
# BinaryField
# BooleanField
# CharField
# DateField
# DateTimeField
# DecimalField (use float instead)
# EmailField
# FileField
# FilePathField
# FloatField
# ImageField
# IntegerField
# JSONField
# SmallIntegerField
# TextField

# UrlField
# UUIDField (uuid7?)

# ForeignKey
# OneToOneField

# is_relation
# many_to_many
# one_to_one
# one_to_many
# many_to_one
# related_model


# GeneratedField (for Hasura)


# def default_values
# hasura_permissions:
# - relations_to_authorization (project, organization, user)
# - which roles has select, update, insert, delete rights


class TableType:
    ENUM = "enum"
    EXTENDED_ENUM = "extended_enum"


class ExtendedModelMeta(object):
    pass

    # db_table
    # verbose_name
    # description
    # extended_documentation
    # development_notes
    # is_enum
    #


section_register = {}


#### FIELD CONFIGURATION ####


class TableSection(object):
    """Section for Tables/ models."""

    def __init__(
        self,
        id_: str,
        name: str = None,
        order: int = 0,
        description: str = None,
    ):
        self.id = id_
        self.name = name
        self.order = order
        self.description = description

        if id_ in section_register:
            raise ValueError(f"Section id {id_} already exists")

        section_register[id_] = self


class FieldSection(object):
    """Section for field."""

    def __init__(
        self,
        id_: str,
        name: str = None,
        order: int = 0,
        description: str = None,
    ):
        self.id = id_
        self.name = name
        self.order = order
        self.description = description
        self.table = None


class Calculation(object):
    """Default values and calculation config for field."""

    def __init__(
        self,
        obj: str,
        name: str,
        nr: int = None,
    ):
        self.obj = obj
        self.name = name
        self.nr = nr

    pass


T = TypeVar("T")

type TableAction = Literal["select", "update", "insert", "delete"]
type FieldActions = Literal["---", "-s-", "i--", "-su", "isu", "is-"]
"""Field Actions.

Can be:
- '---': No access
- '-s-': Select
- '-su': Select, Update
- 'isu': Insert, Select, Update
- 'is-': Insert, Select (for example poid)
"""


# todo: move this specific implementation to another file
class FieldPermissionType(typing.TypedDict, total=False):
    public: FieldActions
    module_auth: FieldActions
    module_auth2: FieldActions
    auth: FieldActions
    user_self: FieldActions
    project_rol: FieldActions
    project_read: FieldActions
    proj_read: FieldActions
    proj_cli: FieldActions
    proj_con: FieldActions
    proj_ext: FieldActions
    project_edit: FieldActions
    proj_fw: FieldActions
    proj_coll: FieldActions
    proj_man: FieldActions
    org_mem: FieldActions
    org_uman: FieldActions
    org_adm: FieldActions
    sys_adm: FieldActions
    dev: FieldActions
    dev_man: FieldActions


type Roles = typing.Literal[
    "public",
    "module_auth",
    "module_auth_2",
    "user_self",
    "project_rol",
    "project_read",
    "project_edit",
    "proj_read",
    "proj_cli",
    "proj_con",
    "proj_ext",
    "project_edit",
    "proj_fw",
    "proj_coll",
    "proj_man",
    "org_mem",
    "org_uman",
    "org_adm",
    "sys_adm",
    "dev",
    "dev_man",
]


class Perm(Generic[T], ABC):
    """Abstract permission."""

    empty: T

    def __getitem__(
        self,
        key: Roles,
    ) -> T:
        try:
            return self._dict[key]
        except KeyError:
            pass
        try:
            # if key is not found, try public
            return self._dict["public"]
        except KeyError:
            # if public is not found, return empty
            return self.empty

    def items(self):
        return self._dict.items()

    def __repr__(self):
        return self._dict.__repr__()


class FPerm(Perm[FieldPermissionType]):
    """Field Permission."""

    def __init__(self, public: FieldActions = "---", **kwargs: typing.Unpack[FieldPermissionType]):
        """Initialize Field permission.

        Args:
            public (FieldActions): Optional. Can be passed as positional argument or additional argument. Default is '---'.
            args: Optional. Can be passed as additional argument. Default is '---'.
            kwargs: Optional. Can be passed as additional argument. Default is empty.

        Raises:
            ValueError: If more than one positional argument is passed.

        Examples:
            >>> FPerm()
            FPerm()
            >>> FPerm('-s-')
            FPerm(public='-s-',)
            >>> FPerm(module_auth='isu')
            FPerm(module_auth='isu',)
            >>> FPerm('-s-', module_auth='isu')
            FPerm(public='-s-', module_auth='isu',)
            >>> FPerm(public='-s-', user_self='isu')
            FPerm(public='-s-', user_self='isu',)
        """
        super().__init__(public, **kwargs)
        self.config = kwargs
        if public:
            self.config["public"] = public
        # todo: validate

        # super().__init__(*args, **kwargs)

    empty = "---"


type PresetActions = Literal["--", "i-", "-u", "iu"]
type PresetArgument = tuple[PresetActions, str] | tuple[tuple[Literal["i-"], str], tuple[Literal["-u"], str]]


class FPresets(Perm[dict[Roles, PresetArgument]]):
    """Field Presets."""

    def __init__(self, public: PresetArgument = None, **kwargs: typing.Unpack[typing.Mapping[Roles, PresetArgument]]):
        """Initialize Field Presets.


        Args:
            public (PresetArgument): Optional. Can be passed as positional argument or additional argument. Default is ('--',).
            args: Optional. Can be passed as additional argument. Default is ('--',).
            kwargs: Optional. Can be passed as additional argument. Default is empty.

        Raises:
            ValueError: If more than one positional argument is passed.

        Examples:
            >>> FPresets()
            FPresets()
            >>> FPresets('i-', 'value')
            FPresets(public=('i-', 'value'))
            >>> FPresets(module_auth=('i-', 'value'))
            FPresets(module_auth=('i-', 'value'))
            >>> FPresets('i-', 'value', module_auth=('i-', 'value2'))
            FPresets(public=('i-', 'value'), module_auth=('i-', 'value2'))
            >>> FPresets(('i-', 'value'), ('-u', 'value2'))
            FPresets(public=(('i-', 'value'), ('-u', 'value2')))
            >>> FPresets(public=('iu', 'value'), user_self=(('i', 'value'), ('-u', 'value2')))
            FPresets(public=('iu', 'value'), user_self=(('i', 'value'), ('-u', 'value2')))
        """
        super().__init__(public, **kwargs)
        self.config = kwargs
        if public:
            self.config["public"] = public

        for key, value in self.config.items():
            if not isinstance(value, tuple):
                raise ValueError(f"Preset for {key} should be a tuple, got {type(value)}")

    empty = ("--",)


class TPerm(Perm[dict[TableAction, dict]]):
    """Table Permission."""

    def __init__(
        self,
        public=None,
        *args,
        **kwargs: typing.Dict[TableAction, typing.Dict[typing.Any, typing.Any]],
    ):
        """Initialize Table permission."""
        self.config = kwargs
        if public:
            self.config["public"] = public

        for key, value in self.config.items():
            if not isinstance(value, dict):
                raise ValueError(f"Permission for {key} should be a dict, got {type(value)}")
        # todo: validate keys..


class Validation(object):
    """Validation config for field."""

    # relevant django keys:
    #   - unique
    #   - unique_for_date
    #   - null
    #   - blank
    #   - choices
    #   - max_length

    # extra:
    #   - min_length
    #   - configurable per organization/ project?
    #   - min_value
    #   - max_value
    #   - max_diff relative to another field


class Model(base_models.Model):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        abstract = True


class Config:
    def __init__(
        self,
        # verbose_name: str = None,
        modules: typing.Iterable[typing.AnyStr | "EnumModuleBase"] = None,
        section: FieldSection = None,
        doc_unit: str = None,
        doc_short: str = None,
        doc_full: str = None,
        doc_constraint: str = None,
        doc_development: str = None,
        calculated_by: Calculation = None,
        calculation_input_for: List[Calculation] = None,
        default_function: Any = None,
        validation: Validation = None,
        permissions: FPerm = None,
        ignore_for_history: bool = False,
        precision: int = None,
        dbf_name: str = None,
        import_mode: str = "all",  # "EnumImportModeEnum"
        export: bool = True,
        presets: FPresets = None,
    ):
        self.modules = modules
        self.section = section
        self.doc_unit = doc_unit
        self.doc_short = doc_short
        self.doc_full = doc_full
        self.doc_constraint = doc_constraint
        self.doc_development = doc_development
        self.calculated_by = calculated_by
        self.calculation_input_for = calculation_input_for
        self.default_function = default_function
        self.validation = validation
        self.permissions = permissions
        self.ignore_for_history = ignore_for_history
        self.precision = precision
        if dbf_name is not None and len(dbf_name) > 10:
            raise ValueError("dbfname should be max 10 characters")
        self.dbf_name = dbf_name
        self.import_mode = import_mode
        self.export = export
        self.presets = presets


class FieldConfig:
    def _init_extras(
        self,
        config: Config = None,
        pd_type: Any = None,
        sql_alchemy_type: TypeEngineMixin = None,
        pd_type_func: typing.Callable = None,
    ):
        self.r_config = config

        if pd_type is not None:
            self.pd_type = pd_type
        if not hasattr(self, "pd_type_func"):
            self.pd_type_func = pd_type_func or (lambda x: x.astype(self.pd_type))
        if sql_alchemy_type is not None:
            self.sql_alchemy_type = sql_alchemy_type

        # verbose_name
        # db_column
        # null
        # blank


class CharField(base_models.CharField, FieldConfig):
    pd_type = pd.StringDtype()

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        # dtype = "U" if self.max_length is None else f"U{self.max_length}"
        # dtype = np.dtype(dtype)
        self._init_extras(config, sql_alchemy_type=sql_types.String(length=self.max_length))


class TextField(base_models.TextField, FieldConfig):
    pd_type = pd.StringDtype()
    sql_alchemy_type = sql_types.Text()

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config)


class TextStringField(TextStringField, FieldConfig):
    """text field with string admin in django admin."""

    pd_type = pd.StringDtype()
    sql_alchemy_type = sql_types.Text()

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config)


class EmailField(base_models.EmailField, FieldConfig):
    pd_type = pd.StringDtype()

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        # dtype = "U" if self.max_length is None else f"U{self.max_length}"
        # np.dtype(dtype)
        self._init_extras(config, sql_alchemy_type=sql_types.String(length=self.max_length))


class FloatField(base_models.FloatField, FieldConfig):
    pd_type = pd.Float64Dtype()  # float32?
    sql_alchemy_type = sql_types.Float(precision=3)

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config, sql_alchemy_type=sql_types.Float(precision=getattr(self, "decimal_places", 3)))


class IntegerField(base_models.IntegerField, FieldConfig):
    pd_type = pd.Int32Dtype()
    sql_alchemy_type = sql_types.Integer()

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config)


class BigIntegerField(base_models.BigIntegerField, FieldConfig):
    pd_type = pd.Int64Dtype()
    sql_alchemy_type = sql_types.BigInteger()

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config)


class AutoField(base_models.AutoField, FieldConfig):
    pd_type = pd.Int32Dtype()
    sql_alchemy_type = sql_types.Integer()

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config)


class BigAutoField(base_models.BigAutoField, FieldConfig):
    pd_type = pd.Int64Dtype()
    sql_alchemy_type = sql_types.BigInteger()

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config)


class ForeignKey(base_models.ForeignKey, FieldConfig):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)

        self._init_extras(config)
        # todo...

    @property
    def pd_type(self):
        field_type = self.foreign_related_fields[0].__class__.__name__
        return type_mapping[field_type]().pd_type

    def pd_type_func(self, value):
        return value.astype(self.pd_type)

    @property
    def sql_alchemy_type(self):
        field_type = self.foreign_related_fields[0].__class__.__name__
        return type_mapping[field_type]().sql_alchemy_type


class OneToOneField(base_models.OneToOneField, FieldConfig):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)

        self._init_extras(config)
        # todo...


class UUIDField(base_models.UUIDField, FieldConfig):
    pd_type = pd.StringDtype  # klopt dit of is het een Object?
    sql_alchemy_type = sql_types.UUID()

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config)


class BooleanField(base_models.BooleanField, FieldConfig):
    pd_type = pd.BooleanDtype()
    sql_alchemy_type = sql_types.Boolean()

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config)


class JSONField(base_models.JSONField, FieldConfig):
    pd_type = np.dtype("O")
    sql_alchemy_type = sql_types.JSON(none_as_null=True)

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config)


class ArrayField(pg_fields.ArrayField, FieldConfig):
    pd_type = np.dtype("O")  # klopt dit, niet beter een array?

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)

        # nested array not needed is:
        # https://stackoverflow.com/questions/9729175/postgresql-multidimensional-arrays-in-sqlalchemy

        base_type = self.base_field.sql_alchemy_type
        while isinstance(base_type, postgresql.ARRAY):
            base_type = base_type.item_type

        self._init_extras(
            config,
            np.dtype("O"),
            postgresql.ARRAY(
                base_type,
            ),
        )


class DateTimeField(base_models.DateTimeField, FieldConfig):
    # pandas serie of datetime64 - timezone aware?!
    pd_type = pd.DatetimeTZDtype(tz="UTC")  # timezone aware datetime
    # np.dtype("datetime64[ms]"),

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config, sql_alchemy_type=sql_types.DateTime(timezone=True))

    def pd_type_func(self, serie):
        return pd.to_datetime(serie)


class DateField(base_models.DateField, FieldConfig):
    # pandas object with python datetime.date

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(config, np.dtype("datetime64[D]"), sql_types.Date())

    def pd_type_func(self, serie):
        return pd.to_datetime(serie).dt.date


if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry, BaseMultipartGeometry


def _gpd_make_single_geometry(
    gs: gpd.GeoSeries,
    shapely_single_geom: typing.Type["BaseGeometry"],
    shapely_multi_geom: typing.Type["BaseMultipartGeometry"],
):
    geom_types = gs.geom_type.dropna().unique()

    if not np.isin(geom_types, [shapely_single_geom.__name__, shapely_multi_geom.__name__]).all():
        raise ValueError(
            "Geometry type should be {} or {}. Found {}".format(
                shapely_single_geom.__name__, shapely_multi_geom.__name__, ", ".join(geom_types.item())
            )
        )

    # if some rows has multigeometry, check if geometry has one geometry
    if shapely_multi_geom.geom_type in geom_types:
        # for all rows where geometry is point, transform to multipoint
        # transform the multi geometries to single geometries
        gs = gs.explode()
        # get nr of lines which are duplicated (these are the lines with multiple points)
        duplicated = gs.duplicated().sum()[0].item()
        if duplicated > 0:
            raise ValueError(f"Point field contains {duplicated} MultiPoints geometries with multiple points")
    return gs


def _gpd_make_multi_geometry(
    gs: gpd.GeoSeries,
    shapely_single_geom: typing.Type["BaseGeometry"],
    shapely_multi_geom: typing.Type["BaseMultipartGeometry"],
):
    geom_types = gs.geom_type.dropna().drop_duplicates()

    single_geom_type = shapely_single_geom().geom_type
    multi_geom_type = shapely_multi_geom().geom_type

    if not geom_types.isin([single_geom_type, multi_geom_type]).all():
        raise ValueError(
            "Geometry type should be {} or {}. Found {}".format(
                shapely_single_geom.geom_type, shapely_multi_geom.geom_type, ", ".join(geom_types.item())
            )
        )

    # if some rows has single geometry, transform them to multi geometry
    if geom_types.isin([single_geom_type]).any():
        # for all rows where geometry is point, transform to multipoint
        # transform the points to multipoints
        gs[gs.geom_type == single_geom_type] = gs[gs.geom_type == single_geom_type].apply(
            lambda x: shapely_multi_geom([x])
        )
    return gs


class PointField(base_models.PointField, FieldConfig):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(
            config,
            "geometry",
            geo_types.Geometry(geometry_type="POINT", srid=self.srid),
        )

    def pd_type_func(self, serie):
        gs = gpd.GeoSeries.from_wkb(serie, crs=self.srid)
        return _gpd_make_single_geometry(gs, Point, MultiPoint)


class MultiPointField(base_models.MultiPointField, FieldConfig):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(
            config,
            "geometry",
            geo_types.Geometry(geometry_type="MULTIPOINT", srid=self.srid),
        )

    def pd_type_func(self, serie):
        gs = gpd.GeoSeries.from_wkb(serie, crs=self.srid)
        return _gpd_make_multi_geometry(gs, Point, MultiPoint)


class LineStringField(base_models.LineStringField, FieldConfig):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(
            config,
            "geometry",
            geo_types.Geometry(geometry_type="LINESTRING", srid=self.srid),
        )

    def pd_type_func(self, serie):
        gs = gpd.GeoSeries.from_wkb(serie, crs=self.srid)
        return _gpd_make_single_geometry(gs, LineString, MultiLineString)


class MultiLineStringField(base_models.MultiLineStringField, FieldConfig):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(
            config,
            "geometry",
            geo_types.Geometry(geometry_type="MULTILINESTRING", srid=self.srid),
        )

    def pd_type_func(self, serie):
        gs = gpd.GeoSeries.from_wkb(serie, crs=self.srid)
        return _gpd_make_multi_geometry(gs, LineString, MultiLineString)


class PolygonField(base_models.MultiPolygonField, FieldConfig):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(
            config,
            "geometry",
            geo_types.Geometry(geometry_type="POLYGON", srid=self.srid),
        )

    def pd_type_func(self, serie):
        gs = gpd.GeoSeries(serie, crs=self.srid)
        return _gpd_make_single_geometry(gs, Polygon, MultiPolygon)


class MultiPolygonField(base_models.MultiPolygonField, FieldConfig):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        self._init_extras(
            config,
            "geometry",
            geo_types.Geometry(geometry_type="MULTIPOLYGON", srid=self.srid),
        )

    def pd_type_func(self, serie):
        gs = gpd.GeoSeries(serie, crs=self.srid)
        return _gpd_make_multi_geometry(gs, Polygon, MultiPolygon)


class FileField(base_models.FileField, FieldConfig):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        dtype = "U" if self.max_length is None else f"U{self.max_length}"
        self._init_extras(config, np.dtype(dtype), sql_types.String(length=self.max_length))


class ImageField(base_models.ImageField, FieldConfig):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None)
        super().__init__(*args, **kwargs)
        dtype = "U" if self.max_length is None else f"U{self.max_length}"
        self._init_extras(config, np.dtype(dtype), sql_types.String(length=self.max_length))


type_mapping = {
    BigAutoField.__name__: BigAutoField,
    AutoField.__name__: AutoField,
    UUIDField.__name__: UUIDField,
    BigIntegerField.__name__: BigIntegerField,
    BooleanField.__name__: BooleanField,
    CharField.__name__: CharField,
    DateField.__name__: DateField,
    DateTimeField.__name__: DateTimeField,
    TextStringField.__name__: TextStringField,
    TextField.__name__: TextField,
    # todo: etc...
}
