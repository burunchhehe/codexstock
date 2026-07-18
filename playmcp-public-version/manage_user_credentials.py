from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import secrets
from pathlib import Path

from cryptography.fernet import Fernet


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_master_key() -> None:
    print(Fernet.generate_key().decode("utf-8"))


def add_profile(args: argparse.Namespace) -> None:
    master_key = args.master_key or getpass.getpass("CODEXSTOCK_CREDENTIAL_MASTER_KEY: ")
    fernet = Fernet(master_key.encode("utf-8"))
    token = args.token or secrets.token_urlsafe(32)
    credentials = {
        "kis_app_key": args.kis_app_key or "",
        "kis_app_secret": args.kis_app_secret or "",
        "dart_api_key": args.dart_api_key or "",
    }
    encrypted = fernet.encrypt(json.dumps(credentials, ensure_ascii=False).encode("utf-8")).decode("utf-8")
    out_dir = Path(args.dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_path = out_dir / f"{token_hash(token)}.json"
    profile_path.write_text(
        json.dumps(
            {
                "version": 1,
                "token_hash": token_hash(token),
                "encrypted_credentials": encrypted,
                "note": "Read-only KIS/DART credential profile for CodexStock public MCP.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("profile_created", profile_path)
    print("user_bearer_token", token)
    print("Keep this token secret. It is shown only once unless you supplied --token.")


def list_profiles(args: argparse.Namespace) -> None:
    out_dir = Path(args.dir)
    for path in sorted(out_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            print(payload.get("token_hash", path.stem))
        except Exception:
            print(path.stem)


def delete_profile(args: argparse.Namespace) -> None:
    profile_path = Path(args.dir) / f"{token_hash(args.token)}.json"
    if profile_path.exists():
        profile_path.unlink()
        print("deleted", profile_path)
    else:
        print("not_found", profile_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage encrypted user credential profiles for CodexStock public MCP.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("new-master-key", help="Generate a Fernet master key for CODEXSTOCK_CREDENTIAL_MASTER_KEY.")

    add = sub.add_parser("add", help="Add an encrypted user credential profile.")
    add.add_argument("--dir", default=".codexstock_credentials")
    add.add_argument("--master-key")
    add.add_argument("--token")
    add.add_argument("--kis-app-key", default="")
    add.add_argument("--kis-app-secret", default="")
    add.add_argument("--dart-api-key", default="")

    list_cmd = sub.add_parser("list", help="List credential profile token hashes.")
    list_cmd.add_argument("--dir", default=".codexstock_credentials")

    delete = sub.add_parser("delete", help="Delete a user credential profile by bearer token.")
    delete.add_argument("--dir", default=".codexstock_credentials")
    delete.add_argument("--token", required=True)

    args = parser.parse_args()
    if args.command == "new-master-key":
        create_master_key()
    elif args.command == "add":
        add_profile(args)
    elif args.command == "list":
        list_profiles(args)
    elif args.command == "delete":
        delete_profile(args)


if __name__ == "__main__":
    main()
