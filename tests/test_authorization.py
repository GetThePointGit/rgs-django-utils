"""De JWT-auth van Django-Ninja moet een ongeldig token daadwerkelijk weigeren.

``JwtUserToken.authenticate`` toetste ``claims.is_authenticated`` zonder
haakjes, terwijl dat een methode is. Een gebonden methode is altijd waar, dus
elk bearer-token kwam door de authenticatielaag heen -- ook een token waarvan
``decode_jwt`` de handtekening al had afgekeurd (die geeft ``None`` terug in
plaats van te raisen, juist zodat de aanroeper "geen token" en "fout token"
gelijk kan behandelen).

Dezelfde fout zat in het mapping-pad: ``{**claims}`` gaf de gebonden methode
door in plaats van de boolean.
"""

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from rgs_django_utils.permissions.claims import Claims, hasura_namespace
from rgs_django_utils.utils.authorization import JwtUserToken, UnauthorizedError


def _claims_zonder_geldig_token() -> Claims:
    """Bouw ``Claims`` uit een token dat de handtekeningcontrole niet haalt.

    Returns
    -------
    Claims
        Claims-object waarvan ``jwt`` ``None`` is; raakt de database niet,
        want zonder gedecodeerd token wordt er geen gebruiker opgezocht.
    """
    return Claims("dit-is-geen-geldig-jwt")


def _gebruiker() -> SimpleNamespace:
    """Minimale stand-in voor een Django-user; ``{**claims}`` leest email en fullname."""
    return SimpleNamespace(email="test@example.org", fullname="Test Gebruiker")


class TestJwtUserTokenWeigertOngeldigeTokens(SimpleTestCase):
    """Het slot op de Django-Ninja-API."""

    def test_onzintoken_wordt_geweigerd(self):
        with self.assertRaises(UnauthorizedError):
            JwtUserToken().authenticate(request=None, token="dit-is-geen-geldig-jwt")

    def test_leeg_token_wordt_geweigerd(self):
        with self.assertRaises(UnauthorizedError):
            JwtUserToken().authenticate(request=None, token="")

    def test_geldig_token_zonder_user_self_wordt_geweigerd(self):
        """Een correct ondertekend token is niet genoeg: ``user_self`` moet erin staan."""
        claims = _claims_zonder_geldig_token()
        claims.jwt = {hasura_namespace: {"x-hasura-allowed-roles": ["public", "auth"]}}
        claims._user = _gebruiker()

        with mock.patch("rgs_django_utils.utils.authorization.Claims", return_value=claims):
            with self.assertRaises(UnauthorizedError):
                JwtUserToken().authenticate(request=None, token="maakt-niet-uit")

    def test_geauthenticeerd_token_komt_er_wel_door(self):
        """Tegenproef: de fix mag niet doorslaan naar "iedereen weigeren"."""
        claims = _claims_zonder_geldig_token()
        claims.jwt = {hasura_namespace: {"x-hasura-allowed-roles": ["public", "auth", "user_self"]}}
        claims._user = _gebruiker()

        with mock.patch("rgs_django_utils.utils.authorization.Claims", return_value=claims):
            resultaat = JwtUserToken().authenticate(request=None, token="maakt-niet-uit")

        assert resultaat is claims


class TestIsAuthenticatedIsEenEchteBoolean(SimpleTestCase):
    """De uitkomst moet vals kunnen zijn, in beide toegangspaden."""

    def test_zonder_geldig_token_is_het_false(self):
        claims = _claims_zonder_geldig_token()
        assert claims.is_authenticated() is False

    def test_mapping_geeft_de_boolean_en_niet_de_methode(self):
        """``{**claims}`` wordt in templates gesplat; daar mag geen methode in landen."""
        claims = _claims_zonder_geldig_token()
        assert {**claims}["is_authenticated"] is False

    def test_mapping_volgt_een_geauthenticeerd_token(self):
        claims = _claims_zonder_geldig_token()
        claims.jwt = {hasura_namespace: {"x-hasura-allowed-roles": ["user_self"]}}
        claims._user = _gebruiker()

        assert {**claims}["is_authenticated"] is True
