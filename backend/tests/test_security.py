import os
import secrets
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from config import Settings, KNOWN_INSECURE_KEYS
from main import verify_api_key


def test_production_settings_validation():
    # 1. Production without API key raises ValueError
    prod_no_key = Settings()
    prod_no_key.ENVIRONMENT = "production"
    prod_no_key.IS_PRODUCTION = True
    prod_no_key.FEEDPULSE_API_KEY = ""
    with pytest.raises(ValueError, match="FEEDPULSE_API_KEY must be explicitly configured"):
        prod_no_key.validate_production_configuration()

    # 2. Production with weak/known key raises ValueError
    for bad_key in KNOWN_INSECURE_KEYS:
        prod_bad_key = Settings()
        prod_bad_key.ENVIRONMENT = "production"
        prod_bad_key.IS_PRODUCTION = True
        prod_bad_key.FEEDPULSE_API_KEY = bad_key
        with pytest.raises(ValueError, match="known insecure development default"):
            prod_bad_key.validate_production_configuration()

    # 3. Production with key shorter than 16 chars raises ValueError
    prod_short_key = Settings()
    prod_short_key.ENVIRONMENT = "production"
    prod_short_key.IS_PRODUCTION = True
    prod_short_key.FEEDPULSE_API_KEY = "too-short-key"
    with pytest.raises(ValueError, match="at least 16 characters long"):
        prod_short_key.validate_production_configuration()

    # 4. Production with strong key (>= 16 chars) succeeds
    prod_strong_key = Settings()
    prod_strong_key.ENVIRONMENT = "production"
    prod_strong_key.IS_PRODUCTION = True
    prod_strong_key.FEEDPULSE_API_KEY = "super-secret-random-prod-key-12345"
    prod_strong_key.validate_production_configuration()  # Should not raise

    # 5. Development mode succeeds with default key
    dev_settings = Settings()
    dev_settings.ENVIRONMENT = "development"
    dev_settings.IS_PRODUCTION = False
    dev_settings.FEEDPULSE_API_KEY = "feedpulse-dev-secret-key"
    dev_settings.validate_production_configuration()  # Should not raise


def test_constant_time_api_key_verification():
    expected_secret = "test-secret-key-12345678"

    with patch("main.settings.FEEDPULSE_API_KEY", expected_secret):
        # 1. Valid via X-API-Key
        assert verify_api_key(x_api_key=expected_secret, authorization=None) is True

        # 2. Valid via Authorization: Bearer
        assert verify_api_key(x_api_key=None, authorization=f"Bearer {expected_secret}") is True

        # 3. Valid via lowercase bearer
        assert verify_api_key(x_api_key=None, authorization=f"bearer {expected_secret}") is True

        # 4. Missing credentials raises 401
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(x_api_key=None, authorization=None)
        assert exc_info.value.status_code == 401

        # 5. Invalid credentials raises 401
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(x_api_key="wrong-key", authorization=None)
        assert exc_info.value.status_code == 401

        # 6. Malformed Authorization header raises 401
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(x_api_key=None, authorization="Bearer")
        assert exc_info.value.status_code == 401

        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(x_api_key=None, authorization="Basic some-token")
        assert exc_info.value.status_code == 401


def test_secrets_compare_digest_is_used():
    """Confirms that constant-time compare_digest is actively invoked during verification."""
    expected_secret = "my-secure-expected-key-999"
    with patch("main.settings.FEEDPULSE_API_KEY", expected_secret), \
         patch("secrets.compare_digest", wraps=secrets.compare_digest) as mock_compare:
        verify_api_key(x_api_key=expected_secret, authorization=None)
        assert mock_compare.called
        assert mock_compare.call_args[0] == (expected_secret, expected_secret)


def test_production_launcher_rejects_insecure_config():
    import subprocess
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script_path = os.path.join(root_dir, "run_production.sh")

    # 1. Missing key
    env_missing = os.environ.copy()
    env_missing["ENVIRONMENT"] = "production"
    env_missing["FEEDPULSE_API_KEY"] = ""
    res = subprocess.run(["bash", script_path], env=env_missing, capture_output=True, text=True, cwd=root_dir)
    assert res.returncode != 0
    out = res.stdout + res.stderr
    assert "FEEDPULSE_API_KEY environment variable is required" in out

    # 2. Insecure default key
    env_insecure = os.environ.copy()
    env_insecure["ENVIRONMENT"] = "production"
    env_insecure["FEEDPULSE_API_KEY"] = "feedpulse-dev-secret-key"
    res = subprocess.run(["bash", script_path], env=env_insecure, capture_output=True, text=True, cwd=root_dir)
    assert res.returncode != 0
    out = res.stdout + res.stderr
    assert "Insecure default or weak FEEDPULSE_API_KEY detected" in out

    # 3. Short key (< 16 chars)
    env_short = os.environ.copy()
    env_short["ENVIRONMENT"] = "production"
    env_short["FEEDPULSE_API_KEY"] = "short-key-123"
    res = subprocess.run(["bash", script_path], env=env_short, capture_output=True, text=True, cwd=root_dir)
    assert res.returncode != 0
    out = res.stdout + res.stderr
    assert "too short" in out
