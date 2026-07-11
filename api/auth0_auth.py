from __future__ import annotations

import jwt
from jwt import PyJWKClient

from core.config import RuntimeConfig
from core.models.exceptions import SecurityError


class Auth0Authenticator:
    def __init__(self, config: RuntimeConfig):
        self._domain = config.auth0_domain
        self._client_id = config.auth0_client_id
        self._audience = config.auth0_audience

        if self._domain:
            # Auth0 JWKS endpoint
            jwks_url = f"https://{self._domain}/.well-known/jwks.json"
            self._jwks_client = PyJWKClient(jwks_url)
        else:
            self._jwks_client = None

    def is_enabled(self) -> bool:
        return bool(self._domain and self._client_id)

    def verify_token(self, token: str) -> dict:
        if not self.is_enabled():
            raise SecurityError("Auth0 authentication is not configured.")

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=f"https://{self._domain}/",
            )

            # Signature, audience, issuer and expiry are already enforced by
            # jwt.decode above. When the token carries an authorized-party claim
            # (`azp`), it must additionally match our configured Client ID.
            azp = payload.get("azp")
            if azp is not None and azp != self._client_id:
                raise SecurityError("Token was not issued for this Client ID.")

            return payload

        except jwt.PyJWKClientError as exc:
            raise SecurityError("Failed to fetch public keys from Auth0.") from exc
        except jwt.ExpiredSignatureError as exc:
            raise SecurityError("Auth0 token has expired.") from exc
        except jwt.InvalidTokenError as exc:
            raise SecurityError(f"Invalid Auth0 token: {exc}") from exc
