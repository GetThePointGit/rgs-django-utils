from copy import copy, deepcopy
from enum import Enum

from django.db.models.base import ModelBase

from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.dj_extended_models import FPerm, TableType


class BaseEnumMetaClass(ModelBase):
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
    """Base class for enums, according to the Hasura standard."""

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
        """Create an Enum class from the django definition.

        Checks on all uppercase variables.
        Enums are used for Fast API models.
        :return:
        """
        return SerializableEnum(cls.__name__, {key: getattr(cls, key) for key in dir(cls) if key.isupper()})

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class SerializableEnum(Enum):
    """An Enum that serializes to its value when cast to a string.

    This class overrides the `__str__` method to return the member's value
    instead of its name (e.g., 'a' instead of 'X.A'). This is particularly
    useful for creating API models, such as in FastAPI, where the enum
    value is desired in the response.

    Example:
        >>> from enum import Enum
        >>>
        >>> # A standard Enum's string representation includes the class name.
        >>> X = Enum("X", {"A": "a", "B": "b"})
        >>> str(X.A)
        'X.A'
        >>>
        >>> # A SerializableEnum's string representation is just the value.
        >>> Y = SerializableEnum("Y", {"A": "a", "B": "b"})
        >>> str(Y.A)
        'a'
    """

    def __str__(self):
        return self.value

    def to_dict(self):
        return {"id": self.name, "name": self.value}


class BaseEnumExtendedMetaClass(BaseEnumMetaClass):
    """Metaclass for BaseEnumExtended."""

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
    """Creates enum table(id, name) and table with extended fields (id, name, ... on name db_table_ext). So
    enum could be used as hasura enum, and extra information is accessible through the 'extended' attribute.

    Extended table has Meta.db_table = Meta.db_table + '_ext'
    from the Modelclass (BaseEnum), the extended class is accessible via the 'extended' field attribute
    extended class is accessible via the ExtendedClass attribute on the BaseEnum class.

    """

    ExtendedClass = None
    is_extended = None

    class Meta:
        abstract = True
