"""De library registreert geen projectspecifieke Hasura-objecten.

Tot en met v0.10.0 zette ``hasura_permissions`` bij het importeren de
waterworks-view ``vw_auth_uman_roles_summary_type`` en de functie
``auth_uman_get_roles_summary`` in de metadata van élk project. Een project
zonder die objecten (urbanworks) kreeg daardoor bij elke apply twee
inconsistenties, en sinds v0.10.0 is dat een ``CommandError`` (#37). Een
project dat eigen views of functies nodig heeft, registreert ze zelf.
"""

from django.test import SimpleTestCase

from rgs_django_utils.commands.hasura_permissions import HasuraConfig

WATERWORKS_OBJECTEN = {"vw_auth_uman_roles_summary_type", "auth_uman_get_roles_summary"}


class TestGeenProjectspecifiekeRegistraties(SimpleTestCase):
    def test_geen_auth_uman_view(self):
        namen = {v["table"]["name"] for v in HasuraConfig.registered_views}
        self.assertFalse(namen & WATERWORKS_OBJECTEN, namen)

    def test_geen_auth_uman_functie(self):
        namen = {f["function"]["name"] for f in HasuraConfig.registered_functions}
        self.assertFalse(namen & WATERWORKS_OBJECTEN, namen)
