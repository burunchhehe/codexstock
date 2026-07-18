from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("CodexStock Research")

MAX_ITEMS = 8
MAX_TEXT = 12000
PUBLIC_DATA_DIR = os.environ.get("CODEXSTOCK_PUBLIC_DATA_DIR")


PRIVATE_PATTERNS = [
    re.compile(r"\b\d{8,14}\b"),
    re.compile(r"(appkey|appsecret|token|authorization|계좌|account)", re.IGNORECASE),
]


DEMO_STATE: dict[str, Any] = {
    "as_of": "public-preview",
    "market_brief": {
        "summary": "CodexStock public preview is running in read-only demo mode.",
        "focus": ["market regime", "liquidity", "theme strength", "risk events"],
        "warning": "This is research software, not investment advice.",
    },
    "candidates": [
        {
            "symbol": "DEMO1",
            "name": "Demo Candidate A",
            "market": "KR",
            "reason": "Momentum, liquidity, and repeated external signals are aligned in the sample data.",
            "risk": "Preview data only. Requires validation before any real decision.",
        },
        {
            "symbol": "DEMO2",
            "name": "Demo Candidate B",
            "market": "US",
            "reason": "Large-cap theme and news context are aligned in the sample data.",
            "risk": "Needs risk review, cost modeling, and out-of-sample validation.",
        },
    ],
    "staff": [
        {"name": "Research AI", "view": "Checks evidence quality and market context.", "stance": "watch"},
        {"name": "Supply/Demand Researcher", "view": "Checks liquidity and pressure.", "stance": "watch"},
        {"name": "Strategy Researcher", "view": "Requires replay and walk-forward evidence.", "stance": "caution"},
        {"name": "Trading AI", "view": "Builds a plan only after risk approval.", "stance": "blocked for public MCP"},
        {"name": "Risk Manager", "view": "Blocks live execution in public mode.", "stance": "block"},
    ],
    "sub_engines": [
        {"name": "Research Forge", "status": "ready", "role": "walk-forward validation and replay evidence"},
        {"name": "External Signal Scout", "status": "ready", "role": "public signal and theme summaries"},
        {"name": "KIS Gateway", "status": "private-only", "role": "broker adapter excluded from public MCP"},
        {"name": "OpenBB", "status": "optional", "role": "market and macro research"},
        {"name": "Qlib", "status": "optional", "role": "factor research"},
        {"name": "vectorbt", "status": "optional", "role": "fast vectorized experiments"},
        {"name": "Lean", "status": "optional", "role": "institutional-style backtest harness"},
        {"name": "NautilusTrader", "status": "optional", "role": "event-driven trading simulation"},
    ],
}


def _read_state() -> dict[str, Any]:
    if not PUBLIC_DATA_DIR:
        return DEMO_STATE
    path = Path(PUBLIC_DATA_DIR) / "public_state.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return DEMO_STATE
    if not isinstance(loaded, dict):
        return DEMO_STATE
    return loaded


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _redact(v) for k, v in value.items() if not _private_key(str(k))}
    if isinstance(value, list):
        return [_redact(v) for v in value[:MAX_ITEMS]]
    if isinstance(value, str):
        text = value[:MAX_TEXT]
        for pattern in PRIVATE_PATTERNS:
            text = pattern.sub("[redacted]", text)
        return text
    return value


def _private_key(key: str) -> bool:
    return any(pattern.search(key) for pattern in PRIVATE_PATTERNS)


def _response(payload: dict[str, Any]) -> dict[str, Any]:
    safe = _redact(payload)
    text = json.dumps(safe, ensure_ascii=False)
    if len(text) > MAX_TEXT:
        safe = {"ok": True, "truncated": True, "summary": text[:MAX_TEXT]}
    return safe


def _find_candidate(symbol_or_name: str) -> dict[str, Any] | None:
    needle = symbol_or_name.strip().lower()
    for candidate in _read_state().get("candidates", []):
        haystack = f"{candidate.get('symbol', '')} {candidate.get('name', '')}".lower()
        if needle and needle in haystack:
            return candidate
    return None


@mcp.tool()
def explain_codexstock() -> dict[str, Any]:
    """Explain what CodexStock Research provides in public read-only mode."""
    return _response({
        "ok": True,
        "positioning": "Stock information lookup plus CodexStock research, risk, replay, and learning workflow.",
        "not_included": ["live order submission", "account lookup", "tokens", "private journals", "raw live trading logs"],
    })


@mcp.tool()
def system_health() -> dict[str, Any]:
    """Return public server health and safety boundaries."""
    state = _read_state()
    return _response({
        "ok": True,
        "server": "CodexStock Research Public MCP",
        "mode": "read-only",
        "as_of": state.get("as_of", "unknown"),
        "tool_count": 18,
        "private_runtime_connected": bool(PUBLIC_DATA_DIR),
        "live_trading_tools": 0,
    })


@mcp.tool()
def public_manifest() -> dict[str, Any]:
    """List public tools and state what is intentionally excluded."""
    return _response({
        "ok": True,
        "tools": [
            "explain_codexstock", "system_health", "public_manifest", "market_brief",
            "resolve_stock", "stock_snapshot", "market_movers", "news_signal_summary",
            "disclosure_financial_summary", "discover_candidates", "explain_candidate",
            "risk_check", "ai_staff_opinions", "strategy_validation_summary",
            "post_market_review", "missed_stock_review", "learning_summary", "sub_engine_status",
        ],
        "excluded": ["orders", "account balances", "credentials", "private logs"],
    })


@mcp.tool()
def market_brief(market: str = "ALL") -> dict[str, Any]:
    """Summarize market context for Korea, US, or all markets."""
    state = _read_state()
    return _response({"ok": True, "market": market, "brief": state.get("market_brief", {})})


@mcp.tool()
def resolve_stock(query: str, market: str = "ALL", limit: int = 5) -> dict[str, Any]:
    """Resolve a stock name or code using public preview candidates."""
    matches = []
    needle = query.strip().lower()
    for candidate in _read_state().get("candidates", []):
        haystack = f"{candidate.get('symbol', '')} {candidate.get('name', '')} {candidate.get('market', '')}".lower()
        if not needle or needle in haystack:
            if market == "ALL" or candidate.get("market") == market:
                matches.append(candidate)
    return _response({"ok": True, "query": query, "matches": matches[: max(1, min(limit, MAX_ITEMS))]})


@mcp.tool()
def stock_snapshot(symbol_or_name: str) -> dict[str, Any]:
    """Return a compact public snapshot for a candidate."""
    candidate = _find_candidate(symbol_or_name)
    if not candidate:
        return _response({"ok": False, "message": "No public snapshot found. Connect redacted snapshots for live data."})
    return _response({"ok": True, "snapshot": candidate, "note": "Public preview snapshot, not investment advice."})


@mcp.tool()
def market_movers(market: str = "ALL", ranking_type: str = "theme_strength") -> dict[str, Any]:
    """Show public mover-style categories without private account data."""
    candidates = _read_state().get("candidates", [])
    return _response({"ok": True, "market": market, "ranking_type": ranking_type, "items": candidates[:MAX_ITEMS]})


@mcp.tool()
def news_signal_summary(symbol_or_theme: str = "market") -> dict[str, Any]:
    """Summarize public news and external signal themes."""
    return _response({
        "ok": True,
        "target": symbol_or_theme,
        "summary": "Public preview: combine repeated sources, theme strength, and risk flags before candidate promotion.",
        "checks": ["source repetition", "recency", "theme relevance", "risk language", "overlap with movers"],
    })


@mcp.tool()
def disclosure_financial_summary(symbol_or_name: str) -> dict[str, Any]:
    """Summarize disclosure and fundamental context in public-preview form."""
    return _response({
        "ok": True,
        "target": symbol_or_name,
        "summary": "Public preview: disclosure and financial context should be checked before promotion.",
        "checks": ["recent filings", "revenue trend", "profitability", "debt/liquidity", "one-off events"],
    })


@mcp.tool()
def discover_candidates(market: str = "ALL", style: str = "balanced", limit: int = 5) -> dict[str, Any]:
    """Return public candidate ideas with evidence categories."""
    candidates = _read_state().get("candidates", [])[: max(1, min(limit, MAX_ITEMS))]
    return _response({"ok": True, "market": market, "style": style, "candidates": candidates})


@mcp.tool()
def explain_candidate(symbol_or_name: str) -> dict[str, Any]:
    """Explain why a candidate is being watched and what could invalidate it."""
    candidate = _find_candidate(symbol_or_name)
    if not candidate:
        return _response({"ok": False, "message": "Candidate not found in public preview data."})
    return _response({
        "ok": True,
        "candidate": candidate,
        "evidence": ["market strength", "liquidity", "news/theme signal", "risk review"],
        "invalidation": ["weak volume", "theme fading", "risk concentration", "failed replay validation"],
    })


@mcp.tool()
def risk_check(symbol_or_name: str, allocation_percent: float = 0.0) -> dict[str, Any]:
    """Explain public risk checks for a symbol or allocation."""
    level = "green" if allocation_percent <= 30 else "yellow" if allocation_percent <= 50 else "red"
    return _response({
        "ok": True,
        "target": symbol_or_name,
        "allocation_percent": allocation_percent,
        "risk_level": level,
        "checks": ["concentration", "liquidity", "drawdown", "event risk", "public-mode live trading block"],
        "decision": "research_only_public_mcp",
    })


@mcp.tool()
def ai_staff_opinions(symbol_or_name: str = "market") -> dict[str, Any]:
    """Show public AI staff viewpoints."""
    return _response({"ok": True, "target": symbol_or_name, "staff": _read_state().get("staff", [])})


@mcp.tool()
def strategy_validation_summary(strategy_name: str = "public-preview") -> dict[str, Any]:
    """Summarize strategy validation status without private performance claims."""
    return _response({
        "ok": True,
        "strategy": strategy_name,
        "status": "research preview",
        "required_evidence": ["walk-forward", "out-of-sample", "cost/slippage", "stress test", "paper observation"],
        "public_claim": "No performance guarantee.",
    })


@mcp.tool()
def post_market_review(date: str = "latest") -> dict[str, Any]:
    """Summarize post-market replay and review questions."""
    return _response({
        "ok": True,
        "date": date,
        "review_questions": [
            "What was selected and why?",
            "What was rejected and why?",
            "What moved strongly and what was the likely catalyst?",
            "What did the system miss?",
            "What should change next session?",
        ],
    })


@mcp.tool()
def missed_stock_review(date: str = "latest") -> dict[str, Any]:
    """Explain the missed-stock review workflow."""
    return _response({
        "ok": True,
        "date": date,
        "workflow": ["find strong movers", "match catalysts", "compare against radar inputs", "record missed trigger", "create next-session rule"],
    })


@mcp.tool()
def learning_summary(period: str = "latest") -> dict[str, Any]:
    """Summarize public learning-loop output."""
    return _response({
        "ok": True,
        "period": period,
        "learning_loop": ["journal", "replay", "missed-name review", "rule candidate", "validation before promotion"],
    })


@mcp.tool()
def sub_engine_status() -> dict[str, Any]:
    """Show public sub-engine readiness and roles."""
    return _response({"ok": True, "sub_engines": _read_state().get("sub_engines", [])})


if __name__ == "__main__":
    # Default stdio is useful for local MCP smoke tests. A hosted PlayMCP deployment
    # should run this server with the MCP SDK's HTTP/streamable transport.
    mcp.run()

