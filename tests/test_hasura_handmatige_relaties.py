"""Handmatige Hasura-relaties via ``HasuraConfig.register_relationship``.

De generator leidt relaties af uit de foreign keys van de modellen. Een kolom
die zonder foreign key naar een andere tabel wijst (bv. een scope-kolom
``access_id``) heeft daardoor geen relatie in Hasura, en een rechtenfilter kan
er niet langs. Een app registreert zo'n relatie zelf; de generator zet hem als
``manual_configuration`` op de tabel. Een registratie die niet te plaatsen is,
faalt hard: een relatie die stil wegvalt breekt het filter dat erop leunt.
"""

from unittest import mock

from django.test import SimpleTestCase

from rgs_django_utils.commands.hasura_permissions import HasuraConfig, HasuraPermissions


def _tabellen() -> list[dict]:
    """Twee kale tabel-entries zoals de generator ze maakt."""
    return [
        {
            "table": {"name": "laag", "schema": "public"},
            "object_relationships": [{"name": "bron", "using": {"foreign_key_constraint_on": "bron_id"}}],
        },
        {"table": {"name": "project", "schema": "public"}},
    ]


def _relatie(**overschrijf) -> dict:
    """Een geldige relatie laag.access_project -> project."""
    return {
        "table": "laag",
        "name": "access_project",
        "remote_table": "project",
        "column_mapping": {"access_id": "id"},
        "kind": "object",
        **overschrijf,
    }


class TestRegisterRelationship(SimpleTestCase):
    def setUp(self):
        patch = mock.patch.object(HasuraConfig, "registered_relationships", [])
        patch.start()
        self.addCleanup(patch.stop)

    def test_registratie_komt_in_de_lijst(self):
        HasuraConfig.register_relationship("laag", "access_project", "project", {"access_id": "id"})
        self.assertEqual(HasuraConfig.registered_relationships, [_relatie()])

    def test_zelfde_registratie_twee_keer_is_geen_fout(self):
        for _ in range(2):
            HasuraConfig.register_relationship("laag", "access_project", "project", {"access_id": "id"})
        self.assertEqual(len(HasuraConfig.registered_relationships), 1)

    def test_andere_definitie_onder_dezelfde_naam_faalt(self):
        HasuraConfig.register_relationship("laag", "access_project", "project", {"access_id": "id"})
        with self.assertRaises(ValueError):
            HasuraConfig.register_relationship("laag", "access_project", "org", {"access_id": "id"})

    def test_onbekende_kind_faalt(self):
        with self.assertRaises(ValueError):
            HasuraConfig.register_relationship("laag", "x", "project", {"access_id": "id"}, kind="veel")

    def test_lege_column_mapping_faalt(self):
        with self.assertRaises(ValueError):
            HasuraConfig.register_relationship("laag", "x", "project", {})


class TestVoegHandmatigeRelatiesToe(SimpleTestCase):
    def test_object_relatie_komt_naast_de_bestaande(self):
        tabellen = _tabellen()
        HasuraPermissions.voeg_handmatige_relaties_toe(tabellen, [_relatie()])
        relaties = tabellen[0]["object_relationships"]
        self.assertEqual([r["name"] for r in relaties], ["bron", "access_project"])
        self.assertEqual(
            relaties[1]["using"],
            {
                "manual_configuration": {
                    "column_mapping": {"access_id": "id"},
                    "insertion_order": None,
                    "remote_table": {"name": "project", "schema": "public"},
                }
            },
        )

    def test_array_relatie_op_tabel_zonder_relaties(self):
        tabellen = _tabellen()
        relatie = _relatie(table="project", name="lagen", remote_table="laag", column_mapping={"id": "access_id"})
        HasuraPermissions.voeg_handmatige_relaties_toe(tabellen, [{**relatie, "kind": "array"}])
        self.assertEqual([r["name"] for r in tabellen[1]["array_relationships"]], ["lagen"])
        self.assertNotIn("object_relationships", tabellen[1])

    def test_onbekende_tabel_faalt(self):
        with self.assertRaisesRegex(ValueError, "tabel staat niet in de metadata"):
            HasuraPermissions.voeg_handmatige_relaties_toe(_tabellen(), [_relatie(table="bestaat_niet")])

    def test_onbekende_doeltabel_faalt(self):
        with self.assertRaisesRegex(ValueError, "doeltabel"):
            HasuraPermissions.voeg_handmatige_relaties_toe(_tabellen(), [_relatie(remote_table="bestaat_niet")])

    def test_botsende_naam_faalt(self):
        with self.assertRaisesRegex(ValueError, "naam bestaat al"):
            HasuraPermissions.voeg_handmatige_relaties_toe(_tabellen(), [_relatie(name="bron")])


class TestGetTablesMetRelaties(SimpleTestCase):
    def test_get_tables_plaatst_de_geregistreerde_relaties(self):
        with (
            mock.patch.object(HasuraPermissions, "get_tables_from_models", staticmethod(_tabellen)),
            mock.patch.object(HasuraConfig, "registered_relationships", [_relatie()]),
        ):
            tabellen = HasuraPermissions().get_tables()
        laag = next(t for t in tabellen if t["table"]["name"] == "laag")
        self.assertIn("access_project", [r["name"] for r in laag["object_relationships"]])
