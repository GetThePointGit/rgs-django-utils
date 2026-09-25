"""Tests voor de generator van de plpgsql-claimfunctie.

De functie zet rol-id's om in de lijst voor ``x-hasura-allowed-roles``. Hij
wordt gegenereerd uit ``settings.PERMISSION_TREE`` zodat de overervingsgraaf
maar op één plek staat; deze suite legt vast dát de gegenereerde SQL de
overerving bevat en geen database nodig heeft.
"""

from django.test import SimpleTestCase, override_settings

from rgs_django_utils.database.claim_sql import build_claim_function_sql

TREE = {
    "public": [],
    "auth": ["public"],
    "user_self": ["auth"],
    "aanvraag_rol": ["auth"],
    "aanvr_read": ["aanvraag_rol"],
    "aanvr_man": ["aanvr_read"],
    "org_mem": ["auth"],
    "org_uman": ["org_mem"],
    "org_adm": ["org_uman"],
}


@override_settings(PERMISSION_TREE=TREE)
class TestBuildClaimFunctionSql(SimpleTestCase):
    def test_signatuur_bevat_alle_argumenten(self):
        sql = build_claim_function_sql("auth_org_member_claim", ["organization_role_id", "aanvraag_role_id"])
        self.assertIn(
            "CREATE OR REPLACE FUNCTION public.auth_org_member_claim(organization_role_id text, aanvraag_role_id text)",
            sql,
        )

    def test_basisrollen_staan_er_altijd_in(self):
        sql = build_claim_function_sql("auth_org_member_claim", ["organization_role_id"])
        self.assertIn("ARRAY ['public', 'auth', 'user_self']", sql)

    def test_rol_levert_zijn_hele_overervingsketen(self):
        """org_adm hoort ook org_uman en org_mem op te leveren."""
        sql = build_claim_function_sql("auth_org_member_claim", ["organization_role_id"])
        self.assertIn("organization_role_id = 'org_adm'", sql)
        regel = next(r for r in sql.splitlines() if "'org_adm'" in r and "role_set :=" in r)
        for verwacht in ("org_adm", "org_uman", "org_mem"):
            self.assertIn(f"'{verwacht}'", regel)

    def test_onbekende_of_lege_rol_voegt_niets_toe(self):
        """Een NULL-argument (bv. geen stafrol) mag geen enkele rol opleveren."""
        sql = build_claim_function_sql("auth_user_claim", ["staff_role_id"])
        self.assertIn("IF staff_role_id IS NULL THEN", sql)

    def test_functie_is_immutable(self):
        """Een STORED generated column eist een IMMUTABLE functie."""
        sql = build_claim_function_sql("auth_org_member_claim", ["organization_role_id"])
        self.assertIn("IMMUTABLE", sql)
        self.assertIn("PARALLEL SAFE", sql)

    def test_basisrollen_zijn_instelbaar(self):
        sql = build_claim_function_sql("x_claim", ["r"], base_roles=("public",))
        self.assertIn("ARRAY ['public']", sql)
        self.assertNotIn("'user_self'", sql.split("role_set :=")[1].split("\n")[0])

    def test_alias_levert_de_keten_van_zijn_doelrol(self):
        """Een alias-id krijgt exact de keten van de rol waar hij naar wijst."""
        sql = build_claim_function_sql("auth_user_claim", ["staff_role_id"], aliases={"sys_admin": "org_adm"})
        self.assertIn("ELSIF staff_role_id = 'sys_admin' THEN", sql)
        regel_alias = next(r for r in sql.splitlines() if "'sys_admin'" in r and "ELSIF" in r)
        toewijzing = sql.splitlines()[sql.splitlines().index(regel_alias) + 1]
        regel_doel = next(r for r in sql.splitlines() if "'org_adm'" in r and "role_set :=" in r)
        self.assertEqual(toewijzing, regel_doel)
        # De alias zelf is geen Hasura-rol en hoort dus niet in de claimset.
        self.assertNotIn("'sys_admin'", toewijzing)

    def test_alias_tak_staat_na_de_boomtakken(self):
        """De alias-takken komen ná alle gegenereerde boomtakken, per argument."""
        sql = build_claim_function_sql("x_claim", ["r"], aliases={"sys_admin": "org_adm"})
        regels = sql.splitlines()
        laatste_boom = max(i for i, r in enumerate(regels) if "ELSIF r = '" in r and "'sys_admin'" not in r)
        alias = next(i for i, r in enumerate(regels) if "ELSIF r = 'sys_admin'" in r)
        self.assertGreater(alias, laatste_boom)
        self.assertEqual(regels[alias + 2].strip(), "END IF;")

    def test_aliassen_gelden_voor_elk_argument(self):
        sql = build_claim_function_sql("m_claim", ["a", "b"], aliases={"sys_admin": "org_adm"})
        self.assertIn("ELSIF a = 'sys_admin' THEN", sql)
        self.assertIn("ELSIF b = 'sys_admin' THEN", sql)

    @override_settings(PERMISSION_TREE=TREE, CLAIM_ROLE_ALIASES={"sys_admin": "org_adm"})
    def test_aliassen_komen_standaard_uit_settings(self):
        sql = build_claim_function_sql("auth_user_claim", ["staff_role_id"])
        self.assertIn("ELSIF staff_role_id = 'sys_admin' THEN", sql)

    def test_zonder_setting_geen_aliassen(self):
        sql = build_claim_function_sql("auth_user_claim", ["staff_role_id"])
        self.assertNotIn("sys_admin", sql)

    def test_alias_naar_onbekende_rol_faalt(self):
        with self.assertRaises(ValueError):
            build_claim_function_sql("x_claim", ["r"], aliases={"sys_admin": "bestaat_niet"})

    def test_alias_mag_zelf_geen_boomrol_zijn(self):
        with self.assertRaises(ValueError):
            build_claim_function_sql("x_claim", ["r"], aliases={"org_adm": "org_uman"})
