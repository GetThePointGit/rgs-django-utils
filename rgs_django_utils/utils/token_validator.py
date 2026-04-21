import jwt
from django.conf import settings


def decode_jwt(token: str) -> dict | None:
    """Decode and verify an RS256-signed JWT, returning its claims dict.

    The token may carry the ``"Bearer "`` prefix (as received from HTTP
    ``Authorization`` headers); it is stripped transparently. Verification
    uses ``settings.JWT_PUBLIC_KEY`` — any failure (invalid signature,
    expired token, missing key) causes ``None`` to be returned rather than
    raised, so callers can treat "no token" and "bad token" uniformly.

    Parameters
    ----------
    token : str or None
        Raw token string, with or without ``"Bearer "`` prefix.

    Returns
    -------
    dict or None
        Decoded claims dict on success; ``None`` when *token* is falsy or
        verification fails for any reason.
    """
    if token is None:
        return None
    if token.startswith("Bearer "):
        token = token.split(" ")[1]
    try:
        return jwt.decode(
            token,
            key=settings.JWT_PUBLIC_KEY,
            algorithms=[
                "RS256",
            ],
        )
    except Exception:
        return None
