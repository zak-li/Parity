from __future__ import annotations

import pytest

from core.io.ssrf import HostAllowlist
from core.models.exceptions import DisallowedHostError


def test_allows_whitelisted_https_host():
    allowlist = HostAllowlist(frozenset({"api.frankfurter.dev"}))
    allowlist.validate("https://api.frankfurter.dev/v1/2026-01-01")


def test_rejects_non_whitelisted_host():
    allowlist = HostAllowlist(frozenset({"api.frankfurter.dev"}))
    with pytest.raises(DisallowedHostError):
        allowlist.validate("https://evil.example.com/steal")


def test_rejects_non_https_scheme_by_default():
    allowlist = HostAllowlist(frozenset({"api.frankfurter.dev"}))
    with pytest.raises(DisallowedHostError):
        allowlist.validate("http://api.frankfurter.dev/v1")


def test_rejects_ssrf_style_internal_target():
    allowlist = HostAllowlist(frozenset({"api.frankfurter.dev"}))
    with pytest.raises(DisallowedHostError):
        allowlist.validate("http://169.254.169.254/latest/meta-data/")


def test_host_matching_is_case_insensitive():
    allowlist = HostAllowlist(frozenset({"API.Frankfurter.DEV"}))
    allowlist.validate("https://api.frankfurter.dev/v1")


def test_allows_http_when_https_not_required():
    allowlist = HostAllowlist(frozenset({"localhost"}), require_https=False)
    allowlist.validate("http://localhost:8000/health")


def test_rejects_empty_allowlist():
    with pytest.raises(ValueError):
        HostAllowlist(frozenset())
