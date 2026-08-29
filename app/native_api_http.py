from __future__ import annotations

from typing import Any, Callable, Mapping


NATIVE_API_GET_PATHS = frozenset({"/api/logic"})
NATIVE_API_POST_PATHS = frozenset({"/api/strategy/run", "/api/research/run", "/api/logic/save", "/api/logic/lock"})


def handle_native_api_get(path: str, *, logic_book: Any) -> tuple[dict[str, Any], int] | None:
    if path not in NATIVE_API_GET_PATHS:
        return None
    return {"slots": logic_book.list()}, 200


def handle_native_api_post(path: str, payload: Mapping[str, Any], *, strategy: Any, research: Any, logic_book: Any, journal_add: Callable[[str, str, dict[str, Any]], None]) -> tuple[dict[str, Any], int] | None:
    if path not in NATIVE_API_POST_PATHS:
        return None
    try:
        if path == "/api/strategy/run":
            return strategy.run_once(symbol=str(payload.get("symbol", "AAPL")), fast=int(payload.get("fast", 12)), slow=int(payload.get("slow", 32)), quantity=float(payload.get("quantity", 10))), 200
        if path == "/api/research/run":
            return research.scan(symbol=str(payload.get("symbol", "AAPL")), days=int(payload.get("days", 260))), 200
        if path == "/api/logic/save":
            result = logic_book.save(name=str(payload.get("name", "나의전략")), fast=int(payload.get("fast", 12)), slow=int(payload.get("slow", 32)), memo=str(payload.get("memo", "")), locked=bool(payload.get("locked", False)))
            journal_add("LOGIC", f"{result['name']} 로직 저장", result)
            return {"slot": result, "slots": logic_book.list()}, 200
        result = logic_book.lock(name=str(payload.get("name", "기준전략")), locked=bool(payload.get("locked", True)))
        journal_add("LOGIC", f"{result['name']} 잠금 상태 변경", result)
        return {"slot": result, "slots": logic_book.list()}, 200
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}, 400
