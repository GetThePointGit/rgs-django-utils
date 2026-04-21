from copy import copy
from enum import Enum

from django.db.models.base import ModelBase

from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.dj_extended_models import FPerm, TableType


class BaseEnumMetaClass(ModelBase):
    """Metaclass that stamps ``TableDescription.table_type = ENUM`` on subclasses.

    Ensures every ``BaseEnum`` subclass carries the enum table-type marker
    without each subclass having to repeat the boilerplate. Creates a
    default ``TableDescription`` class when the subclass does not declare
    one.
    """

    def __new__(cls, name, bases, attrs, **kwargs):
        new_cls = super().__new__(cls, name, bases, attrs)
        if hasattr(new_cls, "TableDescription"):
            setattr(new_cls.TableDescription, "table_type", TableType.ENUM)
        else:
            setattr(
                new_cls,
                "TableDescription",
                type("TableDescription", (), {"table_type": TableType.ENUM}),
            )

        return new_cls


class BaseEnum(models.Model, metaclass=BaseEnumMetaClass):
    """Abstract parent for enum-style tables compatible with Hasura enums.

    Provides the standard ``(id TEXT PRIMARY KEY, name TEXT)`` pair,
    public-select permissions and a :meth:`default_records` hook that
    subclasses override to seed their rows. Use :class:`BaseEnumExtended`
    when additional (non-Hasura-enum) columns are required.

    Examples
    --------
    >>> class Severity(BaseEnum):                    # doctest: +SKIP
    ...     class Meta:
    ...         db_table = "enum_severity"
    ...
    ...     @classmethod
    ...     def default_records(cls):
    ...         return {
    ...             "fields": ["id", "name"],
    ...             "data": [("low", "Low"), ("high", "High")],
    ...         }
    """

    id = models.TextStringField(
        "code",
        primary_key=True,
        config=models.Config(
            doc_short="code/ identificatie van de enum",
            doc_full="Mag niet beginnen met een cijfer. Gebruik underscores in plaats van spaties.",
            permissions=FPerm("-s-"),
        ),
    )
    name = models.TextStringField(
        "name",
        config=models.Config(
            doc_short="naam van de enum",
            permissions=FPerm("-s-"),
        ),
    )

    class Meta:
        abstract = True

    class TableDescription:
        description = "Base class for enums. Overwrite this TableDescription"
        table_type = TableType.ENUM
        modules = "*"

    @classmethod
    def get_permissions(cls):
        no_filt = {}

        return models.TPerm(
            public={
                "select": no_filt,
            },
        )

    def __str__(self):
        return f"{self.name} ({self.id})"

    @classmethod
    def choices(cls):
        return [(r.get("id"), r.get("name")) for r in cls.default_records().get("data", [])]

    @classmethod
    def default_records(cls):
        raise NotImplementedError(f"Please implement default_records for this enum {cls.__name__}")

    @classmethod
    def get_enum_class(cls):
        """Build a :class:`SerializableEnum` from the model's uppercase attributes.

        Collects every class attribute whose name is all-uppercase (by
        convention the "enum value" constants declared on the model) and
        wraps them in a :class:`SerializableEnum`. Useful for generating
        pydantic / ninja schemas whose values should serialize as the raw
        enum string.

        Returns
        -------
        SerializableEnum
            A dynamically-created enum class named after the model.
        """
        return SerializableEnum(cls.__name__, {key: getattr(cls, key) for key in dir(cls) if key.isupper()})

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class SerializableEnum(Enum):
    """``Enum`` whose ``str(member)`` returns the member's value.

    Overrides ``__str__`` so the member serialises as ``'a'`` instead of
    ``'X.A'``. Handy for FastAPI / Ninja response models where the raw
    value is the desired wire format.

    Examples
    --------
    Standard ``Enum`` includes the class name in its string form:

    >>> from enum import Enum
    >>> X = Enum("X", {"A": "a", "B": "b"})
    >>> str(X.A)
    'X.A'

    :class:`SerializableEnum` drops it:

    >>> Y = SerializableEnum("Y", {"A": "a", "B": "b"})
    >>> str(Y.A)
    'a'
    """

    def __str__(self):
        return self.value

    def to_dict(self):
        return {"id": self.name, "name": self.value}


class BaseEnumExtendedMetaClass(BaseEnumMetaClass):
    """Metaclass that materialises :class:`BaseEnumExtended` as two tables.

    For a subclass ``Foo`` this metaclass produces:

    * ``Foo`` — the base enum (``id``, ``name``) with Hasura-enum type.
    * ``FooExtended`` — sibling table ``foo_ext`` with the full field set
      linked via ``OneToOneField`` on ``id``.

    Both classes reference each other through ``Foo.ExtendedClass`` and
    ``extended.foo`` so consumers can pick the level of detail they need.
    """

    def __new__(cls, name, bases, attrs, **kwargs):
        super_new = super().__new__

        if "Meta" in attrs and getattr(attrs["Meta"], "abstract", False):
            # skip abstract model classes
            return super_new(cls, name, bases, attrs, **kwargs)

        # create base enum
        base_enum = copy(bases)
        attr_enum = {k: v for k, v in attrs.items() if not isinstance(v, models.Field)}

        td = attr_enum.get("TableDescription", None)
        table_description = type("TableDescription", object.__bases__, dict(td.__dict__) if td else {})
        setattr(table_description, "table_type", TableType.ENUM)
        attr_enum["TableDescription"] = table_description
        base_enum = super_new(cls, name, base_enum, attr_enum, **kwargs)

        # create extended enum
        attr_extended = copy(attrs)
        # Meta.db_table
        attr_extended["Meta"] = copy(attr_extended.get("Meta", object))
        setattr(attr_extended["Meta"], "db_table", getattr(attr_extended["Meta"], "db_table") + "_ext")
        # TableDescription.table_type
        attr_extended["TableDescription"] = copy(
            attr_extended.get("TableDescription", type("TableDescription", object.__bases__, {}))
        )
        setattr(attr_extended["TableDescription"], "table_type", TableType.EXTENDED_ENUM)
        # tablename
        extended_name = name + "Extended"
        attr_extended["__qualname__"] += "Extended"

        attr_extended["id"] = models.OneToOneField(
            base_enum,
            related_name="extended",
            on_delete=models.CASCADE,
            primary_key=True,
            db_column="id",
            config=models.Config(
                doc_short="id van de base enum",
                doc_full="id van de base enum",
                permissions=FPerm("-s-", user_self="-s-"),
            ),
        )

        extended_enum = super_new(cls, extended_name, bases, attr_extended, **kwargs)

        # reapply the TableDescription table_type
        setattr(extended_enum.TableDescription, "table_type", TableType.EXTENDED_ENUM)

        setattr(base_enum, "ExtendedClass", extended_enum)

        setattr(base_enum, "is_extended", False)
        setattr(extended_enum, "is_extended", True)

        return base_enum


class BaseEnumExtended(BaseEnum, metaclass=BaseEnumExtendedMetaClass):
    """Abstract parent for enum tables that also need non-enum metadata columns.

    Subclasses are split at metaclass time into two physical tables:

    * the enum table (``<db_table>``) exposing only ``id`` and ``name``,
      usable as a Hasura enum.
    * the extended table (``<db_table>_ext``) carrying the other fields
      declared on the subclass and linked to the enum table by a
      ``OneToOneField`` on ``id``.

    Access patterns
    ---------------
    * From the base class: ``foo_instance.extended`` — returns the
      matching extended row (or raises ``DoesNotExist``).
    * From code that needs the extended model class itself:
      ``Foo.ExtendedClass`` — the dynamically-generated
      ``FooExtended`` class.
    """

    ExtendedClass = None
    is_extended = None

    class Meta:
        abstract = True
