from django.test import SimpleTestCase, override_settings

from rgs_django_utils.database.base_models.roles import audit_perm, base_model_role


class TestZonderMapping(SimpleTestCase):
    """Zonder BASE_MODEL_ROLES verandert er niets voor bestaande consumenten."""

    def test_naam_blijft_zichzelf(self):
        assert base_model_role("project_read") == "project_read"
        assert base_model_role("project_edit") == "project_edit"
        assert base_model_role("proj_read") == "proj_read"

    def test_audit_perm_gebruikt_de_oorspronkelijke_namen(self):
        perm = audit_perm()
        # FPerm.__init__ zet altijd een "public"-fallback op de meegegeven
        # default ("---"), ook als die niet expliciet is doorgegeven.
        assert perm.config == {
            "org_mem": "-s-",
            "project_read": "-s-",
            "project_edit": "isu",
            "public": "---",
        }

    def test_edit_argument_wordt_doorgegeven(self):
        assert audit_perm("is-").config["project_edit"] == "is-"


@override_settings(BASE_MODEL_ROLES={"project_read": "aanvr_read", "project_edit": "aanvr_man"})
class TestMetMapping(SimpleTestCase):
    """Een project vertaalt de namen naar zijn eigen vocabulaire."""

    def test_namen_worden_vertaald(self):
        assert base_model_role("project_read") == "aanvr_read"
        assert base_model_role("project_edit") == "aanvr_man"

    def test_niet_gemapte_naam_blijft_zichzelf(self):
        """Een project dat maar twee van de drie mapt houdt de derde ongewijzigd."""
        assert base_model_role("proj_read") == "proj_read"

    def test_audit_perm_gebruikt_de_vertaalde_namen(self):
        perm = audit_perm()
        # zie TestZonderMapping.test_audit_perm_gebruikt_de_oorspronkelijke_namen
        # voor waarom "public" hier ook in staat.
        assert perm.config == {
            "org_mem": "-s-",
            "aanvr_read": "-s-",
            "aanvr_man": "isu",
            "public": "---",
        }
