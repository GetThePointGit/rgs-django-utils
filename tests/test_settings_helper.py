import json

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from rgs_django_utils.database import dj_extended_models
from rgs_django_utils.database.dj_settings_helper import TableDescriptionGetter, resolve_display_field
from rgs_django_utils.database.permission_helper import get_permission_helper
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

        self.assertEqual(len(td.one_to_many_relationships), 2)
        self.assertListEqual(
            [rel.related_model for rel in td.one_to_many_relationships], [ChildModel, ManyToManyModel]
        )

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
            {"insert": False, "select": False, "update": False},
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
        self.assertEqual(len(select_permissions), 0)

        print(json.dumps(permissions, indent=2))

    def test_permissions(self):
        td = TableDescriptionGetter(MiddleModel)
        self.assertEqual(type(td.raw_permissions), dj_extended_models.TPerm)


class TestDisplayField(TestCase):
    """``TableDescriptionGetter.display_field`` en ``resolve_display_field`` (ww#588)."""

    def test_plain_field(self):
        self.assertEqual(TableDescriptionGetter(ParentModel).display_field, "ids")

    def test_dotted_path_through_foreign_key(self):
        self.assertEqual(TableDescriptionGetter(ChildModel).display_field, "middle_model.ids")
        field = resolve_display_field(ChildModel, "middle_model.parent_model.ids")
        self.assertEqual(field.model, ParentModel)
        self.assertEqual(field.name, "ids")

    def test_unset_is_none(self):
        self.assertIsNone(TableDescriptionGetter(MiddleModel).display_field)
        self.assertIsNone(TableDescriptionGetter(ManyToManyModel).display_field)

    def test_invalid_paths_raise(self):
        for path in ["bestaat_niet", "middle_model", "middle_model.bestaat_niet", "ids.x", "middle_models.ids", ""]:
            with self.subTest(path=path), self.assertRaises(ImproperlyConfigured):
                resolve_display_field(ChildModel if path != "middle_models.ids" else ParentModel, path)
