import jwt
from django.conf import settings


def decode_jwt(token: str) -> dict | None:
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
