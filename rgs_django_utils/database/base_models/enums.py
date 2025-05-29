from copy import copy, deepcopy
from enum import Enum

from django.db.models.base import ModelBase
from rgs_django_utils.database import dj_extended_models as models
from rgs_django_utils.database.dj_extended_models import FPerm, TableType


class BaseEnum(models.Model):
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
        description = "Base class for enums. Overwrite this description"
        is_enum = True

        modules = "*"

    @classmethod
    def permissions(cls):
        no_filt = {}

        return models.TPerm(
            public={
                "select": no_filt,
            },
        )

    def __str__(self):
        return self.id

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
    """Overwrite __str__ to return the value instead of the name. This is used for API models.

    Args:
        Enum (_type_): Enum class that serializes the value instead of the name.

    Example:
    ```python
    X = Enum("X", {"A": "a", "B": "b"})
    assert str(X.A) == "X.A"
    Y = SerializableEnum("X", {"A": "a", "B": "b"})
    assert str(Y.A) == "a"
    ```
    """

    def __str__(self):
        return self.value

    def to_dict(self):
        return {"id": self.name, "name": self.value}


class BaseEnumExtendedBaseModel(ModelBase):
    pass

    def __new__(cls, name, bases, attrs, **kwargs):
        super_new = super().__new__

        if "Meta" in attrs and getattr(attrs["Meta"], "abstract", False):
            return super_new(cls, name, bases, attrs, **kwargs)

        base_enum = copy(bases)
        attr_enum = {k: v for k, v in attrs.items() if not isinstance(v, models.Field)}
        table_description = type("TableDescription", object.__bases__, dict(attr_enum["TableDescription"].__dict__))
        setattr(table_description, "table_type", TableType.ENUM)
        attr_enum["TableDescription"] = table_description
        base_enum = super_new(cls, name, base_enum, attr_enum, **kwargs)

        attr_extended = copy(attrs)
        # Meta.db_table
        attr_extended["Meta"] = copy(attr_extended.get("Meta", object))
        setattr(attr_extended["Meta"], "db_table", getattr(attr_extended["Meta"], "db_table") + "_ext")
        # TableDescription.table_type
        attr_extended["TableDescription"] = copy(attr_extended.get("TableDescription", object))
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

        setattr(base_enum, "extended", extended_enum)

        setattr(base_enum, "is_extended", False)
        setattr(extended_enum, "is_extended", True)

        return base_enum


class BaseEnumExtended(BaseEnum, metaclass=BaseEnumExtendedBaseModel):
    """Creates enum table(id, name) and table with extended fields (id, name, ...).

    Extended table has db_table = db_table + '_ext'
    from the Modelclass (=enum), the extended class is accessible via the 'extended' attribute
    """

    # todo: implement

    class Meta:
        abstract = True
