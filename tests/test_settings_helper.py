import json

from django.test import TestCase
from rgs_django_utils.database import dj_extended_models
from rgs_django_utils.database.dj_settings_helper import TableDescriptionGetter
from rgs_django_utils.database.permission_helper import PermissionHelper, get_permission_helper

from tests.testapp.models import (
    ChildModel,
    EnumExtendedTestModel,
    EnumTestModel,
    ManyToManyModel,
    MiddleExtendedModel,
    MiddleModel,
    ParentModel,
)


class TestDoubleIdentifier(TestCase):
    def setUp(self):
        # set context
        pass

    def test_base(self):
        td = TableDescriptionGetter(MiddleModel)
        self.assertFalse(td.is_enum)
        self.assertFalse(td.is_extended_enum)

        td = TableDescriptionGetter(EnumTestModel)
        self.assertTrue(td.is_enum)
        self.assertFalse(td.is_extended_enum)

        td = TableDescriptionGetter(EnumExtendedTestModel)
        self.assertTrue(td.is_enum)
        self.assertFalse(td.is_extended_enum)

        td = TableDescriptionGetter(EnumExtendedTestModel.ExtendedClass)
        self.assertFalse(td.is_enum)
        self.assertTrue(td.is_extended_enum)

    def test_relationships(self):
        td = TableDescriptionGetter(MiddleModel)
        self.assertEqual(len(td.object_relationships), 1)
        self.assertEqual(td.object_relationships[0].related_model, ParentModel)

        self.assertEqual(len(td.one_to_one_relationships), 1)
        self.assertEqual(td.one_to_one_relationships[0].related_model, MiddleExtendedModel)

        self.assertEqual(len(td.array_relationships), 2)
        self.assertListEqual([rel.related_model for rel in td.array_relationships], [ChildModel, ManyToManyModel])

    def test_permission_helper(self):
        ph = get_permission_helper()

        permissions = ph.role_perm_lists
        self.assertListEqual(permissions.get("public"), ["public"])
        self.assertListEqual(permissions.get("auth"), ["auth", "public"])
        self.assertListEqual(
            permissions.get("project_management"),
            ["project_management", "project_edit", "project", "auth", "public"],
        )
        self.assertListEqual(
            permissions.get("organization_management"),
            ["organization_management", "organization", "project", "auth", "public"],
        )
        self.assertListEqual(
            permissions.get("developer"),
            [
                "developer",
                "project_management",
                "organization_projectmanager",
                "project_edit",
                "project",
                "auth",
                "public",
            ],
        )

        table_permissions = ph.get_rol_table_permissions(MiddleModel)
        self.assertDictEqual(
            table_permissions.get("public"),
            {"insert": None, "select": None, "update": None, "delete": None},
        )

        field_permissions = ph.get_rol_field_permissions(MiddleModel)
        ids = field_permissions.get("ids")
        self.assertDictEqual(
            ids.get("public"),
            {"insert": False, "select": False, "update": False},
        )
        self.assertDictEqual(
            ids.get("project"),
            {"insert": False, "select": True, "update": False},
        )
        self.assertDictEqual(
            ids.get("project_edit"),
            {"insert": True, "select": True, "update": True},
        )
        self.assertDictEqual(
            ids.get("developer"),
            {"insert": True, "select": True, "update": True},
        )

        permissions = ph.get_hasura_model_permissions(MiddleModel)

        select_permissions = permissions.get("select_permissions")
        self.assertEqual(len(select_permissions), 8)

        print(json.dumps(permissions, indent=2))

    def test_permissions(self):
        td = TableDescriptionGetter(MiddleModel)
        self.assertEqual(type(td.raw_permissions), dj_extended_models.TPerm)
