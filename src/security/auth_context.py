"""Trusted auth context resolution.

Production mode verifies OIDC/JWT tokens server-side and maps external claims
to internal semantic roles. Local mode uses the SQLite semantic_users table for
development. Frontend-supplied roles are never trusted.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from configs.settings import settings
from src.persistence.semantic_store import SemanticStore


class AuthError(Exception):
    """Raised when IAM/SSO authentication fails."""


@dataclass
class AuthContext:
    user_id: str
    display_name: str
    team: str
    roles: list[str]
    source: str = "iam"
    authenticated: bool = True
    claims: dict[str, Any] | None = None

    def to_state(self) -> dict:
        data = asdict(self)
        # Do not put raw claims into graph state by default; they may contain PII.
        data.pop("claims", None)
        return data


def resolve_auth_context(user_id: str | None = None, token: str | None = None) -> AuthContext:
    if settings.IAM_AUTH_MODE == "oidc":
        if token:
            claims = verify_oidc_token(token)
            return _auth_from_claims(claims)
        if settings.IAM_ALLOW_DEV_FALLBACK:
            return _resolve_local_user(user_id)
        raise AuthError("OIDC token is required.")

    return _resolve_local_user(user_id)


def verify_oidc_token(token: str) -> dict[str, Any]:
    if settings.IAM_JWT_HS256_SECRET:
        return _verify_hs256_token(token)
    return _verify_jwks_token(token)


def _verify_jwks_token(token: str) -> dict[str, Any]:
    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError as exc:
        raise AuthError(
            "PyJWT[crypto] is required for OIDC JWKS verification. "
            "Install backend requirements before enabling IAM_AUTH_MODE=oidc."
        ) from exc

    if not settings.IAM_OIDC_JWKS_URL:
        raise AuthError("IAM_OIDC_JWKS_URL is not configured.")

    try:
        jwks_client = PyJWKClient(settings.IAM_OIDC_JWKS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=settings.IAM_JWT_ALGORITHMS,
            audience=settings.IAM_OIDC_AUDIENCE,
            issuer=settings.IAM_OIDC_ISSUER,
        )
    except Exception as exc:
        raise AuthError(f"OIDC token verification failed: {exc}") from exc
    return dict(claims)


def _verify_hs256_token(token: str) -> dict[str, Any]:
    header, payload, signature = _split_jwt(token)
    if header.get("alg") != "HS256":
        raise AuthError("Only HS256 tokens are accepted when IAM_JWT_HS256_SECRET is used.")
    if "HS256" not in settings.IAM_JWT_ALGORITHMS:
        raise AuthError("HS256 is not enabled in IAM_JWT_ALGORITHMS.")

    signing_input = ".".join(token.split(".")[:2]).encode("utf-8")
    expected = hmac.new(
        settings.IAM_JWT_HS256_SECRET.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    actual = _base64url_decode(signature)
    if not hmac.compare_digest(expected, actual):
        raise AuthError("OIDC token signature verification failed.")

    _validate_standard_claims(payload)
    return payload


def _validate_standard_claims(claims: dict[str, Any]) -> None:
    now = int(time.time())
    exp = claims.get("exp")
    if exp is not None and int(exp) <= now:
        raise AuthError("OIDC token expired.")
    nbf = claims.get("nbf")
    if nbf is not None and int(nbf) > now:
        raise AuthError("OIDC token is not yet valid.")
    issuer = claims.get("iss")
    if settings.IAM_OIDC_ISSUER and issuer != settings.IAM_OIDC_ISSUER:
        raise AuthError("OIDC issuer mismatch.")
    audience = claims.get("aud")
    expected_aud = settings.IAM_OIDC_AUDIENCE
    if expected_aud:
        if isinstance(audience, list):
            aud_ok = expected_aud in audience
        else:
            aud_ok = audience == expected_aud
        if not aud_ok:
            raise AuthError("OIDC audience mismatch.")


def _auth_from_claims(claims: dict[str, Any]) -> AuthContext:
    external_values = _claim_values(claims, settings.IAM_ROLES_CLAIM) + _claim_values(claims, settings.IAM_GROUPS_CLAIM)
    mapped_roles = _map_external_roles(external_values)
    roles = sorted(set(mapped_roles + settings.IAM_DEFAULT_ROLES))
    user_id = str(claims.get(settings.IAM_USER_CLAIM) or claims.get("sub") or "")
    if not user_id:
        raise AuthError("OIDC token does not contain a user id claim.")
    return AuthContext(
        user_id=user_id,
        display_name=str(claims.get(settings.IAM_DISPLAY_NAME_CLAIM) or user_id),
        team=str(claims.get(settings.IAM_TEAM_CLAIM) or "default"),
        roles=roles,
        source="oidc",
        authenticated=True,
        claims=claims,
    )


def _map_external_roles(values: list[str]) -> list[str]:
    mapped: list[str] = []
    for value in values:
        if value in settings.IAM_ROLE_MAPPING:
            mapped.append(settings.IAM_ROLE_MAPPING[value])
        elif settings.IAM_ALLOW_UNMAPPED_ROLES:
            mapped.append(value)
    return mapped


def _claim_values(claims: dict[str, Any], claim_name: str) -> list[str]:
    if not claim_name:
        return []
    value = claims.get(claim_name)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value)]


def _resolve_local_user(user_id: str | None) -> AuthContext:
    use_dev_default = user_id is None or not str(user_id).strip()
    requested_user = "demo_sales" if use_dev_default else str(user_id).strip()
    store = SemanticStore()
    user = store.get_user(requested_user)
    if not user:
        return _anonymous(requested_user if requested_user else "anonymous", source="local_unknown_user")
    return AuthContext(
        user_id=user["user_id"],
        display_name=user.get("display_name", user["user_id"]),
        team=user.get("team", "default"),
        roles=user.get("roles", []),
        source="semantic_users",
        authenticated=True,
    )


def _anonymous(user_id: str, source: str) -> AuthContext:
    return AuthContext(
        user_id=user_id,
        display_name=user_id,
        team="default",
        roles=[],
        source=source,
        authenticated=False,
    )


def _split_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("Invalid JWT format.")
    header = json.loads(_base64url_decode(parts[0]).decode("utf-8"))
    payload = json.loads(_base64url_decode(parts[1]).decode("utf-8"))
    return header, payload, parts[2]


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))
