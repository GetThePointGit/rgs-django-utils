from rgs_django_utils.database.dj_extended_models import TableType


class TableDescription:
    """Default ``TableDescription`` applied when a model does not define its own.

    Models can attach a nested ``class TableDescription`` with any of the
    attributes below to override the defaults surfaced to the Hasura
    metadata generator and the datamodel exporters.

    Attributes
    ----------
    table_type : TableType or None
        Marks the table as a regular model, an enum or an extended enum.
    section : TableSection or None
        Top-level section the table belongs to.
    order : int or None
        Sort order within the section.
    modules : str or iterable, optional
        Modules in which the table is exposed (``"*"`` means every module).
    description : str or None
        Free-form description shown in the generated documentation.
    """

    table_type: TableType = None
    section = None
    order = None
    modules = None
    description = None


class TableDescriptionGetter:
    """Read-only adapter that exposes rgs metadata of a Django model.

    Wraps a Django model class and surfaces the nested ``TableDescription``
    (or the module-level default), plus convenience accessors for the
    different relationship kinds needed by the metadata generator.

    Parameters
    ----------
    model : type[django.db.models.Model]
        The model class to describe.

    Examples
    --------
    >>> getter = TableDescriptionGetter(SomeModel)          # doctest: +SKIP
    >>> getter.is_enum, getter.is_extended_enum             # doctest: +SKIP
    (False, False)
    >>> [f.name for f in getter.object_relationships]       # doctest: +SKIP
    ['owner', 'project']
    """

    def __init__(self, model):
        self.model = model
        self.table_config = getattr(model, "TableDescription", TableDescription)

    @property
    def TableDescription(self):
        """Return the model's nested ``TableDescription`` class, or ``None``."""
        return getattr(self.model, "TableDescription", None)

    @property
    def is_extended_enum(self) -> bool:
        """Return ``True`` when ``table_type == TableType.EXTENDED_ENUM``."""
        td = self.TableDescription
        if td and getattr(td, "table_type", None) == TableType.EXTENDED_ENUM:
            return True
        return False

    @property
    def is_enum(self) -> bool:
        """Return ``True`` when ``table_type == TableType.ENUM``."""
        td = self.TableDescription
        if td and getattr(td, "table_type", None) == TableType.ENUM:
            return True
        return False

    @property
    def object_relationships(self):
        """Forward ``ForeignKey`` and ``OneToOneField`` fields on the model."""
        return [f for f in self.model._meta.fields if f.many_to_one or f.one_to_one]

    @property
    def one_to_one_relationships(self):
        """Reverse ``OneToOne`` relations pointing back to this model."""
        return [f for f in self.model._meta.related_objects if f.is_relation and f.one_to_one]

    @property
    def one_to_many_relationships(self):
        """Reverse relations where many child rows point back to this model."""
        return [f for f in self.model._meta.related_objects if f.is_relation and (f.one_to_many)]

    @property
    def many_to_many_relationships(self):
        """Reverse many-to-many relations involving this model."""
        return [f for f in self.model._meta.related_objects if f.is_relation and f.many_to_many]

    @property
    def raw_permissions(self):
        """Return ``model.get_permissions()`` output, or ``None`` when unset."""
        if hasattr(self.model, "get_permissions"):
            return self.model.get_permissions()
        else:
            return None
