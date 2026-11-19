import os
import re
from urllib.parse import urlparse
from typing import List, Optional

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class Settings:
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()
    IS_PRODUCTION: bool = ENVIRONMENT == "production"

    # Server Bind
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./feedpulse.db")

    # API Security & Authentication
    # Default key provided for frictionless student/dev setup, customizable for deployment
    FEEDPULSE_API_KEY: str = os.getenv("FEEDPULSE_API_KEY", "feedpulse-dev-secret-key")

    # CORS Allowed Origins
    _raw_origins = os.getenv(
        "ALLOWED_ORIGINS",
        os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000")
    )
    ALLOWED_ORIGINS: List[str] = [orig.strip() for orig in _raw_origins.split(",") if orig.strip()]

    # Destructive Action Safety
    # In production, seeding is disabled by default unless explicitly allowed
    ALLOW_DEMO_SEEDING: bool = os.getenv(
        "ALLOW_DEMO_SEEDING",
        "false" if IS_PRODUCTION else "true"
    ).lower() in ("true", "1", "yes")

    # CSV Upload Constraints
    MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(5 * 1024 * 1024)))  # 5 MB
    MAX_UPLOAD_ROWS: int = int(os.getenv("MAX_UPLOAD_ROWS", "5000"))
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", "2000"))

    # Slack Integration Defaults
    DEFAULT_SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    DEFAULT_NEGATIVE_THRESHOLD_PCT: float = float(os.getenv("NEGATIVE_THRESHOLD_PCT", "30.0"))

    # Backup Directory
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", os.path.join(os.path.dirname(__file__), "backups"))
    BACKUP_RETENTION_COUNT: int = int(os.getenv("BACKUP_RETENTION_COUNT", "10"))


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

        # Slack webhook path format: /services/T[A-Z0-9_]+/B[A-Z0-9_]+/[A-Za-z0-9_]+
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
