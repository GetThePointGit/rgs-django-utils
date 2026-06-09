import logging
import os
from abc import ABC, abstractmethod
from typing import Self, Type, TypedDict

from rgs_django_utils.database.dj_extended_models import TPerm

log = logging.getLogger(__name__)

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thissite.settings")
    setup_django(log=log)


all = []

SchemaJsonParts = TypedDict("SchemaJsonParts", {"defs": dict[str, dict], "referenced_by": dict[str, str]})


class HasuraTrackedView(ABC):
    def __init__(self, db_view):
        self._meta = self.Meta(db_view)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        all.append(cls)

    def __repr__(self):
        return self.get_sql()

    def __name__(self):
        return "_".join(part.capitalize() for part in self._meta.db_table.split("_"))

    @property
    def db_table_name(self):
        return self._meta.db_table

    @property
    def db_view_name(self):
        return f"vw_{self._meta.db_table}"

    @staticmethod
    def all() -> list[Type[Self]]:
        """All classes that inherit HasuraTrackedView. Used for auto generation of tracked views and permissions in hasura.

        Returns
        -------
            list[Type[Self]]: All classes that inherit HasuraTrackedView.

        Example
        -------
        ```python
        views = HasuraTrackedView.all()
        # returns [<class 'UserView'>, <class 'AnotherView'>, ...]
        ```
        """
        return set(all)

    def get_json_schema_parts(self) -> SchemaJsonParts:
        return {
            "defs": {
                self.db_view_name: {
                    "type": "object",
                    "readOnly": True,
                    "properties": {
                        field.name: {
                            "type": "string",
                            "readOnly": True,
                            "title": field.verbose_name or field.name or field.column,
                        }
                        for field in self._meta.get_fields()
                    },
                }
            },
            "referenced_by": {self.db_table_name: self.db_view_name},
        }

    def get_relations(self):
        fields = self.fields_referencing_original_table
        object_relationships = []
        for field in fields:
            # relationship from the original table to the view for querying
            object_relationships.append(
                {
                    "table": self.original_model,
                    "object_relationship": {
                        "name": f"{field.name}_short",
                        "using": {
                            "manual_configuration": {
                                "column_mapping": {field.db_column or field.column: "id"},
                                "insertion_order": "before_parent",
                                "remote_table": {"name": self.db_view_name, "schema": "public"},
                            },
                        },
                    },
                }
            )
        # reverse relationship from the view to the original table for permissions in hasura
        object_relationships.append(
            {
                "table": self.db_view_name,
                "object_relationship": {
                    "name": self.original_model,
                    "using": {
                        "manual_configuration": {
                            "column_mapping": {"id": fields[0].db_column or fields[0].column},
                            "insertion_order": "before_parent",
                            "remote_table": {"name": self.original_model, "schema": "public"},
                        },
                    },
                },
            }
        )
        # group permission by table
        relationshipsByTable = []
        for relationship in object_relationships:
            tableName = relationship["table"]
            if tableName not in [r["table"] for r in relationshipsByTable]:
                relationshipsByTable.append(
                    {
                        "table": tableName,
                        "object_relationships": [],
                    }
                )
            for r in relationshipsByTable:
                if r["table"] == tableName:
                    r["object_relationships"].append(relationship["object_relationship"])
                    break
        return relationshipsByTable

    def get_permissions(self):
        new_perm = {}
        model_permissions = self.model.get_permissions() if hasattr(self.model, "get_permissions") else {}
        for role, perms in model_permissions.items():
            for perm in perms:
                if perm == "select":
                    new_perm[role] = {
                        "select": {self.original_model: perms[perm]},
                    }
        return TPerm(**new_perm)

    @property
    @abstractmethod
    def fields_referencing_original_table(self):
        """Return the fields that reference the original model."""
        ...

    @property
    def original_model(self):
        """The original model that the view is based on. Used for auto generation of permissions in hasura."""
        return self.model._meta.db_table

    @classmethod
    @abstractmethod
    def get_all_views(
        cls,
        app_models=None,  # Note: We cannot set default to all models in the app. Because default are eveluated at import time, and at that time not all models are imported yet.
    ) -> list[Self]:
        """
        Return all views of the class. Used for auto generation of views in postgresql.

        Arguments
        ---------
            app_models: list of all models in the app, used to find the models that are referenced by the view. Default is all models in the app.

        Example
        -------
        ```python
        all_views = HasuraTrackedView.get_all_views()
        # returns [HasuraTrackedView("vw_ww_user"), HasuraTrackedView("vw_pl_user"), ...]
        ```
        """
        ...

    @abstractmethod
    def get_sql(self) -> str:
        """
        Return the sql for the view. Used for auto generation of views in postgresql.

        Example
        -------
        ```python
        view = UserView("vw_ww_user")
        view.get_sql()
        # returns "DROP VIEW IF EXISTS "vw_ww_user"; CREATE OR REPLACE VIEW vw_ww_user AS SELECT ... FROM ..."
        ```
        """
        ...

    class Meta:
        def __init__(self, db_view):
            self.db_table = db_view

        view = True
        abstract = True


class ViewField(object):
    def __init__(self, name, verbose_name, column, config):
        self.name = name
        self.verbose_name = verbose_name
        self.column = column
        self.r_config = config
        self.is_relation = False
        self.primary_key = False
