from rgs_django_utils.database.dj_extended_models import TableType


class TableDescription:
    table_type: TableType = None
    section = None
    order = None
    modules = None
    description = None


class TableDescriptionGetter:
    def __init__(self, model):
        self.model = model
        self.table_config = getattr(model, "TableDescription", TableDescription)

    @property
    def TableDescription(self):
        return getattr(self.model, "TableDescription", None)

    @property
    def is_extended_enum(self):
        td = self.TableDescription
        if td and getattr(td, "table_type", None) == TableType.EXTENDED_ENUM:
            return True
        return False

    @property
    def is_enum(self):
        td = self.TableDescription
        if td and getattr(td, "table_type", None) == TableType.ENUM:
            return True
        return False

    @property
    def object_relationships(self):
        return [f for f in self.model._meta.fields if f.many_to_one or f.one_to_one]

    @property
    def one_to_one_relationships(self):
        return [f for f in self.model._meta.related_objects if f.is_relation and f.one_to_one]

    @property
    def one_to_many_relationships(self):
        """Reverse relations of one to many or one to one."""
        return [f for f in self.model._meta.related_objects if f.is_relation and (f.one_to_many)]

    @property
    def many_to_many_relationships(self):
        return [f for f in self.model._meta.related_objects if f.is_relation and f.many_to_many]

    @property
    def raw_permissions(self):
        if hasattr(self.model, "get_permissions"):
            return self.model.get_permissions()
        else:
            return None
