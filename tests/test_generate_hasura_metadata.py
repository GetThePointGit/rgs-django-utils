"""Een mislukte metadata-apply moet het commando laten falen, niet stil doorlopen.

``generate_hasura_metadata --apply`` kende vijf paden waarop er niets werd
toegepast terwijl het commando met exit 0 eindigde: een ontbrekend
metadatabestand, een ontbrekende URL, een ontbrekend admin-secret, een
``HTTPError`` en een ``URLError``. In een deploy-job onder ``set -e`` betekende
dat: job ``Complete``, ArgoCD groen, en de rechten van Hasura ongewijzigd.

Daar kwamen twee dingen bovenop. De succesmelding stond *boven* de apply, dus
het log eindigde altijd op "Successfully ran ...". En een inconsistente apply
(Hasura laat de objecten vallen die het niet kon plaatsen) gaf alleen een
waarschuwing -- precies de plek waar rechten ongemerkt verdwijnen.
"""

import json
import os
import urllib.error
from io import StringIO
from unittest import mock

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from rgs_django_utils.management.commands.generate_hasura_metadata import Command

GELDIGE_CONFIG = {
    "HASURA_GRAPHQL_URL": "http://hasura.test:8080",
    "HASURA_GRAPHQL_ADMIN_SECRET": "geheim",
}

# Zonder deze patch kan een gezette omgevingsvariabele op de ontwikkelmachine de
# "niet ingesteld"-tests alsnog laten slagen via de env-fallback.
LEGE_OMGEVING = mock.patch.dict(os.environ, {"HASURA_GRAPHQL_URL": "", "HASURA_GRAPHQL_ADMIN_SECRET": ""})


def _commando() -> Command:
    """Een ``Command`` met afgevangen uitvoer, zodat tests de logregels kunnen lezen."""
    return Command(stdout=StringIO(), stderr=StringIO())


def _antwoord(body: dict) -> mock.MagicMock:
    """Bootst de context manager na die ``urlopen`` teruggeeft."""
    resp = mock.MagicMock()
    resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.__enter__.return_value = resp
    return resp


class TestApplyFaaltHardBijOnbereikbareHasura(SimpleTestCase):
    """De faalmodus die op waterworks-dev een beveiligingsfix stil liet verdampen."""

    def test_urlerror_geeft_commanderror(self):
        commando = _commando()
        fout = urllib.error.URLError("[Errno 111] Connection refused")

        with self.settings(**GELDIGE_CONFIG), mock.patch("urllib.request.urlopen", side_effect=fout):
            with self.assertRaises(CommandError) as ctx:
                commando._send_metadata_to_hasura({"version": 3})

        self.assertIn("Kan Hasura niet bereiken", str(ctx.exception))

    def test_httperror_geeft_commanderror(self):
        commando = _commando()
        fout = urllib.error.HTTPError(
            url="http://hasura.test:8080/v1/metadata",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=None,
        )
        fout.read = mock.Mock(return_value=b'{"error": "kapot"}')

        with self.settings(**GELDIGE_CONFIG), mock.patch("urllib.request.urlopen", side_effect=fout):
            with self.assertRaises(CommandError) as ctx:
                commando._send_metadata_to_hasura({"version": 3})

        self.assertIn("500", str(ctx.exception))
        self.assertIn("kapot", str(ctx.exception))


class TestApplyFaaltHardBijOntbrekendeConfiguratie(SimpleTestCase):
    """Zonder URL of secret is er niets toegepast -- dat mag geen exit 0 zijn."""

    @LEGE_OMGEVING
    def test_ontbrekende_url_geeft_commanderror(self):
        with self.settings(HASURA_GRAPHQL_URL="", HASURA_GRAPHQL_ADMIN_SECRET="geheim"):
            with self.assertRaises(CommandError) as ctx:
                _commando()._send_metadata_to_hasura({"version": 3})

        self.assertIn("HASURA_GRAPHQL_URL", str(ctx.exception))

    @LEGE_OMGEVING
    def test_ontbrekend_secret_geeft_commanderror(self):
        with self.settings(HASURA_GRAPHQL_URL="http://hasura.test:8080", HASURA_GRAPHQL_ADMIN_SECRET=""):
            with self.assertRaises(CommandError) as ctx:
                _commando()._send_metadata_to_hasura({"version": 3})

        self.assertIn("HASURA_GRAPHQL_ADMIN_SECRET", str(ctx.exception))

    @LEGE_OMGEVING
    def test_instelling_die_helemaal_ontbreekt_geeft_ook_commanderror(self):
        """Niet een ``AttributeError``-traceback: de testsettings kennen deze namen niet."""
        with self.assertRaises(CommandError):
            _commando()._send_metadata_to_hasura({"version": 3})

    def test_ontbrekend_metadatabestand_geeft_commanderror(self):
        with self.assertRaises(CommandError) as ctx:
            _commando()._apply_from_file("/pad/dat/niet/bestaat/metadata.json")

        self.assertIn("niet gevonden", str(ctx.exception))


class TestInconsistenteMetadataIsStandaardEenFout(SimpleTestCase):
    """Hasura laat objecten vallen die het niet kon plaatsen; daar gaan rechten verloren."""

    INCONSISTENT = {
        "is_consistent": False,
        "inconsistent_objects": [
            {"type": "select_permission", "name": "spatial_source", "reason": "parse failed"},
        ],
    }

    def test_inconsistente_apply_geeft_commanderror(self):
        commando = _commando()

        with self.settings(**GELDIGE_CONFIG):
            with mock.patch("urllib.request.urlopen", return_value=_antwoord(self.INCONSISTENT)):
                with self.assertRaises(CommandError) as ctx:
                    commando._send_metadata_to_hasura({"version": 3})

        self.assertIn("inconsistenties", str(ctx.exception))
        self.assertIn("spatial_source", str(ctx.exception))

    def test_allow_inconsistent_laat_het_door_als_waarschuwing(self):
        commando = _commando()

        with self.settings(**GELDIGE_CONFIG):
            with mock.patch("urllib.request.urlopen", return_value=_antwoord(self.INCONSISTENT)):
                commando._send_metadata_to_hasura({"version": 3}, allow_inconsistent=True)

        self.assertIn("inconsistenties", commando.stdout.getvalue())

    def test_consistente_apply_meldt_succes(self):
        commando = _commando()

        with self.settings(**GELDIGE_CONFIG):
            with mock.patch("urllib.request.urlopen", return_value=_antwoord({"is_consistent": True})):
                commando._send_metadata_to_hasura({"version": 3})

        self.assertIn("succesvol toegepast", commando.stdout.getvalue())


class TestSuccesmeldingStaatNaDeApply(SimpleTestCase):
    """De regel waar een deploy-log op eindigt, moet over de apply gaan."""

    def _draai_handle(self, **urlopen_gedrag):
        """Draai ``handle(apply=True)`` en geef het commando terug, ook als het faalde.

        Parameters
        ----------
        **urlopen_gedrag
            Doorgegeven aan ``mock.patch`` voor ``urllib.request.urlopen``
            (``return_value`` of ``side_effect``).

        Returns
        -------
        tuple of (Command, CommandError or None)
            Het commando met zijn afgevangen uitvoer, en de fout die het gooide.
        """
        commando = _commando()
        perm = mock.MagicMock()
        perm.generate_hasura_metadata.return_value = {"metadata": {"version": 3}}
        fout = None

        with self.settings(**GELDIGE_CONFIG):
            with mock.patch(
                "rgs_django_utils.commands.hasura_permissions.HasuraPermissions",
                return_value=perm,
            ):
                with mock.patch("urllib.request.urlopen", **urlopen_gedrag):
                    try:
                        commando.handle(apply=True, export_path="/tmp/negeer.json")
                    except CommandError as e:
                        fout = e

        return commando, fout

    def test_geen_succesmelding_als_de_apply_faalt(self):
        commando, fout = self._draai_handle(side_effect=urllib.error.URLError("weg"))

        self.assertIsNotNone(fout, "een mislukte apply hoort een CommandError te geven")
        self.assertNotIn("Successfully ran generate_hasura_metadata", commando.stdout.getvalue())

    def test_wel_succesmelding_als_de_apply_slaagt(self):
        commando, fout = self._draai_handle(return_value=_antwoord({"is_consistent": True}))

        self.assertIsNone(fout)
        self.assertIn("Successfully ran generate_hasura_metadata", commando.stdout.getvalue())
