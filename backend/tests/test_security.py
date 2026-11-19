import os
import secrets
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from config import Settings, KNOWN_INSECURE_KEYS
from main import verify_api_key


def test_production_settings_validation():
    # 1. Production without API key raises ValueError and includes generation hint
    prod_no_key = Settings()
    prod_no_key.ENVIRONMENT = "production"
    prod_no_key.IS_PRODUCTION = True
    prod_no_key.FEEDPULSE_API_KEY = ""
    with pytest.raises(ValueError, match="FEEDPULSE_API_KEY must be explicitly configured") as exc_info:
        prod_no_key.validate_production_configuration()
    assert "secrets.token_urlsafe(32)" in str(exc_info.value)

    # 2. Production with weak/known key raises ValueError and includes generation hint
    for bad_key in KNOWN_INSECURE_KEYS:
        prod_bad_key = Settings()
        prod_bad_key.ENVIRONMENT = "production"
        prod_bad_key.IS_PRODUCTION = True
        prod_bad_key.FEEDPULSE_API_KEY = bad_key
        with pytest.raises(ValueError, match="known insecure development default") as exc_info:
            prod_bad_key.validate_production_configuration()
        assert "secrets.token_urlsafe(32)" in str(exc_info.value)

    # 3. Production with key shorter than 16 chars raises ValueError and includes hint
    prod_short_key = Settings()
    prod_short_key.ENVIRONMENT = "production"
    prod_short_key.IS_PRODUCTION = True
    prod_short_key.FEEDPULSE_API_KEY = "too-short-key"
    with pytest.raises(ValueError, match="at least 16 characters long") as exc_info:
        prod_short_key.validate_production_configuration()
    assert "secrets.token_urlsafe(32)" in str(exc_info.value)

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


def test_production_cors_validation():
    # 1. Wildcard origin rejected in production
    s = Settings()
    s.ENVIRONMENT = "production"
    s.IS_PRODUCTION = True
    s.FEEDPULSE_API_KEY = "super-secret-random-prod-key-12345"
    s.ALLOWED_ORIGINS = ["*"]
    with pytest.raises(ValueError, match="Wildcard origin '\\*' is not permitted"):
        s.validate_production_configuration()

    # 2. Empty origins list rejected in production
    s.ALLOWED_ORIGINS = []
    with pytest.raises(ValueError, match="ALLOWED_ORIGINS cannot be empty"):
        s.validate_production_configuration()

    # 3. Missing scheme rejected
    s.ALLOWED_ORIGINS = ["localhost:5173"]
    with pytest.raises(ValueError, match="must include an http:// or https:// scheme"):
        s.validate_production_configuration()

    # 4. Origin with URL path rejected
    s.ALLOWED_ORIGINS = ["https://feedpulse.example.com/api/v1"]
    with pytest.raises(ValueError, match="must not include paths, query parameters"):
        s.validate_production_configuration()

    # 5. Origin with query or fragment rejected
    s.ALLOWED_ORIGINS = ["https://feedpulse.example.com?foo=bar"]
    with pytest.raises(ValueError, match="must not include paths, query parameters"):
        s.validate_production_configuration()

    # 6. Valid origins succeed
    s.ALLOWED_ORIGINS = ["https://feedpulse.example.com", "http://localhost:5173", "http://127.0.0.1:3000"]
    s.validate_production_configuration()  # Should not raise


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
    assert "secrets.token_urlsafe(32)" in out

    # 2. Insecure default key
    env_insecure = os.environ.copy()
    env_insecure["ENVIRONMENT"] = "production"
    env_insecure["FEEDPULSE_API_KEY"] = "feedpulse-dev-secret-key"
    res = subprocess.run(["bash", script_path], env=env_insecure, capture_output=True, text=True, cwd=root_dir)
    assert res.returncode != 0
    out = res.stdout + res.stderr
    assert "Insecure default or weak FEEDPULSE_API_KEY detected" in out
    assert "secrets.token_urlsafe(32)" in out

    # 3. Short key (< 16 chars)
    env_short = os.environ.copy()
    env_short["ENVIRONMENT"] = "production"
    env_short["FEEDPULSE_API_KEY"] = "short-key-123"
    res = subprocess.run(["bash", script_path], env=env_short, capture_output=True, text=True, cwd=root_dir)
    assert res.returncode != 0
    out = res.stdout + res.stderr
    assert "too short" in out
    assert "secrets.token_urlsafe(32)" in out


def test_production_launcher_loads_key_from_dotenv_file():
    import subprocess
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script_path = os.path.join(root_dir, "run_production.sh")
    backend_env_path = os.path.join(root_dir, "backend", ".env")

    # Create temporary backend/.env with valid key
    valid_key = "super-secret-from-dotenv-file-99999"
    env_content = f"FEEDPULSE_API_KEY={valid_key}\n"

    existed_before = os.path.exists(backend_env_path)
    original_content = None
    if existed_before:
        with open(backend_env_path, "r") as f:
            original_content = f.read()

    try:
        with open(backend_env_path, "w") as f:
            f.write(env_content)

        env_run = os.environ.copy()
        env_run["ENVIRONMENT"] = "production"
        env_run.pop("FEEDPULSE_API_KEY", None)

        # Run script up to end of step 1 validation
        check_cmd = (
            f"bash -c 'source <(sed \"/Checking frontend build/q\" \"{script_path}\")'"
        )
        res = subprocess.run(
            check_cmd,
            shell=True,
            env=env_run,
            capture_output=True,
            text=True,
            cwd=root_dir,
        )
        assert res.returncode == 0, f"Launcher failed with .env key: {res.stderr}\nStdout: {res.stdout}"
    finally:
        if existed_before:
            with open(backend_env_path, "w") as f:
                f.write(original_content)
        else:
            if os.path.exists(backend_env_path):
                os.remove(backend_env_path)


def test_production_launcher_shell_env_overrides_dotenv():
    import subprocess
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script_path = os.path.join(root_dir, "run_production.sh")
    root_env_path = os.path.join(root_dir, ".env")

    # In .env: insecure weak key
    # In shell env: strong valid key
    existed_before = os.path.exists(root_env_path)
    original_content = None
    if existed_before:
        with open(root_env_path, "r") as f:
            original_content = f.read()

    try:
        with open(root_env_path, "w") as f:
            f.write("FEEDPULSE_API_KEY=weak-short-key\n")

        env_run = os.environ.copy()
        env_run["ENVIRONMENT"] = "production"
        env_run["FEEDPULSE_API_KEY"] = "strong-shell-override-key-12345"

        check_cmd = (
            f"bash -c 'source <(sed \"/Checking frontend build/q\" \"{script_path}\")'"
        )
        res = subprocess.run(
            check_cmd,
            shell=True,
            env=env_run,
            capture_output=True,
            text=True,
            cwd=root_dir,
        )
        assert res.returncode == 0, f"Shell override failed: {res.stderr}\nStdout: {res.stdout}"
    finally:
        if existed_before:
            with open(root_env_path, "w") as f:
                f.write(original_content)
        else:
            if os.path.exists(root_env_path):
                os.remove(root_env_path)
