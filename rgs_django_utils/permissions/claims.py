import collections

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()

from django.contrib.auth import get_user_model

from rgs_django_utils.utils.token_validator import decode_jwt

hasura_namespace = "https://hasura.io/jwt/claims"


class Claims(collections.abc.Mapping):
    """Read-only view over the Hasura-namespaced claims in a JWT.

    ``Claims`` wraps :func:`decode_jwt` and exposes the commonly-needed
    fields (authenticated flag, user object, email, full name, passwordless
    token) through both attribute access and mapping protocol, so a claims
    instance can be splatted as ``{**claims}`` into a template context.

    Parameters
    ----------
    token : str
        Raw encoded JWT string. If the token is invalid or missing the
        Hasura namespace, every accessor falls back to ``None`` / ``False``.

    Examples
    --------
    >>> claims = Claims("")                        # doctest: +SKIP
    >>> claims.is_authenticated()                  # doctest: +SKIP
    False
    """

    # all attributes that are mappable ({**claims})
    _keys = ["is_authenticated", "user", "email", "passwordless_token", "fullname"]

    def __init__(self, token: str):
        self.jwt = decode_jwt(token)
        if self.jwt is not None:
            user_id = self.user_id
            self._user = get_user_model().objects.get(pk=user_id) if user_id is not None else None
        else:
            self._user = None

    def is_authenticated(self) -> bool:
        """Return ``True`` when the token carries a user with the ``user_self`` role.

        Returns
        -------
        bool
            ``True`` if a valid user was resolved *and* ``user_self`` is in
            the token's allowed roles; ``False`` otherwise.
        """
        return self.user and self.has_allowed_role("user_self")

    @property
    def user(self) -> get_user_model() | None:
        """Return the resolved Django user, or ``None`` when unknown.

        Notes
        -----
        Presence of a user object does **not** imply authentication — a
        valid JWT might still lack the ``user_self`` role. Use
        :meth:`is_authenticated` when an auth check is required.
        """
        return self._user

    @property
    def user_id(self) -> int | None:
        """Return the ``x-hasura-user-id`` claim as ``int``, or ``None`` when absent."""
        if not self.jwt or hasura_namespace not in self.jwt:
            return None
        token = self.jwt[hasura_namespace]
        return int(token["x-hasura-user-id"]) if "x-hasura-user-id" in token else None

    def has_allowed_role(self, role: str) -> bool:
        """Return ``True`` when *role* appears in the token's allowed roles.

        Parameters
        ----------
        role : str
            Role name to probe (e.g. ``"user_self"``, ``"module_auth"``).

        Returns
        -------
        bool
            ``True`` if the role is listed under ``x-hasura-allowed-roles``.

        Notes
        -----
        This is a membership check on the token only. It does not verify
        the user is authenticated.
        """
        if not self.jwt or hasura_namespace not in self.jwt:
            return False
        token = self.jwt[hasura_namespace]
        return token["x-hasura-allowed-roles"] and role in token["x-hasura-allowed-roles"]

    @property
    def email(self) -> str | None:
        """Return the email from the claims, falling back to the user object.

        Notes
        -----
        An email may be returned even when the user is not authenticated,
        since the JWT may carry it without the ``user_self`` role.
        """
        if not self.jwt or hasura_namespace not in self.jwt:
            return None
        token = self.jwt[hasura_namespace]
        email = token.get("x-hasura-email", None)
        if email:
            return email
        if self.user:
            return self.user.email
        return None

    @property
    def passwordless_token(self) -> str | None:
        """Return the ``x-passwordless-token`` claim, or ``None`` when absent."""
        if not self.jwt or hasura_namespace not in self.jwt:
            return None
        token = self.jwt[hasura_namespace]
        return token.get("x-passwordless-token", None)

    @property
    def fullname(self) -> str:
        """Return the full name of the resolved user, or ``""`` when missing."""
        return self.user.fullname if self.user else ""

    def __getitem__(self, key):
        if key not in self._keys:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._keys)

    def __len__(self):
        return len(self._keys)

    def haskey(self, key):
        return key in self._keys

    def keys(self):
        return self._keys
