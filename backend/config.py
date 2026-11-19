"""Centralized FeedPulse Application Configuration

Supported .env File Syntax:
---------------------------
- KEY=value                  # Standard unquoted key-value pair
- KEY="value with spaces"    # Double-quoted string (preserves internal whitespace)
- KEY='value with spaces'    # Single-quoted string
- KEY=                       # Empty string
- # Comment line             # Ignored
- KEY="value" # Comment      # Trailing comments stripped
- Search order: `backend/.env` then project root `.env`
- Precedence: Existing shell environment variables ALWAYS take precedence over .env files.
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv

# Search order for .env files: backend/.env then project root .env
# override=False ensures existing shell environment variables always take precedence
_backend_dir = Path(__file__).resolve().parent
_root_dir = _backend_dir.parent

for _env_path in [_backend_dir / ".env", _root_dir / ".env"]:
    if _env_path.is_file():
        load_dotenv(dotenv_path=_env_path, override=False)

KNOWN_INSECURE_KEYS = {
    "feedpulse-dev-secret-key",
    "secret",
    "password",
    "admin",
    "123456",
    "12345678",
    "changeme",
    "development",
    "test",
}

KEY_GEN_HINT = 'Generate a secure key using: python -c "import secrets; print(secrets.token_urlsafe(32))"'


class Settings:
    """
    Centralized FeedPulse Application Configuration.
    Reads environment variables with sensible defaults for local development,
    and enforces strict security validation when running in production.
    """

    def __init__(self):
        # Environment Mode
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()
        self.IS_PRODUCTION: bool = self.ENVIRONMENT == "production"

        # Server Bind
        self.HOST: str = os.getenv("HOST", "0.0.0.0" if self.IS_PRODUCTION else "127.0.0.1")
        self.PORT: int = int(os.getenv("PORT", "8000"))

        # Database
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./feedpulse.db")

        # API Security & Authentication
        # In production, require an explicit, non-default key. In development, fallback to convenience key.
        self.FEEDPULSE_API_KEY: str = os.getenv(
            "FEEDPULSE_API_KEY",
            "" if self.IS_PRODUCTION else "feedpulse-dev-secret-key"
        )

        # Read-Endpoint Security Policy
        # In production, read endpoints require API-key authentication by default
        # to prevent unauthorized scraping of customer feedback, sentiments, and alert configs.
        # In development, read access is open by default for local exploration,
        # but can be enforced by setting REQUIRE_READ_AUTH=true.
        self.REQUIRE_READ_AUTH: bool = os.getenv(
            "REQUIRE_READ_AUTH",
            "true" if self.IS_PRODUCTION else "false"
        ).lower() in ("true", "1", "yes")

        # CORS Allowed Origins
        _raw_origins = os.getenv(
            "ALLOWED_ORIGINS",
            os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000")
        )
        self.ALLOWED_ORIGINS: List[str] = [orig.strip() for orig in _raw_origins.split(",") if orig.strip()]

        # Destructive Action Safety
        # In production, seeding is disabled by default unless explicitly allowed
        self.ALLOW_DEMO_SEEDING: bool = os.getenv(
            "ALLOW_DEMO_SEEDING",
            "false" if self.IS_PRODUCTION else "true"
        ).lower() in ("true", "1", "yes")

        # CSV Upload Constraints
        self.MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(5 * 1024 * 1024)))  # 5 MB
        self.MAX_UPLOAD_ROWS: int = int(os.getenv("MAX_UPLOAD_ROWS", "5000"))
        self.MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", "2000"))

        # Slack Integration Defaults
        self.DEFAULT_SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
        self.DEFAULT_NEGATIVE_THRESHOLD_PCT: float = float(os.getenv("NEGATIVE_THRESHOLD_PCT", "30.0"))

        # Backup Directory
        self.BACKUP_DIR: str = os.getenv("BACKUP_DIR", os.path.join(str(_backend_dir), "backups"))
        self.BACKUP_RETENTION_COUNT: int = int(os.getenv("BACKUP_RETENTION_COUNT", "10"))

    def validate_production_configuration(self) -> None:
        """
        Validates critical security settings for production environments.
        Raises ValueError with an actionable message if any requirement fails.
        """
        if not self.IS_PRODUCTION:
            return

        key = (self.FEEDPULSE_API_KEY or "").strip()
        if not key:
            raise ValueError(
                "CRITICAL CONFIGURATION ERROR: In production mode (ENVIRONMENT=production), "
                "FEEDPULSE_API_KEY must be explicitly configured via environment variable. "
                f"It cannot be empty or omitted. {KEY_GEN_HINT}"
            )

        if key.lower() in KNOWN_INSECURE_KEYS:
            raise ValueError(
                f"CRITICAL CONFIGURATION ERROR: The configured FEEDPULSE_API_KEY ('{key}') is a known "
                f"insecure development default. In production, configure a dedicated, high-entropy secret key. {KEY_GEN_HINT}"
            )

        if len(key) < 16:
            raise ValueError(
                f"CRITICAL CONFIGURATION ERROR: FEEDPULSE_API_KEY length is {len(key)} characters. "
                f"Production keys must be at least 16 characters long. {KEY_GEN_HINT}"
            )

        # CORS Allowed Origins validation in production
        if not self.ALLOWED_ORIGINS:
            raise ValueError(
                "CRITICAL CONFIGURATION ERROR: In production mode (ENVIRONMENT=production), "
                "ALLOWED_ORIGINS cannot be empty. Specify at least one trusted origin URL (e.g. 'https://yourdomain.com')."
            )

        if "*" in self.ALLOWED_ORIGINS:
            raise ValueError(
                "CRITICAL CONFIGURATION ERROR: Wildcard origin '*' is not permitted in production "
                "when credentials are enabled. Specify explicit trusted origin URLs."
            )

        for origin in self.ALLOWED_ORIGINS:
            parsed = urlparse(origin)
            if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
                raise ValueError(
                    f"CRITICAL CONFIGURATION ERROR: Invalid CORS origin '{origin}'. "
                    "Allowed origins must include an http:// or https:// scheme and host (e.g. 'https://feedpulse.example.com')."
                )
            if (parsed.path and parsed.path != "/") or parsed.params or parsed.query or parsed.fragment:
                raise ValueError(
                    f"CRITICAL CONFIGURATION ERROR: Invalid CORS origin '{origin}'. "
                    f"Allowed origins must not include paths, query parameters, or URL fragments (e.g. use 'https://example.com' instead of '{origin}')."
                )


settings = Settings()


def validate_slack_webhook_url(url: Optional[str]) -> bool:
    """
    Validates a Slack incoming webhook URL:
    - Must be valid HTTPS URL
    - Hostname must be strictly 'hooks.slack.com'
    - Path must match standard Slack webhook format: /services/T.../B.../...
    """
    if not url or not url.strip():
        return False

    url_str = url.strip()
    try:
        parsed = urlparse(url_str)
        if parsed.scheme.lower() != "https":
            return False
        if parsed.netloc.lower() != "hooks.slack.com":
            return False

        # Slack webhook path format: /services/T[A-Z0-9_]+/B[A-Z0-9_]+/[A-Za-z0-9_-]+
        slack_path_pattern = re.compile(r"^/services/T[A-Z0-9_]+/B[A-Z0-9_]+/[A-Za-z0-9_-]+$")
        return bool(slack_path_pattern.match(parsed.path))
    except Exception:
        return False


def mask_slack_webhook(url: Optional[str]) -> Optional[str]:
    """
    Masks a webhook URL to avoid exposing secret tokens in API responses or logs.
    Example: https://hooks.slack.com/services/T123/B456/abcdef... -> https://hooks.slack.com/services/T***/B***/******
    """
    if not url or not url.strip():
        return ""
    if not validate_slack_webhook_url(url):
        return "https://hooks.slack.com/services/****/****/****"

    parts = url.strip().split("/")
    if len(parts) >= 7:
        team = parts[4][:2] + "***" if len(parts[4]) >= 2 else "***"
        bot = parts[5][:2] + "***" if len(parts[5]) >= 2 else "***"
        return f"https://hooks.slack.com/services/{team}/{bot}/******"
    return "https://hooks.slack.com/services/****/****/****"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FeedPulse Configuration Utility")
    parser.add_argument("--validate-production", action="store_true", help="Validate production settings")
    parser.add_argument("--dump-env", action="store_true", help="Dump loaded configuration as key-value pairs")
    args = parser.parse_args()

    if args.validate_production:
        try:
            settings.validate_production_configuration()
            print("OK: Production configuration is valid.")
            sys.exit(0)
        except Exception as exc:
            print(f"{exc}", file=sys.stderr)
            sys.exit(1)
    elif args.dump_env:
        print(f"ENVIRONMENT={settings.ENVIRONMENT}")
        print(f"HOST={settings.HOST}")
        print(f"PORT={settings.PORT}")
        print(f"DATABASE_URL={settings.DATABASE_URL}")
        print(f"REQUIRE_READ_AUTH={settings.REQUIRE_READ_AUTH}")
        print(f"ALLOW_DEMO_SEEDING={settings.ALLOW_DEMO_SEEDING}")
        print(f"ALLOWED_ORIGINS={','.join(settings.ALLOWED_ORIGINS)}")
