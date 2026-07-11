from unittest.mock import MagicMock, patch

import jwt
import pytest

from api.auth0_auth import Auth0Authenticator
from core.config import RuntimeConfig
from core.models.exceptions import SecurityError


def test_auth0_authenticator_disabled():
    config = RuntimeConfig(auth0_domain=None, auth0_client_id=None)
    auth = Auth0Authenticator(config)
    assert not auth.is_enabled()
    with pytest.raises(SecurityError, match="Auth0 authentication is not configured."):
        auth.verify_token("any_token")


def test_auth0_authenticator_verify_success():
    config = RuntimeConfig(
        auth0_domain="test.auth0.com", auth0_client_id="my_client", auth0_audience="api://default"
    )
    auth = Auth0Authenticator(config)
    assert auth.is_enabled()

    # Mock PyJWKClient
    mock_key = MagicMock()
    mock_key.key = "fake_key"

    with patch("jwt.PyJWKClient.get_signing_key_from_jwt", return_value=mock_key):
        with patch("jwt.decode", return_value={"sub": "user@test.com", "azp": "my_client"}):
            payload = auth.verify_token("fake_token")
            assert payload["sub"] == "user@test.com"


def test_auth0_authenticator_invalid_client():
    config = RuntimeConfig(auth0_domain="test.auth0.com", auth0_client_id="my_client")
    auth = Auth0Authenticator(config)

    mock_key = MagicMock()
    mock_key.key = "fake_key"

    with patch("jwt.PyJWKClient.get_signing_key_from_jwt", return_value=mock_key):
        with patch("jwt.decode", return_value={"sub": "user@test.com", "azp": "wrong_client"}):
            with pytest.raises(SecurityError, match="Token was not issued for this Client ID."):
                auth.verify_token("fake_token")


def test_auth0_authenticator_expired_token():
    config = RuntimeConfig(auth0_domain="test.auth0.com", auth0_client_id="my_client")
    auth = Auth0Authenticator(config)

    mock_key = MagicMock()
    mock_key.key = "fake_key"

    with patch("jwt.PyJWKClient.get_signing_key_from_jwt", return_value=mock_key):
        with patch("jwt.decode", side_effect=jwt.ExpiredSignatureError("Expired")):
            with pytest.raises(SecurityError, match="Auth0 token has expired."):
                auth.verify_token("fake_token")
