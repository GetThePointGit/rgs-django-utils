import logging
from functools import cache
from typing import OrderedDict

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from rgs_django_utils.database.dj_extended_models import FPerm, FPresets, TPerm

# cache permission instance
_permission_helper = None

log = logging.getLogger(__name__)


def recursive_list(root_element, permissions, permission_tree, child_list, depth):
    for child in child_list:
        if child not in permission_tree:
            raise ImproperlyConfigured(f"reference '{child}' from PERMISSION_TREE does not exists.")
        if child == root_element:
            raise ImproperlyConfigured(f"circular reference '{child}' in PERMISSION_TREE.")
        if child not in permissions:
            permissions[child] = depth
            recursive_list(root_element, permissions, permission_tree, permission_tree[child], depth + 1)
    return


permission_keys = {"select", "insert", "update", "delete"}


# todo:
# -config select aggregation rights
# - insert and update "set"
# - ignore update "check"?
# - comments?


class PermissionHelper:
    def __init__(self):
        if not hasattr(settings, "PERMISSION_TREE"):
            raise ImproperlyConfigured("PERMISSION_TREE must be defined")

        self.role_perm_lists = self.get_permission_inherence_list()

    @staticmethod
    def get_permission_inherence_list():
        permission_tree = settings.PERMISSION_TREE
        out = {}

        for k in settings.PERMISSION_TREE.keys():
            permissions = {k: 0}
            # for key, find all nested permissions
            recursive_list(k, permissions, permission_tree, permission_tree[k], 1)
            out[k] = [l[0] for l in sorted(permissions.items(), key=lambda i: i[1])]

        return out

    @cache
    def get_rol_table_permissions(self, model):
        # todo: make arrays from subbranches to correctly propagate None
        # get table permissions
        if not hasattr(model, "get_permissions"):
            log.info(f"{model} has no hasura permissions")
            return None
        table_permissions = model.get_permissions()
        table_permissions: TPerm

        out = {}
        for k, role_list in self.role_perm_lists.items():
            out[k] = {
                "insert": None,
                "select": None,
                "update": None,
                "delete": None,
            }
            for role in role_list:
                if role in table_permissions.config:
                    rol_table_permissions = table_permissions.config[role]
                    if type(rol_table_permissions) is str:
                        a = 1

                    if set(rol_table_permissions.keys()).issubset(permission_keys):
                        out[k].update(rol_table_permissions)
                    else:
                        if out[k]["insert"] is None:
                            out[k]["insert"] = rol_table_permissions
                        if out[k]["select"] is None:
                            out[k]["select"] = rol_table_permissions
                        if out[k]["update"] is None:
                            out[k]["update"] = rol_table_permissions

        if table_permissions.config.get("module_auth") is not None:
            # only select permission for module_auth
            rol_table_permissions = table_permissions.config["module_auth"]
            if "module_auth_" not in out:
                out["module_auth_2"] = {
                    "insert": None,
                    "select": None,
                    "update": None,
                    "delete": None,
                }
            if rol_table_permissions.get("select") is not None:
                out["module_auth_2"]["select"] = rol_table_permissions["select"] 
            pass
        if table_permissions.config.get("module_auth_2") is not None:
            rol_table_permissions = table_permissions.config["module_auth_2"]
            if "module_auth_2" not in out:
                out["module_auth_2"] = {
                    "insert": None,
                    "select": None,
                    "update": None,
                    "delete": None,
                }
            if rol_table_permissions.get("select") is not None:
                out["module_auth_2"]["select"] = rol_table_permissions["select"]
            if rol_table_permissions.get("insert") is not None:
                out["module_auth_2"]["insert"] = rol_table_permissions["insert"]
            if rol_table_permissions.get("update") is not None:
                out["module_auth_2"]["update"] = rol_table_permissions["update"]
            if rol_table_permissions.get("delete") is not None:
                out["module_auth_2"]["delete"] = rol_table_permissions["delete"]
        return out

    @cache
    def get_rol_field_permissions(self, model):
        out = {}
        for field in model._meta.get_fields():
            if field.is_relation:
                if getattr(field, "attname", None) is not None:
                    # foreign key, add _id field
                    name = field.attname
                else:
                    continue

            else:
                name = field.name

            field_config = getattr(field, "r_config", None)
            if field_config is None and field.primary_key:
                # primary key field, no config
                # todo: should check if other fields can be accessed?
                out[name] = {
                    k: {"insert": False, "select": True, "update": False} for k in self.role_perm_lists.keys()
                }
                continue
            if field_config is None:
                log.info(f"'{name}' has no config for with permissions ")
                continue
            field_permissions = getattr(field_config, "permissions", None)
            if field_permissions is None:
                log.info(f"'{name}' has no config for with permissions ")
                continue
            presets: FPresets | None = getattr(field_config, "presets", None)

            out[name] = {}

            field_permissions: FPerm

            for k, role_list in self.role_perm_lists.items():
                out_fr = {
                    "insert": False,
                    "select": False,
                    "update": False,
                    "preset_insert": (False,),
                    "preset_update": (False,),
                }

                for role in role_list:
                    if role in field_permissions.config:
                        role_field_permission = field_permissions.config[role]
                        if not out_fr["insert"] and role_field_permission[0] == "i":
                            out_fr["insert"] = True
                        if not out_fr["select"] and role_field_permission[1] == "s":
                            out_fr["select"] = True
                        if not out_fr["update"] and role_field_permission[2] == "u":
                            out_fr["update"] = True
                    if presets is not None and role in presets.config:
                        role_presets = presets.config[role]
                        if not out_fr["preset_insert"]:
                            if role_presets[0][0] == "i":
                                out_fr["preset_insert"] = (True, role_presets[1])
                            elif type(role_presets[0]) is tuple and role_presets[0][0][0] == "i":
                                out_fr["preset_insert"] = (True, role_presets[0][1])
                        if not out_fr["preset_update"]:
                            if role_presets[0][1] == "u":
                                out_fr["preset_update"] = (True, role_presets[1])
                            elif type(role_presets[0]) is tuple and role_presets[1][0][1] == "u":
                                out_fr["preset_update"] = (True, role_presets[1][1])

                out[name][k] = out_fr

            table_permissions = model.get_permissions()
            table_permissions: TPerm
            if table_permissions.config.get("module_auth") is not None:
                out_fr = {
                    "insert": False,
                    "select": False,
                    "update": False,
                    "preset_insert": (False,),
                    "preset_update": (False,),
                }
                role_field_permission = field_permissions.config.get("module_auth", "---")
                if role_field_permission and not out_fr["select"] and role_field_permission[1] == "s":
                    out_fr["select"] = True
                out[name]["module_auth"] = out_fr
            if table_permissions.config.get("module_auth_2") is not None:
                out_fr = {
                    "insert": False,
                    "select": False,
                    "update": False,
                    "preset_insert": (False,),
                    "preset_update": (False,),
                }
                role_field_permission = field_permissions.config.get("module_auth_2", "---")
                if role_field_permission and not out_fr["insert"] and role_field_permission[0] == "i":
                    out_fr["insert"] = True
                if role_field_permission and not out_fr["select"] and role_field_permission[1] == "s":
                    out_fr["select"] = True
                if role_field_permission and not out_fr["update"] and role_field_permission[2] == "u":
                    out_fr["update"] = True
                # TODO auth_module_2 presets
                if presets is not None and "module_auth_2" in presets.config:
                    role_presets = presets.config.get("module_auth_2")
                    if not out_fr["preset_insert"][0]:
                        if role_presets[0][0] == "i":
                            out_fr["preset_insert"] = (True, role_presets[1])
                        elif type(role_presets[0]) is tuple and role_presets[0][0][0] == "i":
                            out_fr["preset_insert"] = (True, role_presets[0][1])
                    if not out_fr["preset_update"][0]:
                        if role_presets[0][1] == "u":
                            out_fr["preset_update"] = (True, role_presets[1])
                        elif type(role_presets[0]) is tuple and role_presets[1][0][1] == "u":
                            out_fr["preset_update"] = (True, role_presets[1][1])
                out[name]["module_auth_2"] = out_fr
        return out

    def get_hasura_model_permissions(self, model, wrap_role_table_filter=None):
        table_perms = self.get_rol_table_permissions(model)
        if table_perms is None:
            log.warning(f"{model} has no hasura permissions")
            return {}

        field_perms = self.get_rol_field_permissions(model)

        select_permissions = []
        insert_permissions = []
        update_permissions = []
        delete_permissions = []

        def _permissions_for_role(role):
            role_table_filter = table_perms.get(role)
            role_fields = [(k, perms.get(role)) for k, perms in field_perms.items()]
            # select
            try:
                action_fields = [k for k, p in role_fields if p["select"]]
            except TypeError:
                a = 1
            if role_table_filter.get("select") is not None and len(action_fields) > 0:
                select_permissions.append(
                    {
                        "role": role,
                        "permission": {
                            "filter": wrap_role_table_filter(role_table_filter.get("select")) if wrap_role_table_filter else role_table_filter.get("select"),
                            "columns": action_fields,
                            "allow_aggregations": True,  # todo
                        },
                    }
                )
            action_fields = [k for k, p in role_fields if p["insert"]]
            set_fields = dict((k, p["preset_insert"][1]) for k, p in role_fields if p["insert"] and p["preset_insert"] and p["preset_insert"][0])
            if role_table_filter.get("insert") is not None and len(action_fields) > 0:
                insert_permissions.append(
                    {
                        "role": role,
                        "permission": {
                            "check": wrap_role_table_filter(role_table_filter.get("insert")) if wrap_role_table_filter else role_table_filter.get("insert"),
                            "columns": action_fields,
                            "set": set_fields,  # todo
                        },
                        "backend_only": False,
                    }
                )
            action_fields = [k for k, p in role_fields if p["update"]]
            set_fields = dict((k, p["preset_update"][1]) for k, p in role_fields if p["update"] and p["preset_update"] and p["preset_update"][0])
            if role_table_filter.get("update") is not None and len(action_fields) > 0:
                update_permissions.append(
                    {
                        "role": role,
                        "permission": {
                            "filter": wrap_role_table_filter(role_table_filter.get("update")) if wrap_role_table_filter else role_table_filter.get("update"),
                            "check": {},  # todo: also support?
                            "columns": action_fields,
                            "set": set_fields,  # todo: also support?
                        },
                    }
                )
            if role_table_filter.get("delete") is not None:
                delete_permissions.append(
                    {
                        "role": role,
                        "permission": {
                            "filter": wrap_role_table_filter(role_table_filter.get("delete")) if wrap_role_table_filter else role_table_filter.get("delete"),
                        },
                    }
                )

        for role in self.role_perm_lists.keys():
            _permissions_for_role(role)
        if "module_auth" in table_perms:
            _permissions_for_role("module_auth")
        if "module_auth_2" in table_perms:
            _permissions_for_role("module_auth_2")

        return OrderedDict(
            (
                ("select_permissions", select_permissions),
                ("insert_permissions", insert_permissions),
                ("update_permissions", update_permissions),
                ("delete_permissions", delete_permissions),
            )
        )


@cache
def get_permission_helper():
    return PermissionHelper()
