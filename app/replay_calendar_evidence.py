from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from typing import Any


CALENDAR_ADJACENCY_PROOF_CONTRACT = "sha256-merkle-symbol-calendar-adjacency-v1"
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _normalized_dates(values: Iterable[object]) -> list[str]:
    return [str(value or "").strip()[:10] for value in values if str(value or "").strip()]


def _pair_leaf(symbol: str, pair_index: int, decision_date: str, execution_date: str) -> bytes:
    payload = (
        f"{CALENDAR_ADJACENCY_PROOF_CONTRACT}|{symbol.strip().upper()}|{pair_index}|"
        f"{decision_date}|{execution_date}"
    )
    return hashlib.sha256(payload.encode("utf-8")).digest()


def _pair_leaves(symbol: str, dates: list[str]) -> list[bytes]:
    return [
        _pair_leaf(symbol, index, dates[index], dates[index + 1])
        for index in range(len(dates) - 1)
    ]


def _merkle_root(leaves: list[bytes]) -> bytes:
    if not leaves:
        return b""
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256(level[index] + level[index + 1]).digest()
            for index in range(0, len(level), 2)
        ]
    return level[0]


def calendar_adjacency_root(symbol: object, trading_dates: Iterable[object]) -> str:
    normalized_symbol = str(symbol or "").strip().upper()
    dates = _normalized_dates(trading_dates)
    root = _merkle_root(_pair_leaves(normalized_symbol, dates))
    return root.hex() if root else ""


def build_calendar_adjacency_proof(
    symbol: object,
    trading_dates: Iterable[object],
    execution_bar_index: int,
) -> dict[str, Any]:
    normalized_symbol = str(symbol or "").strip().upper()
    dates = _normalized_dates(trading_dates)
    execution_index = int(execution_bar_index)
    if not normalized_symbol or execution_index <= 0 or execution_index >= len(dates):
        raise ValueError("calendar adjacency proof requires an in-range execution bar")
    pair_index = execution_index - 1
    leaves = _pair_leaves(normalized_symbol, dates)
    root = _merkle_root(leaves)
    proof: list[dict[str, str]] = []
    level = list(leaves)
    cursor = pair_index
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        if cursor % 2:
            sibling_index = cursor - 1
            side = "left"
        else:
            sibling_index = cursor + 1
            side = "right"
        proof.append({"side": side, "hash": level[sibling_index].hex()})
        level = [
            hashlib.sha256(level[index] + level[index + 1]).digest()
            for index in range(0, len(level), 2)
        ]
        cursor //= 2
    return {
        "symbol_calendar_contract": CALENDAR_ADJACENCY_PROOF_CONTRACT,
        "symbol_calendar_root": root.hex(),
        "symbol_calendar_pair_count": len(leaves),
        "symbol_calendar_adjacency_index": pair_index,
        "decision_symbol_bar_index": pair_index,
        "execution_symbol_bar_index": execution_index,
        "decision_symbol_bar_date": dates[pair_index],
        "execution_symbol_bar_date": dates[execution_index],
        "symbol_calendar_adjacency_proof": proof,
    }


def verify_calendar_adjacency_proof(
    evidence: Mapping[str, Any],
    *,
    expected_symbol: object = "",
    expected_root: object = "",
) -> bool:
    if str(evidence.get("symbol_calendar_contract") or "") != CALENDAR_ADJACENCY_PROOF_CONTRACT:
        return False
    symbol = str(expected_symbol or evidence.get("symbol") or "").strip().upper()
    root = str(evidence.get("symbol_calendar_root") or "").strip().lower()
    if not symbol or _SHA256_PATTERN.fullmatch(root) is None:
        return False
    if expected_root and root != str(expected_root).strip().lower():
        return False
    try:
        pair_index = int(evidence.get("symbol_calendar_adjacency_index"))
        decision_index = int(evidence.get("decision_symbol_bar_index"))
        execution_index = int(evidence.get("execution_symbol_bar_index"))
        pair_count = int(evidence.get("symbol_calendar_pair_count"))
    except (TypeError, ValueError):
        return False
    if pair_index < 0 or decision_index != pair_index or execution_index != pair_index + 1:
        return False
    if pair_count <= pair_index:
        return False
    decision_date = str(evidence.get("decision_symbol_bar_date") or "").strip()[:10]
    execution_date = str(evidence.get("execution_symbol_bar_date") or "").strip()[:10]
    if not decision_date or not execution_date or decision_date >= execution_date:
        return False
    proof = evidence.get("symbol_calendar_adjacency_proof")
    if not isinstance(proof, list):
        return False
    digest = _pair_leaf(symbol, pair_index, decision_date, execution_date)
    for step in proof:
        if not isinstance(step, Mapping):
            return False
        side = str(step.get("side") or "")
        sibling_hex = str(step.get("hash") or "").strip().lower()
        if side not in {"left", "right"} or _SHA256_PATTERN.fullmatch(sibling_hex) is None:
            return False
        sibling = bytes.fromhex(sibling_hex)
        digest = (
            hashlib.sha256(sibling + digest).digest()
            if side == "left"
            else hashlib.sha256(digest + sibling).digest()
        )
    return digest.hex() == root
