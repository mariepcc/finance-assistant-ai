from dataclasses import dataclass, field
from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: UUID
    email: str | None
    access_token: str = field(default="", repr=False)


@lru_cache
def _jwks_client(jwks_uri: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_uri)


async def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    if settings.supabase_jwt_secret:
        key: Any = settings.supabase_jwt_secret
        algorithms = ["HS256"]
    else:
        signing_key = await run_in_threadpool(
            _jwks_client(settings.jwks_uri).get_signing_key_from_jwt, token
        )
        key = signing_key.key
        algorithms = ["ES256", "RS256"]
    claims: dict[str, Any] = jwt.decode(
        token,
        key,
        algorithms=algorithms,
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "sub", "aud", "iss"]},
    )
    return claims


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nieprawidłowy lub brakujący token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = await decode_token(credentials.credentials, settings)
        return CurrentUser(
            id=UUID(claims["sub"]),
            email=claims.get("email"),
            access_token=credentials.credentials,
        )
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise unauthorized from exc


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
