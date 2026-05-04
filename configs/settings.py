"""Project settings loaded from environment variables and .env."""

from __future__ import annotations

import os
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ---- LLM ----
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))

    # ---- Sandbox ----
    SANDBOX_TYPE: str = os.getenv("SANDBOX_TYPE", "subprocess")
    SANDBOX_TIMEOUT: int = int(os.getenv("SANDBOX_TIMEOUT", "30"))
    SANDBOX_MEMORY_MB: int = int(os.getenv("SANDBOX_MEMORY_MB", "512"))
    SANDBOX_MAX_MEMORY_MB: int = int(os.getenv("SANDBOX_MAX_MEMORY_MB", "512"))
    SANDBOX_CPU_QUOTA: float = float(os.getenv("SANDBOX_CPU_QUOTA", "1.0"))
    SANDBOX_IMAGE: str = os.getenv("SANDBOX_IMAGE", "multiagent-sandbox:latest")

    # ---- Checkpointing ----
    POSTGRES_URI: str = os.getenv(
        "POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/langgraph",
    )
    CHECKPOINTER_TYPE: str = os.getenv("CHECKPOINTER_TYPE", "postgres")

    # ---- Paths ----
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    OUTPUT_DIR: Path = DATA_DIR / "outputs"

    # ---- Logging ----
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ---- SQL validation ----
    SQL_VALIDATOR_MODE: str = os.getenv("SQL_VALIDATOR_MODE", "production").lower()
    SQL_VALIDATOR_ALLOW_DEV_FALLBACK: bool = (
        os.getenv("SQL_VALIDATOR_ALLOW_DEV_FALLBACK", "false").lower() == "true"
    )
    SQL_VALIDATOR_ALLOW_DETAIL_QUERY: bool = (
        os.getenv("SQL_VALIDATOR_ALLOW_DETAIL_QUERY", "false").lower() == "true"
    )

    # ---- IAM / SSO ----
    # local: use semantic_users table for development.
    # oidc: verify Bearer/access_token JWT and map external claims to app roles.
    IAM_AUTH_MODE: str = os.getenv("IAM_AUTH_MODE", "local").lower()
    IAM_ALLOW_DEV_FALLBACK: bool = os.getenv("IAM_ALLOW_DEV_FALLBACK", "true").lower() == "true"
    IAM_OIDC_ISSUER: str = os.getenv("IAM_OIDC_ISSUER", "")
    IAM_OIDC_AUDIENCE: str = os.getenv("IAM_OIDC_AUDIENCE", "")
    IAM_OIDC_JWKS_URL: str = os.getenv("IAM_OIDC_JWKS_URL", "")
    IAM_JWT_ALGORITHMS: list[str] = [
        item.strip()
        for item in os.getenv("IAM_JWT_ALGORITHMS", "RS256").split(",")
        if item.strip()
    ]
    IAM_JWT_HS256_SECRET: str = os.getenv("IAM_JWT_HS256_SECRET", "")
    IAM_USER_CLAIM: str = os.getenv("IAM_USER_CLAIM", "sub")
    IAM_DISPLAY_NAME_CLAIM: str = os.getenv("IAM_DISPLAY_NAME_CLAIM", "name")
    IAM_TEAM_CLAIM: str = os.getenv("IAM_TEAM_CLAIM", "team")
    IAM_ROLES_CLAIM: str = os.getenv("IAM_ROLES_CLAIM", "roles")
    IAM_GROUPS_CLAIM: str = os.getenv("IAM_GROUPS_CLAIM", "groups")
    IAM_ALLOW_UNMAPPED_ROLES: bool = os.getenv("IAM_ALLOW_UNMAPPED_ROLES", "false").lower() == "true"
    IAM_ROLE_MAPPING: dict[str, str] = json.loads(os.getenv("IAM_ROLE_MAPPING_JSON", "{}") or "{}")
    IAM_DEFAULT_ROLES: list[str] = json.loads(os.getenv("IAM_DEFAULT_ROLES_JSON", "[]") or "[]")

    def __init__(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        errors = []
        if not self.DEEPSEEK_API_KEY:
            errors.append("DEEPSEEK_API_KEY is not configured.")
        if self.IAM_AUTH_MODE == "oidc":
            if not (self.IAM_OIDC_JWKS_URL or self.IAM_JWT_HS256_SECRET):
                errors.append("IAM_AUTH_MODE=oidc requires IAM_OIDC_JWKS_URL or IAM_JWT_HS256_SECRET.")
            if not self.IAM_OIDC_ISSUER:
                errors.append("IAM_AUTH_MODE=oidc requires IAM_OIDC_ISSUER.")
            if not self.IAM_OIDC_AUDIENCE:
                errors.append("IAM_AUTH_MODE=oidc requires IAM_OIDC_AUDIENCE.")
        if self.SQL_VALIDATOR_MODE not in {"production", "development"}:
            errors.append("SQL_VALIDATOR_MODE must be production or development.")
        return errors


settings = Settings()
