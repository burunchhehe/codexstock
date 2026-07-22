from __future__ import annotations

import argparse
import json
from pathlib import Path

from mobile_console import MobileAccessStore
from runtime_paths import active_data_root


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage CodexStock mobile device pairing")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="Create a one-time phone pairing code")
    create.add_argument("--minutes", type=int, default=10)
    subparsers.add_parser("list", help="List paired devices without token values")
    revoke = subparsers.add_parser("revoke", help="Revoke one paired device")
    revoke.add_argument("device_id")
    args = parser.parse_args()

    store = MobileAccessStore(active_data_root(REPO_ROOT) / "mobile")
    if args.command == "create":
        result = store.create_pairing_code(ttl_seconds=max(1, args.minutes) * 60)
        print("\n코덱스스톡 휴대폰 연결 코드")
        print(f"  {result['code'][:4]} {result['code'][4:]}")
        print(f"만료: {result['expires_at']}")
        print("휴대폰 앱의 연결 설정에 PC 주소와 이 코드를 입력하세요.\n")
        return 0
    if args.command == "list":
        print(json.dumps(store.status(), ensure_ascii=False, indent=2))
        return 0
    result = store.revoke(args.device_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
