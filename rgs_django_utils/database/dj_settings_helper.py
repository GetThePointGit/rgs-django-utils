from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured

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
    display_field : str or None
        Field that gives a record a human-readable label (e.g. ``"ids"`` or
        ``"name"``), used where a UI has to name a single record, such as a
        pick list. A dotted path (``"profile_location.ids"``) follows forward
        ``ForeignKey``/``OneToOneField`` relations. ``None`` means the model
        has no display field.
    """

    table_type: TableType = None
    section = None
    order = None
    modules = None
    description = None
    display_field = None


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
    def display_field(self) -> str | None:
        """Return the validated ``TableDescription.display_field`` path, or ``None``.

        Returns
        -------
        str or None
            The configured (possibly dotted) field path.

        Raises
        ------
        django.core.exceptions.ImproperlyConfigured
            When the path does not resolve to a non-relational field.
        """
        path = getattr(self.TableDescription, "display_field", None)
        if path is None:
            return None
        resolve_display_field(self.model, path)
        return path

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
        """Reverse relations where many child rows point back to this model.

        Includes both reverse ``ForeignKey`` (``one_to_many``) and reverse
        ``ManyToManyField`` (``many_to_many``) relations — from the parent's
        point of view both surface as Hasura "array relationships".
        """
        return [f for f in self.model._meta.related_objects if f.is_relation and (f.one_to_many or f.many_to_many)]

    @property
    def many_to_many_relationships(self):
        """Reverse many-to-many relations involving this model.

        Strict subset of :attr:`one_to_many_relationships` — exposed
        separately so the Hasura metadata generator can resolve the
        ``through`` model for each M2M.
        """
        return [f for f in self.model._meta.related_objects if f.is_relation and f.many_to_many]

    @property
    def raw_permissions(self):
        """Return ``model.get_permissions()`` output, or ``None`` when unset."""
        if hasattr(self.model, "get_permissions"):
            return self.model.get_permissions()
        else:
            return None


def resolve_display_field(model, path: str):
    """Resolve a (dotted) display-field path to the field it ends on.

    Parameters
    ----------
    model : type[django.db.models.Model]
        The model the path starts from.
    path : str
        Field name, or a dotted path through forward ``ForeignKey`` /
        ``OneToOneField`` relations (``"profile_location.ids"``).

    Returns
    -------
    django.db.models.Field
        The non-relational field at the end of the path.

    Raises
    ------
    django.core.exceptions.ImproperlyConfigured
        When a step does not exist, a step before the last is not a forward
        to-one relation, or the last step is itself a relation.
    """
    parts = path.split(".") if isinstance(path, str) else []
    if not parts or not all(parts):
        raise ImproperlyConfigured(f"{model.__name__}.TableDescription.display_field: invalid path {path!r}")
    current = model
    for i, name in enumerate(parts):
        try:
            field = current._meta.get_field(name)
        except FieldDoesNotExist as exc:
            raise ImproperlyConfigured(
                f"{model.__name__}.TableDescription.display_field {path!r}: {current.__name__} has no field {name!r}"
            ) from exc
        is_last = i == len(parts) - 1
        is_to_one = field.concrete and (field.many_to_one or field.one_to_one)
        if not is_last:
            if not is_to_one:
                raise ImproperlyConfigured(
                    f"{model.__name__}.TableDescription.display_field {path!r}: "
                    f"{name!r} is not a forward ForeignKey/OneToOneField"
                )
            current = field.related_model
        elif field.is_relation or not field.concrete:
            raise ImproperlyConfigured(
                f"{model.__name__}.TableDescription.display_field {path!r}: "
                f"must end on a plain field, {name!r} is a relation"
            )
    return field
