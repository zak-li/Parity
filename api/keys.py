"""Manage API keys from the command line.

    python -m api.keys create --client acme [--days 90]
    python -m api.keys revoke --id <key-id>

Keys are stored (hashed) in the configured auth repository — set
``XI_POSTGRES_DSN`` so they survive process restarts. The plaintext key is
printed once on creation and never again.
"""

from __future__ import annotations

import argparse
import datetime as dt

from api.security import generate_api_key
from db import build_auth_repository


def _create(client: str, days: int | None) -> None:
    expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(days=days) if days is not None else None
    plaintext, record = generate_api_key(client, expires_at)
    build_auth_repository().save_api_key(record)
    print(f"Created API key for '{client}' (id={record.id}, prefix={record.prefix}).")
    print(f"  {plaintext}")
    print("Store it now — it will not be shown again.")


def _revoke(key_id: str) -> None:
    ok = build_auth_repository().revoke_api_key(key_id)
    print("Revoked." if ok else "No key with that id.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="api.keys", description="Manage Parity API keys.")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Mint a new API key.")
    create.add_argument("--client", required=True, help="Client identifier.")
    create.add_argument("--days", type=int, default=None, help="Expiry in days (optional).")

    revoke = sub.add_parser("revoke", help="Revoke an existing API key.")
    revoke.add_argument("--id", required=True, help="Key id to revoke.")

    args = parser.parse_args()
    if args.command == "create":
        _create(args.client, args.days)
    elif args.command == "revoke":
        _revoke(args.id)


if __name__ == "__main__":
    main()
