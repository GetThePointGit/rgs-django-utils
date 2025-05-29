import json
import logging
import os

log = logging.getLogger(__name__)

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django(log)

from django.apps import apps
from django.db import models as dj_models
from rgs_django_utils.database.dj_extended_models import TPerm, TableType
from rgs_django_utils.database.dj_settings_helper import TableDescriptionGetter
from thissite import settings


def generate_hasura_metadata(file_path: str = None):
    if file_path is None:
        file_path = os.path.join(settings.BASE_DIR, os.pardir, "hasura", "hasura_metadata_exported.json")

    with open(file_path, "w") as f:
        f.write(json.dumps(make_metadata()))

    log.info(f"Hasura metadata exported to {file_path}")


def make_metadata():
    tables = []

    app_models = [model for model in apps.get_models() if callable(model) and issubclass(model, dj_models.Model)]  # NOQA

    for model in app_models:
        if model._meta.abstract:
            log.debug("skipped {}".format(model._meta.verbose_name))
            continue

        tc = TableDescriptionGetter(model)

        table = {"table": {"name": model._meta.db_table, "schema": "public"}}
        log.warning(f"Processing model {model._meta.object_name}")

        td = getattr(model, "TableDescription", None)
        if td and getattr(td, "table_type", None) == TableType.ENUM:
            table["is_enum"] = True

        object_relationships = tc.object_relationships

        # TODO: One on one relationships
        oneToOneFields = [
            f
            for f in model._meta.fields
            if isinstance(f, dj_models.OneToOneField)
            and not getattr(getattr(f.related_model, "TableDescription", {}), "table_type", None) == TableType.ENUM
        ]
        pass
        if oneToOneFields:
            table["object_relationships"] = []
            for f in oneToOneFields:
                if f.name != f.remote_field.field_name:
                    log.warning(
                        f"Related name for field {f.remote_field.name} "
                        f"of table {f.related_model._meta.object_name} is not provided"
                    )

                table["object_relationships"].append(
                    {"name": f"{f.name}", "using": {"foreign_key_constraint_on": f"{f.db_column or f.attname}"}}
                )

        if object_relationships:
            table["object_relationships"] = (
                [] if "object_relationships" not in table else table["object_relationships"]
            )
            for f in object_relationships:
                table["object_relationships"].append(
                    {"name": f"{f.name}", "using": {"foreign_key_constraint_on": f"{f.column}"}}
                )

        array_relationships = tc.array_relationships
        if array_relationships:
            table["array_relationships"] = []
            for f in array_relationships:
                if f.name != f.remote_field._related_name:
                    log.warning(
                        f"Related name for field {f.remote_field.name} "
                        f"of table {f.related_model._meta.object_name} is not provided"
                    )

                table["array_relationships"].append(
                    {
                        "name": f"{f.name}",
                        "using": {
                            "foreign_key_constraint_on": {
                                "column": f"{f.remote_field.column}",
                                "table": {"name": f"{f.related_model._meta.db_table}", "schema": "public"},
                            }
                        },
                    }
                )

        log.warning("start permissions")
        table["insert_permissions"] = []
        table["select_permissions"] = []
        table["update_permissions"] = []
        table["delete_permissions"] = []
        model_permissions = get_permissions(model)
        log.warning("model_permissions is {}".format(model_permissions))
        for role, role_permissions in model_permissions.items():
            if "insert" in role_permissions:
                columns = [
                    f.column
                    for f in model._meta.fields
                    if hasattr(f, "r_config")
                    and f.r_config is not None
                    and f.r_config.permissions is not None
                    and "i" in f.r_config.permissions[role]
                ]
                if len(columns) != 0 and "id" not in columns and model._meta.pk.column == "id":
                    columns.append("id")

                table["insert_permissions"].append(
                    {
                        "role": role,
                        "permission": {
                            "check": role_permissions["insert"],
                            "columns": columns,
                        },
                        "comment": "",
                    }
                )
            if "select" in role_permissions:
                columns = [
                    f.column
                    for f in model._meta.fields
                    if hasattr(f, "r_config")
                    and f.r_config is not None
                    and f.r_config.permissions is not None
                    and "s" in f.r_config.permissions[role]
                ]
                if len(columns) != 0 and "id" not in columns and model._meta.pk.column == "id":
                    columns.append("id")

                table["select_permissions"].append(
                    {
                        "role": role,
                        "permission": {
                            "columns": columns,
                            "filter": role_permissions["select"],
                        },
                        "comment": "",
                    }
                )
            if "update" in role_permissions:
                table["update_permissions"].append(
                    {
                        "role": role,
                        "permission": {
                            "check": role_permissions["update"],
                            "columns": [
                                f.column
                                for f in model._meta.fields
                                if hasattr(f, "r_config")
                                and f.r_config is not None
                                and f.r_config.permissions is not None
                                and "u" in f.r_config.permissions[role]
                            ],
                            "filter": role_permissions["update"],
                        },
                        "comment": "",
                    }
                )
            if "delete" in role_permissions:
                table["delete_permissions"].append(
                    {
                        "role": role,
                        "permission": {
                            "filter": role_permissions["delete"],
                        },
                        "comment": "",
                    }
                )

        tables.append(table)

    tables.extend(
        [
            {
                "table": {"name": "vw_hasura_auth_organization_policy", "schema": "public"},
                "select_permissions": [
                    {
                        "role": "module_auth",
                        "permission": {"columns": ["config", "id", "method_id", "visible"], "filter": {}},
                        "comment": "",
                    }
                ],
            },
            {
                "table": {"name": "vw_hasura_auth_user", "schema": "public"},
                "select_permissions": [
                    {
                        "role": "module_auth",
                        "permission": {"columns": ["id", "email_verified", "email", "organization_id"], "filter": {}},
                        "comment": "",
                    }
                ],
            },
            {
                "table": {"name": "vw_hasura_auth_account", "schema": "public"},
                "select_permissions": [
                    {
                        "role": "module_auth",
                        "permission": {
                            "columns": ["id", "method_id", "provider_account_id", "organization_id"],
                            "filter": {},
                        },
                        "comment": "",
                    }
                ],
            },
        ]
    )

    return {
        "resource_version": 1,  # ??
        "metadata": {
            "version": 3,
            "sources": [
                {
                    "name": "default",
                    "kind": "postgres",
                    "tables": tables,
                    "functions": [
                        {
                            "function": {"name": "auth_organization_policy", "schema": "public"},
                            "configuration": {"custom_root_fields": {}, "session_argument": "hasura_session"},
                            "permissions": [{"role": "module_auth"}],
                        },
                        {
                            "function": {"name": "auth_user", "schema": "public"},
                            "configuration": {"custom_root_fields": {}, "session_argument": "hasura_session"},
                            "permissions": [{"role": "module_auth"}],
                        },
                        {
                            "function": {"name": "auth_account", "schema": "public"},
                            "configuration": {"custom_root_fields": {}, "session_argument": "hasura_session"},
                            "permissions": [{"role": "module_auth"}],
                        },
                        {
                            "function": {"name": "auth_account_insert", "schema": "public"},
                            "configuration": {"custom_root_fields": {}, "session_argument": "hasura_session"},
                            "permissions": [{"role": "module_auth_2"}],
                        },
                        {
                            "function": {"name": "auth_validate_password", "schema": "public"},
                            "configuration": {"custom_root_fields": {}, "session_argument": "hasura_session"},
                            "permissions": [{"role": "module_auth"}],
                        },
                    ],
                    "configuration": {
                        "connection_info": {
                            "database_url": {"from_env": "HASURA_GRAPHQL_DATABASE_URL"},
                            "isolation_level": "read-committed",
                            "pool_settings": {
                                "connection_lifetime": 600,
                                "idle_timeout": 180,
                                "max_connections": 50,
                                "retries": 1,
                            },
                            "use_prepared_statements": True,
                        }
                    },
                }
            ],
        },
    }


def get_permissions(app_model: dj_models.Model):
    if hasattr(app_model, "permissions") and callable(app_model.permissions):
        return app_model.permissions()
    return TPerm()


if __name__ == "__main__":
    generate_hasura_metadata()
    # get_permissions(django.contrib.admin.models.LogEntry)
    pass
