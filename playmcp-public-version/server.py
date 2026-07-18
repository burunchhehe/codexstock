from __future__ import annotations

import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings


MAX_ITEMS = 8
MAX_TEXT = 12000
PUBLIC_DATA_DIR = os.environ.get("CODEXSTOCK_PUBLIC_DATA_DIR")
MCP_HOST = os.environ.get("CODEXSTOCK_PUBLIC_MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("CODEXSTOCK_PUBLIC_MCP_PORT", "8000"))
MCP_TRANSPORT = os.environ.get("CODEXSTOCK_PUBLIC_MCP_TRANSPORT", "stdio")
DNS_REBINDING_PROTECTION = os.environ.get("CODEXSTOCK_PUBLIC_DISABLE_DNS_REBINDING", "0") != "1"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "CODEXSTOCK_PUBLIC_ALLOWED_HOSTS",
        f"127.0.0.1:{MCP_PORT},localhost:{MCP_PORT}",
    ).split(",")
    if host.strip()
]

mcp = FastMCP(
    "CodexStock Research",
    host=MCP_HOST,
    port=MCP_PORT,
    streamable_http_path="/mcp",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=DNS_REBINDING_PROTECTION,
        allowed_hosts=ALLOWED_HOSTS,
    ),
)

PRIVATE_PATTERNS = [
    re.compile(r"\b\d{8,14}\b"),
    re.compile(r"(appkey|appsecret|token|authorization|account|balance|order|fill)", re.IGNORECASE),
]

PUBLIC_TOOLS = [
    "explain_codexstock",
    "system_health",
    "public_manifest",
    "market_brief",
    "resolve_stock",
    "stock_snapshot",
    "market_movers",
    "news_signal_summary",
    "disclosure_financial_summary",
    "discover_candidates",
    "explain_candidate",
    "risk_check",
    "ai_staff_opinions",
    "investment_committee",
    "daily_operations_plan",
    "strategy_validation_summary",
    "post_market_review",
    "missed_stock_review",
    "learning_summary",
    "sub_engine_status",
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
        {"name": "Fundamental Researcher", "view": "Checks disclosure and financial context.", "stance": "watch"},
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
    return loaded if isinstance(loaded, dict) else DEMO_STATE


def _data_mode() -> str:
    if not PUBLIC_DATA_DIR:
        return "sample"
    return str(_read_state().get("data_mode", "delayed"))


def _private_key(key: str) -> bool:
    return any(pattern.search(key) for pattern in PRIVATE_PATTERNS)


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


def _response(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("meta", {
        "data_mode": _data_mode(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_scope": "public_redacted",
        "investment_action": "disabled",
        "disclaimer": "Research support only. Not investment advice, not a trade recommendation, and not live order execution.",
    })
    safe = _redact(payload)
    text = json.dumps(safe, ensure_ascii=False)
    if len(text) > MAX_TEXT:
        return {"ok": True, "truncated": True, "summary": text[:MAX_TEXT]}
    return safe


def _find_candidate(symbol_or_name: str) -> dict[str, Any] | None:
    needle = symbol_or_name.strip().lower()
    for candidate in _read_state().get("candidates", []):
        haystack = f"{candidate.get('symbol', '')} {candidate.get('name', '')}".lower()
        if needle and needle in haystack:
            return candidate
    return None


def _risk_level(allocation_percent: float) -> str:
    if allocation_percent <= 30:
        return "green"
    if allocation_percent <= 50:
        return "yellow"
    return "red"


@mcp.tool()
def explain_codexstock() -> dict[str, Any]:
    """Explain what CodexStock Research provides in public read-only mode."""
    return _response({
        "ok": True,
        "positioning": "Stock information lookup plus CodexStock research, risk, replay, and learning workflow.",
        "public_value": [
            "turns raw market information into candidate evidence",
            "shows AI staff disagreement instead of one opaque answer",
            "keeps live trading and private account data out of the public MCP",
        ],
        "not_included": ["live order submission", "account lookup", "tokens", "private journals", "raw live trading logs"],
    })


@mcp.tool()
def system_health() -> dict[str, Any]:
    """Return public server health and safety boundaries."""
    state = _read_state()
    sub_engines = state.get("sub_engines", [])
    active_engines = [engine for engine in sub_engines if engine.get("status") in {"ready", "optional"}]
    return _response({
        "ok": True,
        "server": "CodexStock Research Public MCP",
        "server_status": "online",
        "data_mode": _data_mode(),
        "last_data_update": state.get("as_of", "unknown"),
        "tool_count": len(PUBLIC_TOOLS),
        "private_runtime_connected": bool(PUBLIC_DATA_DIR),
        "sub_engine_count": len(sub_engines),
        "active_or_optional_sub_engine_count": len(active_engines),
        "delayed_or_private_only_engines": [
            engine.get("name") for engine in sub_engines if engine.get("status") not in {"ready", "optional"}
        ],
        "live_trading_tools": 0,
        "sensitive_data_access": "blocked",
        "credential_access": "blocked",
        "private_journal_access": "blocked",
    })


@mcp.tool()
def public_manifest() -> dict[str, Any]:
    """List public tools and state what is intentionally excluded."""
    return _response({
        "ok": True,
        "tools": PUBLIC_TOOLS,
        "excluded": ["orders", "account balances", "credentials", "private logs"],
    })


@mcp.tool()
def market_brief(market: str = "ALL") -> dict[str, Any]:
    """Summarize the broad market regime, tone, themes, and key risks."""
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
    """Show hot-stock or theme movement categories without private account data."""
    candidates = _read_state().get("candidates", [])
    return _response({"ok": True, "market": market, "ranking_type": ranking_type, "items": candidates[:MAX_ITEMS]})


@mcp.tool()
def news_signal_summary(symbol_or_theme: str = "market") -> dict[str, Any]:
    """Summarize public news and external signal themes."""
    return _response({
        "ok": True,
        "target": symbol_or_theme,
        "summary": "Combine repeated sources, theme strength, and risk flags before candidate promotion.",
        "checks": ["source repetition", "recency", "theme relevance", "risk language", "overlap with movers"],
    })


@mcp.tool()
def disclosure_financial_summary(symbol_or_name: str) -> dict[str, Any]:
    """Summarize disclosure and fundamental context in public-preview form."""
    return _response({
        "ok": True,
        "target": symbol_or_name,
        "summary": "Disclosure and financial context should be checked before promotion.",
        "checks": ["recent filings", "revenue trend", "profitability", "debt/liquidity", "one-off events"],
    })


@mcp.tool()
def discover_candidates(market: str = "ALL", style: str = "balanced", limit: int = 5) -> dict[str, Any]:
    """Return CodexStock watch candidates after public evidence filtering."""
    candidates = _read_state().get("candidates", [])[: max(1, min(limit, MAX_ITEMS))]
    return _response({"ok": True, "market": market, "style": style, "candidates": candidates})


@mcp.tool()
def explain_candidate(symbol_or_name: str) -> dict[str, Any]:
    """Explain one watch candidate's evidence, weakness, and invalidation checks."""
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
    return _response({
        "ok": True,
        "target": symbol_or_name,
        "allocation_percent": allocation_percent,
        "risk_level": _risk_level(allocation_percent),
        "checks": ["concentration", "liquidity", "drawdown", "event risk", "public-mode live trading block"],
        "decision": "research_only_public_mcp",
    })


@mcp.tool()
def ai_staff_opinions(symbol_or_name: str = "market") -> dict[str, Any]:
    """Show public AI staff viewpoints."""
    return _response({"ok": True, "target": symbol_or_name, "staff": _read_state().get("staff", [])})


@mcp.tool()
def investment_committee(symbol_or_name: str = "market", allocation_percent: float = 0.0) -> dict[str, Any]:
    """Show a public CodexStock-style research committee observation."""
    candidate = _find_candidate(symbol_or_name) or {
        "symbol": symbol_or_name,
        "name": symbol_or_name,
        "reason": "No exact public candidate match. Treat as a watch-only research request.",
        "risk": "Insufficient public evidence.",
    }
    risk_level = _risk_level(allocation_percent)
    return _response({
        "ok": True,
        "mode": "public_read_only_research_committee",
        "target": candidate,
        "chair_observation": "Review candidate strength, catalyst quality, liquidity, risk concentration, and validation evidence before any private decision process.",
        "staff_votes": [
            {"role": "Research AI", "vote": "watch", "reason": "Evidence exists but source quality must be checked."},
            {"role": "Supply/Demand", "vote": "watch", "reason": "Liquidity and pressure should confirm the theme."},
            {"role": "Strategy", "vote": "caution", "reason": "Needs replay, cost, and out-of-sample validation."},
            {"role": "Trading", "vote": "blocked", "reason": "Public MCP never sends live orders."},
            {"role": "Risk", "vote": risk_level, "reason": "Allocation and event risk decide whether research can progress."},
        ],
        "research_opinion": "watch_only_no_trade_recommendation",
        "next_checks": ["fresh market data", "news catalyst", "sector confirmation", "risk gate", "paper/replay validation"],
    })


@mcp.tool()
def daily_operations_plan(session: str = "today") -> dict[str, Any]:
    """Show the CodexStock daily operating loop in public-preview form."""
    return _response({
        "ok": True,
        "session": session,
        "routine": [
            {"time": "pre-market", "focus": "overnight issues, US market tone, macro events, watchlist preparation"},
            {"time": "market open", "focus": "movers, liquidity, theme strength, candidate review"},
            {"time": "midday", "focus": "morning leaders, weak sectors, risk reset, afternoon plan"},
            {"time": "pre-close", "focus": "position/risk review, missed opportunities, closing strength"},
            {"time": "post-market", "focus": "10/30/50 replay, trade reasons, missed-name review, learning notes"},
            {"time": "night/weekend", "focus": "heavy research, strategy validation, sub-engine jobs, documentation"},
        ],
        "public_note": "This public MCP describes the workflow only. It does not operate a user account or send orders.",
    })


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
    # Default stdio is useful for local MCP smoke tests.
    # For PlayMCP endpoint testing:
    # $env:CODEXSTOCK_PUBLIC_MCP_TRANSPORT="streamable-http"
    # $env:CODEXSTOCK_PUBLIC_MCP_HOST="127.0.0.1"
    # $env:CODEXSTOCK_PUBLIC_MCP_PORT="8000"
    # $env:CODEXSTOCK_PUBLIC_DISABLE_DNS_REBINDING="1"  # quick-tunnel testing only
    # python server.py
    mcp.run(transport=MCP_TRANSPORT)
