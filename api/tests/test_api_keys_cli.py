from __future__ import annotations

from api.keys import _create, _revoke, main
from db.memory import InMemoryAuthRepository


def test_api_keys_cli_create_and_revoke(monkeypatch, capsys):
    repo = InMemoryAuthRepository()
    monkeypatch.setattr("api.keys.build_auth_repository", lambda: repo)

    # 1. Create key
    _create("acme-corp", 30)
    out = capsys.readouterr().out
    assert "Created API key for 'acme-corp'" in out

    keys = repo.list_api_keys()
    assert len(keys) == 1
    key_id = keys[0].id

    # 2. Revoke key
    _revoke(key_id)
    out_rev = capsys.readouterr().out
    assert "Revoked." in out_rev

    # 3. Revoke unknown key
    _revoke("unknown-id")
    out_rev2 = capsys.readouterr().out
    assert "No key with that id." in out_rev2


def test_api_keys_cli_main(monkeypatch, capsys):
    repo = InMemoryAuthRepository()
    monkeypatch.setattr("api.keys.build_auth_repository", lambda: repo)

    monkeypatch.setattr("sys.argv", ["api.keys", "create", "--client", "test-client"])
    main()
    out = capsys.readouterr().out
    assert "Created API key for 'test-client'" in out
