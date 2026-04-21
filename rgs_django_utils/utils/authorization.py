from ninja.security import HttpBearer

from rgs_django_utils.permissions.claims import Claims


class UnauthorizedError(Exception):
    """Raised when the JWT claims do not permit access to the requested resource."""

    pass


class JwtUserToken(HttpBearer):
    """Django-Ninja auth backend that requires a fully authenticated user.

    Use as ``auth=JwtUserToken()`` on a Ninja route. The bearer token is
    decoded into :class:`~rgs_django_utils.permissions.claims.Claims`; the
    request is allowed only when :meth:`Claims.is_authenticated` returns
    true (i.e. both a valid user and the ``user_self`` role).

    Examples
    --------
    >>> from rgs_django_utils.utils.authorization import JwtUserToken
    >>> @router.get("/me", auth=JwtUserToken())        # doctest: +SKIP
    ... def get_me(request):
    ...     return request.auth.user
    """

    def authenticate(self, request, token):
        """Return ``Claims`` when the token is authenticated, otherwise raise."""
        claims = Claims(token)
        if claims.is_authenticated:
            return claims
        raise UnauthorizedError("User not authenticated.")


class JwtModuleToken(HttpBearer):
    """Django-Ninja auth backend that gates routes on a named Hasura role.

    Instead of a full user-authentication check, only the presence of
    *module_name* in the token's allowed roles is required. This is the
    pattern used for module-level or admin endpoints that shouldn't be
    tied to a specific user session.

    Parameters
    ----------
    module_name : str
        Role name that the JWT must include under ``x-hasura-allowed-roles``
        (for example ``"admin"`` or ``"module_auth"``).

    Examples
    --------
    >>> from rgs_django_utils.utils.authorization import JwtModuleToken
    >>> @router.get("/admin/ping", auth=JwtModuleToken("admin"))   # doctest: +SKIP
    ... def admin_ping(request):
    ...     return {"ok": True}
    """

    def __init__(self, module_name: str):
        super().__init__()
        self._module_name = module_name

    def authenticate(self, request, token):
        """Return ``Claims`` when *module_name* is an allowed role, otherwise raise."""
        claims = Claims(token)
        if claims.has_allowed_role(self._module_name):
            return claims
        raise UnauthorizedError("User not authorized to access this module.")
