"""Tests voor PermissionHelper.get_rol_table_permissions.

Dekt de first-match-wins-resolutie: een rol die zelf een actie-permissie
definieert mag niet worden overschreven door geërfde (voorouder-)rollen.
Geen Django DB nodig — werkt op fake-modelklassen met get_permissions().
"""

from django.test import SimpleTestCase, override_settings

from rgs_django_utils.database import dj_extended_models
from rgs_django_utils.database.dj_extended_models import FPerm, TPerm
from rgs_django_utils.database.permission_helper import PermissionHelper

TEST_TREE = {
    "public": [],
    "auth": ["public"],
    "org_mem": ["auth"],
    "org_uman": ["org_mem"],
    "org_adm": ["org_uman"],
    "sys_adm": ["org_adm"],
}


class ModelWithExplicitOverride:
    """sys_adm definieert expliciet bredere permissies dan zijn voorouders."""

    @classmethod
    def get_permissions(cls):
        return TPerm(
            auth={"select": {"active": {"_eq": True}}},
            org_adm={
                "select": {"active": {"_eq": True}},
                "update": {"id": {"_eq": "x-hasura-org-id"}},
            },
            sys_adm={"select": {}, "update": {}, "delete": {}},
        )


class ModelMixedForms:
    """Filter-vorm bij org_mem; sys_adm overschrijft expliciet per actie."""

    @classmethod
    def get_permissions(cls):
        return TPerm(
            org_mem={"organization": {"id": {"_eq": "x-hasura-org-id"}}},
            sys_adm={"select": {}, "update": {}, "insert": {}},
        )


class _FakeCompositePk:
    """Stub voor Django 5.2's CompositePrimaryKey-veld.

    get_rol_field_permissions leest: __class__.__name__, is_relation,
    primary_key, name.  Een attname-attribuut is er niet op CompositePrimaryKey
    (is_relation=False), dus dat hoeft de stub niet te bieden.
    """

    __class__ = type("CompositePrimaryKey", (), {"__name__": "CompositePrimaryKey"})()
    is_relation = False
    primary_key = True
    name = "pk"


class _FakePlainField:
    """Gewoon IntegerField-achtig veld zonder r_config (wordt overgeslagen)."""

    __class__ = type("IntegerField", (), {"__name__": "IntegerField"})()
    is_relation = False
    primary_key = False
    name = "organization_id"
    r_config = None


class ModelWithCompositePk:
    """Fake model met een composite primary key (zoals org_module).

    get_rol_field_permissions leest alleen _meta.get_fields() en per veld
    __class__/is_relation/primary_key/name/r_config — een lichte stub volstaat.
    """

    class _Meta:
        @staticmethod
        def get_fields():
            return [_FakePlainField(), _FakeCompositePk()]

    _meta = _Meta()


@override_settings(PERMISSION_TREE=TEST_TREE)
class TestCompositePrimaryKeySkipped(SimpleTestCase):
    def test_composite_pk_emits_no_field_entry(self):
        """CompositePrimaryKey heeft geen eigen kolom en mag geen permissie-entry krijgen."""
        perms = PermissionHelper().get_rol_field_permissions(ModelWithCompositePk)
        self.assertNotIn(
            "pk",
            perms,
            "CompositePrimaryKey heeft geen eigen kolom en mag geen permissie-entry krijgen",
        )


@override_settings(PERMISSION_TREE=TEST_TREE)
class TestGetRolTablePermissionsFirstMatchWins(SimpleTestCase):
    def test_own_action_dict_wins_over_inherited(self):
        perms = PermissionHelper().get_rol_table_permissions(ModelWithExplicitOverride)
        self.assertEqual(perms["sys_adm"]["select"], {}, "sys_adm select: eigen {} moet winnen van auth")
        self.assertEqual(perms["sys_adm"]["update"], {}, "sys_adm update: eigen {} moet winnen van org_adm")
        self.assertEqual(
            perms["sys_adm"]["delete"], {}, "sys_adm delete: actie-dict-vorm moet ook delete kunnen zetten"
        )

    def test_role_without_own_entry_inherits_nearest(self):
        perms = PermissionHelper().get_rol_table_permissions(ModelWithExplicitOverride)
        self.assertEqual(perms["org_adm"]["select"], {"active": {"_eq": True}})
        self.assertEqual(perms["org_adm"]["update"], {"id": {"_eq": "x-hasura-org-id"}})
        # org_uman heeft zelf niets en erft select van auth; update is nergens
        # in zijn keten gedefinieerd (org_adm is geen voorouder van org_uman).
        self.assertEqual(perms["org_uman"]["select"], {"active": {"_eq": True}})
        self.assertIsNone(perms["org_uman"]["update"])

    def test_own_action_dict_wins_over_inherited_filter_form(self):
        perms = PermissionHelper().get_rol_table_permissions(ModelMixedForms)
        self.assertEqual(perms["sys_adm"]["select"], {})
        self.assertEqual(perms["sys_adm"]["update"], {})
        self.assertEqual(perms["sys_adm"]["insert"], {})
        # org_mem behoudt zijn filter-vorm op insert/select/update (geen delete).
        org_filt = {"organization": {"id": {"_eq": "x-hasura-org-id"}}}
        self.assertEqual(perms["org_mem"]["select"], org_filt)
        self.assertEqual(perms["org_mem"]["update"], org_filt)
        self.assertEqual(perms["org_mem"]["insert"], org_filt)
        self.assertIsNone(perms["org_mem"]["delete"])


# Een boom met namen die bewust NIET in de oude roles_list staan.
EIGEN_TREE = {
    "public": [],
    "auth": ["public"],
    "aanvr_read": ["auth"],
    "aanvr_man": ["aanvr_read"],
}


@override_settings(PERMISSION_TREE=EIGEN_TREE)
class TestRolvalidatieVolgtDeBoom(SimpleTestCase):
    def test_eigen_rol_uit_de_boom_wordt_geaccepteerd(self):
        """Een projectrol die alleen in PERMISSION_TREE staat mag gebruikt worden."""
        perm = FPerm("---", aanvr_man="isu")
        self.assertEqual(perm.config["aanvr_man"], "isu")

    def test_rol_buiten_de_boom_wordt_geweigerd(self):
        """Een rol die het project niet kent hoort te knallen waar je hem schrijft."""
        with self.assertRaises(ValueError):
            FPerm("---", proj_cli="isu")

    def test_tperm_volgt_dezelfde_regel(self):
        """TPerm valideert tegen dezelfde bron als FPerm."""
        perm = TPerm(aanvr_read={"select": {}})
        self.assertIn("aanvr_read", perm.config)
        with self.assertRaises(ValueError):
            TPerm(proj_cli={"select": {}})


@override_settings(PERMISSION_TREE=None)
class TestTerugvalZonderBoom(SimpleTestCase):
    def test_zonder_boom_geldt_de_ingebouwde_lijst(self):
        """Consumers zonder PERMISSION_TREE blijven op roles_list werken."""
        self.assertEqual(dj_extended_models.allowed_role_names(), dj_extended_models.roles_set)
