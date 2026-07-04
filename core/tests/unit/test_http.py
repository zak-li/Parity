from __future__ import annotations

import pytest

from core.config.settings import RuntimeConfig
from core.io.http import build_secure_session
from core.io.ssrf import HostAllowlist
from core.models.exceptions import DisallowedHostError


def test_build_secure_session_configures_retries():
    config = RuntimeConfig()
    allowlist = HostAllowlist(frozenset({"api.frankfurter.dev"}))
    session = build_secure_session(config, allowlist)

    adapter = session.get_adapter("https://api.frankfurter.dev/v1")
    assert adapter.max_retries.total == config.http_max_retries
    assert adapter.max_retries.backoff_factor == pytest.approx(config.http_backoff_factor)
    assert 429 in adapter.max_retries.status_forcelist
    assert 503 in adapter.max_retries.status_forcelist


def test_secure_session_blocks_disallowed_host_before_network():
    config = RuntimeConfig()
    allowlist = HostAllowlist(frozenset({"api.frankfurter.dev"}))
    session = build_secure_session(config, allowlist)

    with pytest.raises(DisallowedHostError):
        session.get("https://evil.example.com/steal", timeout=1)


def test_secure_session_blocks_redirect_hop_to_disallowed_host():
    import requests

    config = RuntimeConfig()
    allowlist = HostAllowlist(frozenset({"api.frankfurter.dev"}))
    session = build_secure_session(config, allowlist)

    redirect_hop = requests.Request(method="GET", url="https://evil.example.com/pwn").prepare()
    with pytest.raises(DisallowedHostError):
        session.send(redirect_hop)
