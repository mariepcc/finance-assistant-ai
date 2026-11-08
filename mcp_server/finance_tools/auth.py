from uuid import UUID

from app.config import Settings
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token


def build_verifier(settings: Settings) -> JWTVerifier:
    if settings.supabase_jwt_secret:
        return JWTVerifier(
            public_key=settings.supabase_jwt_secret,
            algorithm="HS256",
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    return JWTVerifier(
        jwks_uri=settings.jwks_uri,
        algorithm="ES256",
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )


def current_user_id() -> UUID:
    token = get_access_token()
    sub = token.claims.get("sub") if token is not None else None
    if not sub:
        raise ToolError("Brak uwierzytelnionego użytkownika")
    try:
        return UUID(str(sub))
    except ValueError as exc:
        raise ToolError("Nieprawidłowy identyfikator użytkownika w tokenie") from exc
