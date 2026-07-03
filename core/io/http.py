from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from ..config.settings import RuntimeConfig
from .ssrf import HostAllowlist

_RETRYABLE_STATUS = (429, 500, 502, 503, 504)


class SecureHttpSession(requests.Session):
    def __init__(self, allowlist: HostAllowlist) -> None:
        super().__init__()
        self._allowlist = allowlist

    def request(self, method, url, *args, **kwargs):
        self._allowlist.validate(url)
        return super().request(method, url, *args, **kwargs)

    def send(self, request, **kwargs):
        self._allowlist.validate(request.url)
        return super().send(request, **kwargs)


def build_secure_session(config: RuntimeConfig, allowlist: HostAllowlist) -> SecureHttpSession:
    session = SecureHttpSession(allowlist)
    retry = Retry(
        total=config.http_max_retries,
        backoff_factor=config.http_backoff_factor,
        status_forcelist=_RETRYABLE_STATUS,
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
