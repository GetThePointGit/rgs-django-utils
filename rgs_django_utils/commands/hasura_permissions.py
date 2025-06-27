import json
import logging
import os

from django.apps import apps
from django.conf import settings
from django.db import models as dj_models

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
    ]
)

HasuraConfig.register_multiple_views(
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
            file_path = os.path.join(settings.BASE_DIR, os.pardir, "hasura", "hasura_metadata_exported.json")

        with open(file_path, "w") as f:
            f.write(json.dumps(self.generate_hasura_metadata()))

        log.info(f"Hasura metadata exported to {file_path}")

    @staticmethod
    def get_tables_from_models():
        tables = []

        perm_helper = PermissionHelper()

        app_models = [model for model in apps.get_models() if callable(model) and issubclass(model, dj_models.Model)]

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
            if tc.is_enum:
                out["is_enum"] = True

            object_relationships = []
            # many_to_one
            for field in tc.object_relationships:
                object_relationships.extend(
                    {
                        "name": field.name,
                        "using": {"foreign_key_constraint_on": field.column},
                    }
                )

            # one_to_one
            # also works for reverse?
            for field in tc.one_to_one_relationships:
                if isinstance(field, dj_models.OneToOneRel):
                    # todo: does this work?
                    if field.name != field.remote_field._related_name:
                        log.warning(
                            f"Related name for field {field.remote_field.name} "
                            f"of table {field.related_model._meta.object_name} is not provided"
                        )

                    object_relationships.extend(
                        {
                            "name": field.name,
                            "using": {
                                "foreign_key_constraint_on": {
                                    "column": field.remote_field.column,
                                    "table": {
                                        "name": field.related_model._meta.db_table,
                                        "schema": "public",
                                    },
                                }
                            },
                        }
                    )
                else:
                    object_relationships.extend(
                        {
                            "name": field.name,
                            "using": {"foreign_key_constraint_on": field.column},
                        }
                    )

            if len(object_relationships):
                out["object_relationships"] = object_relationships

            array_relationships = []
            for field in tc.array_relationships:
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
                                "column": field.remote_field.column,
                                "table": {"name": field.related_model._meta.db_table, "schema": "public"},
                            }
                        },
                    }
                )
            if len(array_relationships):
                out["array_relationships"] = array_relationships

            log.debug("start permissions")
            out.update(perm_helper.get_hasura_model_permissions(model))

            tables.append(out)

        return tables
