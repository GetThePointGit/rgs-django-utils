import logging
import os
from typing import Generator

from rgs_django_utils.database.dj_extended_models import Config, FPerm, TPerm
from rgs_django_utils.models.views.abstract import HasuraTrackedView, ViewField

log = logging.getLogger(__name__)

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thissite.settings")
    setup_django(log=log)

from django.apps import apps  # noqa: E402
from django.db import models as dj_models  # noqa: E402


class UserView(HasuraTrackedView):
    def __init__(self, model):
        super().__init__(model)
        self.model = model
        self.through_model = self.get_through_model(model) or model
        self._meta = self.Meta(model)

    class Meta(HasuraTrackedView.Meta):
        def __init__(self, model):
            super().__init__(model._meta.db_table)

        @classmethod
        def get_field(cls, col):
            return next(field for field in cls.get_fields() if field.name == col)

        @staticmethod
        def get_fields():
            return [
                ViewField(
                    name="project_id",
                    verbose_name="project_id",
                    column="project_id",
                    config=Config(
                        permissions=FPerm(org_mem="-s-", proj_read="-s-"),
                    ),
                ),
                ViewField(
                    name="id",
                    verbose_name="id",
                    column="id",
                    config=Config(
                        permissions=FPerm(org_mem="-s-", proj_read="-s-"),
                    ),
                ),
                ViewField(
                    name="alias",
                    verbose_name="alias",
                    column="alias",
                    config=Config(
                        permissions=FPerm(org_mem="-s-", proj_read="-s-"),
                    ),
                ),
                ViewField(
                    name="organization_name",
                    verbose_name="organization_name",
                    column="organization_name",
                    config=Config(
                        permissions=FPerm(org_mem="-s-", proj_read="-s-"),
                    ),
                ),
            ]

    def get_permissions(self):
        new_perm = {}
        model_permissions = self.model.get_permissions() if hasattr(self.model, "get_permissions") else {}
        for role, perms in model_permissions.items():
            for perm in perms:
                if perm == "select":
                    new_perm[role] = {
                        "select": {self.model._meta.db_table: perms[perm]},
                    }
        return TPerm(**new_perm)

    def get_relations(self):
        fields = self._field_referencing_user()
        object_relationships = []
        for field in fields:
            # relationship from the original table to the view for querying
            object_relationships.append(
                {
                    "table": self.model._meta.db_table,
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
                    "name": self.model._meta.db_table,
                    "using": {
                        "manual_configuration": {
                            "column_mapping": {"id": self.model._meta.pk.column},
                            "insertion_order": "before_parent",
                            "remote_table": {"name": self.model._meta.db_table, "schema": "public"},
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

    def _field_referencing_user(self):
        fields = self.model._meta.get_fields()
        return [
            field
            for field in fields
            if field.is_relation
            and field.related_model == apps.get_model("core", "User")
            and isinstance(field, dj_models.ForeignKey)
        ]

    @property
    def db_view_name(self):
        return f"vw_{self._meta.db_table}_user"

    def get_sql(self):
        db_table = self.model._meta.db_table
        fields = self.model._meta.get_fields()
        fields_refencing_user = self._field_referencing_user()
        if self.through_model != self.model:
            field_that_references_through_model = next(
                (
                    field
                    for field in fields
                    if field.is_relation
                    and field.related_model == self.through_model
                    and isinstance(field, dj_models.ForeignKey)
                ),
                None,
            )
            join_clause = f"INNER JOIN {self.through_model._meta.db_table} ON {self.through_model._meta.db_table}.{self.through_model._meta.pk.name} = tbl.{field_that_references_through_model.column}"
        else:
            join_clause = ""
        on_clause = " OR ".join(
            [
                f'au.id = {"tbl" if self.through_model == self.model else self.through_model._meta.db_table}."{field.name}_id"'
                for field in fields_refencing_user
            ]
        )
        # We drop the view instead of replace so we can change the columns without problems in PostgreSQL.
        # If we would use CREATE OR REPLACE VIEW, we would get an error if we try to change the columns of the view.
        return f"""
            DROP VIEW IF EXISTS "{self.db_view_name}"
            ;
            CREATE VIEW "{self.db_view_name}" AS
            SELECT distinct {"tbl" if self.through_model == self.model else self.through_model._meta.db_table}.project_id, au.id, au.alias, org.name as organization_name
            FROM "{db_table}" tbl
            {join_clause}
            INNER JOIN auth_user au
            ON {on_clause}
            LEFT JOIN org org
            ON au.organization_id = org.id
            ;
        """

    @classmethod
    def get_through_model(cls, model):
        table_prefix = model._meta.db_table.split("_")[0]
        if table_prefix != model._meta.db_table:
            try:
                through_model = next(m for m in apps.get_models() if m._meta.db_table == table_prefix)
            except StopIteration:
                return model
            return through_model
        return model

    @classmethod
    def get_all_views(cls) -> Generator[HasuraTrackedView, None, None]:
        app_models = [model for model in apps.get_models() if callable(model) and issubclass(model, dj_models.Model)]
        for model in app_models:
            # skip if abstract model
            if model._meta.abstract:
                continue
            fields = model._meta.get_fields()
            # skip if no reference to user
            if not any(
                field.is_relation
                and field.related_model == apps.get_model("core", "User")
                and isinstance(field, dj_models.ForeignKey)
                for field in fields
            ):
                continue
            through_model = cls.get_through_model(model)
            through_model_fields = through_model._meta.get_fields()
            # skip if no reference to project in through model, because we need project_id in the view for permissions in hasura.
            if not any(
                field.is_relation
                and field.related_model == apps.get_model("core", "Project")
                and isinstance(field, dj_models.ForeignKey)
                and field.column == "project_id"
                for field in through_model_fields
            ):
                continue
            # for every model that has a reference to user and project, we create a view for that model. The view will be used to get the user information for that model.
            yield cls(model)
