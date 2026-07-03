from __future__ import annotations

from urllib.parse import urlsplit

from ..models.exceptions import DisallowedHostError


class HostAllowlist:
    def __init__(self, allowed_hosts: frozenset[str], *, require_https: bool = True) -> None:
        if not allowed_hosts:
            raise ValueError("La liste d'hôtes autorisés ne peut pas être vide.")
        self._allowed_hosts = frozenset(h.lower() for h in allowed_hosts)
        self._require_https = require_https

    def validate(self, url: str) -> None:
        parts = urlsplit(url)
        if self._require_https and parts.scheme != "https":
            raise DisallowedHostError(f"Schéma non autorisé: {parts.scheme!r}. HTTPS obligatoire.")
        host = (parts.hostname or "").lower()
        if host not in self._allowed_hosts:
            raise DisallowedHostError(f"Hôte non autorisé: {host!r}.")

    @property
    def allowed_hosts(self) -> frozenset[str]:
        return self._allowed_hosts
