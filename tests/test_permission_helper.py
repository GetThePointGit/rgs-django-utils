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


# --- Post-update check (rgs-django-utils#25) --------------------------------
#
# Zonder check mag een rij naar een staat buiten de eigen scope worden
# geüpdatet (bv. auth_user_project.project_id naar een ander project). De
# generator zet de check daarom standaard gelijk aan de update-filter.

PROJECT_FILTER = {"project_id": {"_in": "x-hasura-project-ids"}}
ORG_FILTER = {"organization_id": {"_eq": "x-hasura-org-id"}}


class _FakeConfigField:
    """Veld met een ``r_config`` dat org_adm (en dus sys_adm) laat updaten."""

    __class__ = type("IntegerField", (), {"__name__": "IntegerField"})()
    is_relation = False
    primary_key = False

    def __init__(self, name):
        self.name = name
        # FPerm valideert rollen tegen PERMISSION_TREE: pas aanmaken binnen
        # override_settings, dus hier (bij get_fields) en niet op moduleniveau.
        self.r_config = type("Cfg", (), {"permissions": FPerm("-s-", org_adm="isu"), "presets": None})()


def _model_met_permissies(tperm_factory):
    """Bouw een fake model met één updatebaar veld en de gegeven ``TPerm``."""

    class _Meta:
        @staticmethod
        def get_fields():
            return [_FakeConfigField("project_id")]

    class FakeModel:
        _meta = _Meta()

        @classmethod
        def get_permissions(cls):
            return tperm_factory()

    return FakeModel


def _update_check_per_rol(model, wrap=None):
    perms = PermissionHelper().get_hasura_model_permissions(model, wrap)
    return {p["role"]: p["permission"] for p in perms["update_permissions"]}


@override_settings(PERMISSION_TREE=TEST_TREE)
class TestUpdateCheckGelijkAanFilter(SimpleTestCase):
    def test_filtervorm_krijgt_check_gelijk_aan_filter(self):
        model = _model_met_permissies(lambda: TPerm(org_adm=PROJECT_FILTER))
        perms = _update_check_per_rol(model)
        self.assertEqual(perms["org_adm"]["filter"], PROJECT_FILTER)
        self.assertEqual(perms["org_adm"]["check"], PROJECT_FILTER)

    def test_actievorm_zonder_check_krijgt_check_gelijk_aan_filter(self):
        model = _model_met_permissies(lambda: TPerm(org_adm={"select": {}, "update": PROJECT_FILTER}))
        perms = _update_check_per_rol(model)
        self.assertEqual(perms["org_adm"]["check"], PROJECT_FILTER)

    def test_geerfde_update_neemt_check_mee(self):
        """sys_adm heeft geen eigen entry en erft update én check van org_adm."""
        model = _model_met_permissies(lambda: TPerm(org_adm={"update": PROJECT_FILTER}))
        perms = _update_check_per_rol(model)
        self.assertEqual(perms["sys_adm"]["filter"], PROJECT_FILTER)
        self.assertEqual(perms["sys_adm"]["check"], PROJECT_FILTER)

    def test_lege_filter_geeft_lege_check(self):
        model = _model_met_permissies(lambda: TPerm(org_adm={"update": {}}))
        perms = _update_check_per_rol(model)
        self.assertEqual(perms["org_adm"]["check"], {})

    def test_wrapper_geldt_ook_voor_check(self):
        """Through-tabellen nesten filter én check onder de relatie naar het bronmodel."""
        model = _model_met_permissies(lambda: TPerm(org_adm=PROJECT_FILTER))
        perms = _update_check_per_rol(model, lambda x: {"bron": x})
        self.assertEqual(perms["org_adm"]["filter"], {"bron": PROJECT_FILTER})
        self.assertEqual(perms["org_adm"]["check"], {"bron": PROJECT_FILTER})


@override_settings(PERMISSION_TREE=TEST_TREE)
class TestExplicieteUpdateCheck(SimpleTestCase):
    def test_expliciete_check_wint_van_filter(self):
        model = _model_met_permissies(lambda: TPerm(org_adm={"update": PROJECT_FILTER, "update_check": ORG_FILTER}))
        perms = _update_check_per_rol(model)
        self.assertEqual(perms["org_adm"]["filter"], PROJECT_FILTER)
        self.assertEqual(perms["org_adm"]["check"], ORG_FILTER)

    def test_expliciet_lege_check_schakelt_de_check_uit(self):
        model = _model_met_permissies(lambda: TPerm(org_adm={"update": PROJECT_FILTER, "update_check": {}}))
        perms = _update_check_per_rol(model)
        self.assertEqual(perms["org_adm"]["check"], {})

    def test_check_van_voorouder_wordt_niet_met_eigen_filter_gecombineerd(self):
        """sys_adm's eigen update-filter krijgt zijn eigen check, niet die van org_adm."""
        model = _model_met_permissies(
            lambda: TPerm(
                org_adm={"update": PROJECT_FILTER, "update_check": ORG_FILTER},
                sys_adm={"update": {}},
            )
        )
        table_perms = PermissionHelper().get_rol_table_permissions(model)
        self.assertNotIn("update_check", table_perms["sys_adm"])
        perms = _update_check_per_rol(model)
        self.assertEqual(perms["sys_adm"]["check"], {})
        self.assertEqual(perms["org_adm"]["check"], ORG_FILTER)

    def test_update_check_zonder_update_wordt_geweigerd(self):
        with self.assertRaises(ValueError):
            TPerm(org_adm={"select": {}, "update_check": ORG_FILTER})
