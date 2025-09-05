import json
import logging
import os
from typing import Type

from attrs import field
from django.apps import apps
from django.conf import settings
from django.db import models as dj_models

from core import models
from rgs_django_utils.database.dj_extended_models import TableType, TPerm
from rgs_django_utils.database.dj_settings_helper import TableDescriptionGetter
from rgs_django_utils.database.permission_helper import PermissionHelper

log = logging.getLogger(__name__)


class HasuraConfigClass(type):
    def __new__(cls, name, bases, attrs, **kwargs):
        new_cls = super().__new__(cls, name, bases, attrs)
        if hasattr(new_cls, "Meta"):
            if new_cls.Meta.abstract:
                del new_cls.Meta
                return new_cls

        cls.registered_functions = []
        cls.registered_views = []
        return new_cls


class HasuraConfig(metaclass=HasuraConfigClass):
    @classmethod
    def register_multiple_functions(cls, functions):
        for function in functions:
            cls.register_function(**function)

    @classmethod
    def register_function(cls, function, configuration, permissions):
        """

        Example:
        function = {"name": "auth_organization_policy", "schema": "public"}
        configuration = {"custom_root_fields": {}, "session_argument": "hasura_session"}
        permissions = [{"role": "module_auth"}]

        :param function:
        :param configuration:
        :param permission:
        :return:
        """
        cls.registered_functions.append(
            {
                "function": function,
                "configuration": configuration,
                "permissions": permissions,
            }
        )

    @classmethod
    def register_multiple_views(cls, views):
        for view in views:
            cls.register_view(**view)

    @classmethod
    def register_view(
        cls,
        table,
        select_permissions=None,
    ):
        """

        :param table:
        :param select_permissions:
        :return:
        """
        cls.registered_views.append(
            {
                "table": table,
                "select_permissions": select_permissions,
            }
        )


HasuraConfig.register_multiple_functions(
    [
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
        {
            "function": {"name": "auth_update_user", "schema": "public"},
            "configuration": {"custom_root_fields": {}, "session_argument": "hasura_session", "exposed_as": "mutation"},
            "permissions": [{"role": "module_auth_2"}]
        },
    ]
)

HasuraConfig.register_multiple_views(
    [
        {
            "table": {"name": "vw_hasura_auth_organization_policy", "schema": "public"},
            "select_permissions": [
                {
                    "role": "module_auth",
                    "permission": {"columns": ["auth_method_id", "config", "id", "method_id", "visible"], "filter": {}},
                    "comment": "",
                }
            ],
        },
        {
            "table": {"name": "vw_hasura_auth_user", "schema": "public"},
            "select_permissions": [
                {
                    "role": "module_auth",
                    "permission": {"columns": ["id", "email_verified", "email", "organization_id", "is_active"], "filter": {}},
                    "comment": "",
                },
                {
                    "role": "module_auth_2",
                    "permission": {"columns": ["id", "email_verified", "email", "organization_id", "is_active"], "filter": {}},
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


class HasuraPermissions(object):
    def get_tables(self):
        return [*self.get_tables_from_models(), *HasuraConfig.registered_views]

    def get_functions(self):
        return HasuraConfig.registered_functions

    def generate_hasura_metadata(self):
        return {
            "resource_version": 1,  # ??
            "metadata": {
                "version": 3,
                "sources": [
                    {
                        "name": "default",
                        "kind": "postgres",
                        "tables": self.get_tables(),
                        "functions": self.get_functions(),
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

    def write_generate_hasura_metadata(self, file_path: str = None):
        if file_path is None:
            file_path = os.path.join(settings.BASE_DIR, "hasura", "hasura_metadata_exported.json")

        with open(file_path, "w") as f:
            f.write(json.dumps(self.generate_hasura_metadata()))

        log.info(f"Hasura metadata exported to {file_path}")

    @staticmethod
    def get_tables_from_models():
        tables = []

        perm_helper = PermissionHelper()

        app_models = [model for model in apps.get_models() if callable(model) and issubclass(model, dj_models.Model)]

        # Many-to-many relationships have through models which are not in app_models.
        # After generating the initial tables list, we need to include those through models.
        through_models: list[dict] = []

        for model in app_models:
            if model._meta.abstract:
                log.debug("skipped abstract model {}".format(model._meta.verbose_name))
                continue

            log.info(f"Processing model {model._meta.object_name}")

            out = {
                "table": {
                    "name": model._meta.db_table,
                    "schema": "public",
                },
            }
            tc = TableDescriptionGetter(model)
            if tc.is_enum and not model._meta.db_table.endswith("_ext"):
                out["is_enum"] = True

            object_relationships = []
            # Only add object relationships if not enum
            if not tc.is_enum and not model._meta.db_table.startswith("enum_"):
                # many_to_one
                for field in tc.object_relationships:
                    object_relationships.append(
                        {
                            "name": field.name,
                            "using": {"foreign_key_constraint_on": getattr(field, "column", field.name)},
                        }
                    )

                # one_to_one
                for field in tc.one_to_one_relationships:
                    if isinstance(field, dj_models.OneToOneRel):
                        if field.name != field.remote_field._related_name:
                            log.warning(
                                f"Related name for field {field.remote_field.name} "
                                f"of table {field.related_model._meta.object_name} is not provided"
                            )

                        object_relationships.append(
                            {
                                "name": field.name,
                                "using": {
                                    "foreign_key_constraint_on": {
                                        "column": getattr(field.remote_field, "column", field.remote_field.name),
                                        "table": {
                                            "name": field.related_model._meta.db_table,
                                            "schema": "public",
                                        },
                                    }
                                },
                            }
                        )
                    else:
                        object_relationships.append(
                            {
                                "name": field.name,
                                "using": {"foreign_key_constraint_on": getattr(field, "column", field.name)},
                            }
                        )

            if len(object_relationships):
                out["object_relationships"] = object_relationships

            array_relationships = []
            for field in tc.one_to_many_relationships:
                if field.name != field.remote_field._related_name:
                    log.warning(
                        f"Related name for field {field.remote_field.name} "
                        f"of table {field.related_model._meta.object_name} is not provided"
                    )

                array_relationships.append(
                    {
                        "name": field.name,
                        "using": {
                            "foreign_key_constraint_on": {
                                "column": getattr(field.remote_field, "column", field.remote_field.name),
                                "table": {"name": field.related_model._meta.db_table, "schema": "public"},
                            }
                        },
                    }
                )

            if len(array_relationships):
                out["array_relationships"] = array_relationships

            for field in tc.many_to_many_relationships:
                if hasattr(field, 'through'):
                    through_models.append({
                        'from_field': field,
                        "from_model": field.model,
                        "through_model": field.through,
                        "to_model": field.related_model,
                        "to_field": field.target_field,
                    })

            log.debug("start permissions")
            # FIX: Use actual DB column names for permissions
            permissions = perm_helper.get_hasura_model_permissions(model)
            for perm_type in ["select_permissions", "insert_permissions", "update_permissions", "delete_permissions"]:
                if perm_type in permissions:
                    for perm in permissions[perm_type]:
                        if "permission" in perm and "columns" in perm["permission"]:
                            perm["permission"]["columns"] = [
                                getattr(model._meta.get_field(col), "column", col)
                                for col in perm["permission"]["columns"]
                            ]

            out.update(permissions)

            tables.append(out)

        for model in through_models:
            # Add through model
            out = {
                "table": {
                    "name": model.get("through_model")._meta.db_table,
                    "schema": "public",
                },
            }
            from_field = model.get("from_field")
            from_model = model.get("from_model")
            through_model = model.get("through_model")
            to_model = model.get("to_model")
            to_field = model.get("to_field")
            array_relationships = []
            # for field in [field for field in through_model._meta.fields if field != through_model._meta.pk]:
            #     array_relationships.append(
            #         {
            #             "name": field.name,
            #             "using": {
            #                 "foreign_key_constraint_on": getattr(field, "column", getattr(field, 'field_name', field.name)),
            #             },
            #         }
            #     )
            # out["object_relationships"] = array_relationships
            permissions = perm_helper.get_hasura_model_permissions(from_model, lambda x: {
                from_model._meta.db_table: x
            })
            out.update(permissions)
            tables.append(out)

            # TODO: add field to from_model
            try:
                out = next(filter(lambda x: x["table"]["name"] == from_model._meta.db_table, tables))
                existing_names = {rel["name"] for rel in out.get("array_relationships", [])}
                relationship_name = from_field.accessor_name
                reverse_from_field = next(f for f in through_model._meta.fields if hasattr(f, 'target_field') and f.target_field.model == from_model)
                if relationship_name in existing_names:
                    log.warning("Array relationship already exists for through model: %s", relationship_name)
                else:
                    out["array_relationships"] = out.get("array_relationships", []) or []
                    out["array_relationships"].append({
                            "name": relationship_name,
                            "using": {
                                "foreign_key_constraint_on": {
                                    "column": getattr(reverse_from_field, "column", reverse_from_field.attname),
                                    "table": {
                                        "name": reverse_from_field.model._meta.db_table,
                                        "schema": "public",
                                    },
                                }
                            },
                        }
                    )
            except StopIteration:
                pass

            # TODO: add field to to_model
            try:
                out = next(filter(lambda x: x["table"]["name"] == to_model._meta.db_table, tables))
                existing_names = {rel["name"] for rel in out.get("array_relationships", [])}
                reverse_from_field = next(f for f in through_model._meta.fields if hasattr(f, 'target_field') and f.target_field.model == to_model)
                relationship_name = reverse_from_field.cache_name
                if relationship_name in existing_names:
                    log.warning("Array relationship already exists for through model: %s", relationship_name)
                else:
                    out["array_relationships"] = out.get("array_relationships", []) or []
                    out["array_relationships"].append(
                        {
                            "name": relationship_name,
                            "using": {
                                "foreign_key_constraint_on": {
                                    "column": getattr(reverse_from_field, "column", reverse_from_field.attname),
                                    "table": {
                                        "name": reverse_from_field.model._meta.db_table,
                                        "schema": "public",
                                    },
                                }
                            },
                        }
                    )
            except StopIteration:
                pass
        
        return tables
