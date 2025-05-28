from ninja.security import HttpBearer

from rgs_utils.permissions.claims import Claims


class UnauthorizedError(Exception):
    """The claims in the JWT token do not allow access to the requested resource."""

    pass


class JwtUserToken(HttpBearer):
    def authenticate(self, request, token):
        claims = Claims(token)
        if claims.is_authenticated:
            return claims
        raise UnauthorizedError("User not authenticated.")


class JwtModuleToken(HttpBearer):
    def __init__(self, module_name: str):
        super().__init__()
        self._module_name = module_name

    def authenticate(self, request, token):
        claims = Claims(token)
        if claims.has_allowed_role(self._module_name):
            return claims
        raise UnauthorizedError("User not authorized to access this module.")
