import collections

if __name__ == "__main__":
    from rgs_django_utils.setup_django import setup_django

    setup_django()

from core import models
from rgs_django_utils.tasks.token_validator import decode_jwt

hasura_namespace = "https://hasura.io/jwt/claims"


class Claims(collections.abc.Mapping):
    # all attributes that are mappable ({**claims})
    _keys = ["is_authenticated", "user", "email", "passwordless_token", "fullname"]

    def __init__(self, token: str):
        self.jwt = decode_jwt(token)
        if self.jwt is not None:
            user_id = self.user_id
            self._user = models.User.objects.get(pk=user_id) if user_id is not None else None
        else:
            self._user = None

    def is_authenticated(self) -> bool:
        """Check if the user is authenticated.

        Returns:
            bool: True if the user is authenticated, False otherwise
        """
        return self.user and self.has_allowed_role("user_self")

    @property
    def user(self) -> models.User | None:
        """Get the user object from the claims.

        **Note**: It does not check if the user is authenticated. Use `is_authenticated` for that.

        Returns:
            Union[models.User,None]: user object
        """
        return self._user

    @property
    def user_id(self) -> int | None:
        """Get the user ID from the claims.

        Returns:
            Union[int,None]: user ID
        """
        if not self.jwt or hasura_namespace not in self.jwt:
            return None
        token = self.jwt[hasura_namespace]
        return int(token["x-hasura-user-id"]) if "x-hasura-user-id" in token else None

    def has_allowed_role(self, role: str) -> bool:
        """Check if in the token the claim with allowed roles has the specified role.
        This method does not check if the user is authenticated.

        Args:
            role (str): Role to check

        Returns:
            bool: True if the role is in the allowed roles, False otherwise
        """
        if not self.jwt or hasura_namespace not in self.jwt:
            return False
        token = self.jwt[hasura_namespace]
        return token["x-hasura-allowed-roles"] and role in token["x-hasura-allowed-roles"]

    @property
    def email(self) -> str | None:
        """Get the email from the claims or the user object.
        This method first checks the claims, then the user object.

        **Note**: It can return an email address even if the user is not authenticated.

        Returns:
            Union[str,None]: email
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
        """Get the passwordless token from the claims.

        Returns:
            Union[str,None]: passwordless token
        """
        if not self.jwt or hasura_namespace not in self.jwt:
            return None
        token = self.jwt[hasura_namespace]
        return token.get("x-passwordless-token", None)

    @property
    def fullname(self) -> str:
        """Get the fullname of the user."""
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
