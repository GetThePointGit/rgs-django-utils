class TableDescription:
    is_extended_enum = False
    section = None
    order = None
    modules = None
    description = None


class TableDescriptionGetter:
    def __init__(self, model):
        self.model = model
        self.table_config = getattr(model, "TableDescription", TableDescription)

    @property
    def is_enum(self):
        return getattr(self.table_config, "is_extended_enum", False)

    @property
    def object_relationships(self):
        return [f for f in self.model._meta.fields if f.many_to_one]

    @property
    def one_to_one_relationships(self):
        return [f for f in self.model._meta.related_objects if f.is_relation and f.one_to_one]

    @property
    def array_relationships(self):
        """reverse relations of one to many or one to one"""
        return [f for f in self.model._meta.related_objects if f.is_relation and (f.one_to_many or f.one_to_one)]
