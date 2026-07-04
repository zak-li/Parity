from __future__ import annotations

import os
import sys

import pytest

from core.config.settings import RuntimeConfig, load_runtime_config


@pytest.fixture
def clean_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("XI_"):
            monkeypatch.delenv(key, raising=False)
    yield
    for key in list(os.environ):
        if key.startswith("XI_"):
            monkeypatch.delenv(key, raising=False)


def test_defaults_are_applied_without_env(clean_env):
    config = load_runtime_config(use_dotenv=False)
    assert config.http_timeout_seconds == pytest.approx(10.0)
    assert config.http_max_retries == 3
    assert "api.frankfurter.dev" in config.allowed_fx_hosts


def test_env_overrides_are_parsed(monkeypatch):
    monkeypatch.setenv("XI_HTTP_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("XI_HTTP_MAX_RETRIES", "5")
    monkeypatch.setenv("XI_ALLOWED_FX_HOSTS", "a.example.com, b.example.com")

    config = RuntimeConfig()
    assert config.http_timeout_seconds == pytest.approx(3.5)
    assert config.http_max_retries == 5
    assert config.allowed_fx_hosts == frozenset({"a.example.com", "b.example.com"})


def test_invalid_float_env_raises(monkeypatch):
    monkeypatch.setenv("XI_HTTP_TIMEOUT_SECONDS", "not-a-float")
    with pytest.raises(ValueError):
        RuntimeConfig()


def test_below_minimum_env_raises(monkeypatch):
    monkeypatch.setenv("XI_HTTP_MAX_RETRIES", "-1")
    with pytest.raises(ValueError):
        RuntimeConfig()


def test_invalid_int_env_raises(monkeypatch):
    monkeypatch.setenv("XI_HTTP_MAX_RETRIES", "not-an-int")
    with pytest.raises(ValueError):
        RuntimeConfig()


def test_empty_hosts_env_raises(monkeypatch):
    monkeypatch.setenv("XI_ALLOWED_FX_HOSTS", "  ,  ")
    with pytest.raises(ValueError):
        RuntimeConfig()


def test_dotenv_file_values_are_loaded(tmp_path, clean_env):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "XI_HTTP_TIMEOUT_SECONDS=7.5\nXI_ALLOWED_FX_HOSTS=a.example.com,b.example.com\n",
        encoding="utf-8",
    )

    config = load_runtime_config(env_file=env_file)

    assert config.http_timeout_seconds == pytest.approx(7.5)
    assert config.allowed_fx_hosts == frozenset({"a.example.com", "b.example.com"})


def test_real_environment_takes_precedence_over_dotenv(tmp_path, clean_env, monkeypatch):
    monkeypatch.setenv("XI_HTTP_TIMEOUT_SECONDS", "3.0")
    env_file = tmp_path / ".env"
    env_file.write_text("XI_HTTP_TIMEOUT_SECONDS=7.5\n", encoding="utf-8")

    config = load_runtime_config(env_file=env_file)

    assert config.http_timeout_seconds == pytest.approx(3.0)


def test_dotenv_can_be_disabled(tmp_path, clean_env):
    env_file = tmp_path / ".env"
    env_file.write_text("XI_HTTP_TIMEOUT_SECONDS=7.5\n", encoding="utf-8")

    config = load_runtime_config(env_file=env_file, use_dotenv=False)

    assert config.http_timeout_seconds == pytest.approx(10.0)


def test_below_minimum_float_env_raises(monkeypatch):
    monkeypatch.setenv("XI_HTTP_TIMEOUT_SECONDS", "0.0")
    with pytest.raises(ValueError):
        RuntimeConfig()


def test_empty_env_file_path_is_ignored(clean_env):
    config = load_runtime_config(env_file="")
    assert config.http_timeout_seconds == pytest.approx(10.0)


def test_gracefully_degrades_when_dotenv_not_installed(tmp_path, clean_env, monkeypatch):
    monkeypatch.setitem(sys.modules, "dotenv", None)
    env_file = tmp_path / ".env"
    env_file.write_text("XI_HTTP_TIMEOUT_SECONDS=7.5\n", encoding="utf-8")

    config = load_runtime_config(env_file=env_file)

    assert config.http_timeout_seconds == pytest.approx(10.0)
