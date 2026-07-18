from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
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
USE_LIVE_PUBLIC_DATA = os.environ.get("CODEXSTOCK_PUBLIC_USE_LIVE_DATA", "1") != "0"
PUBLIC_HTTP_TIMEOUT = float(os.environ.get("CODEXSTOCK_PUBLIC_HTTP_TIMEOUT", "4.0"))
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

PRIVATE_KEY_PATTERNS = [
    re.compile(r"(appkey|appsecret|token|authorization|account|balance|order|fill)", re.IGNORECASE),
]

PRIVATE_VALUE_PATTERNS = [
    re.compile(r"\b\d{8,14}\b"),
    re.compile(r"(appkey|appsecret|authorization|bearer)\s*[:=]\s*[\w.\-]+", re.IGNORECASE),
]

PUBLIC_TOOLS = [
    "system_health",
    "market_brief",
    "market_risk_events",
    "sector_theme_brief",
    "market_movers",
    "resolve_stock",
    "stock_snapshot",
    "news_signal_summary",
    "catalyst_check",
    "disclosure_financial_summary",
    "discover_candidates",
    "candidate_compare",
    "explain_candidate",
    "risk_check",
    "watchlist_plan",
    "ai_staff_opinions",
    "ai_research_consensus",
    "strategy_validation_summary",
    "post_market_review",
    "learning_summary",
]

SYMBOL_ALIASES = {
    "삼성전자": "005930.KS",
    "삼성전자우": "005935.KS",
    "sk하이닉스": "000660.KS",
    "하이닉스": "000660.KS",
    "현대차": "005380.KS",
    "기아": "000270.KS",
    "네이버": "035420.KS",
    "naver": "035420.KS",
    "카카오": "035720.KS",
    "lg에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "셀트리온": "068270.KS",
    "한화오션": "042660.KS",
    "두산에너빌리티": "034020.KS",
    "대한전선": "001440.KS",
    "삼성중공업": "010140.KS",
    "irobot": "IRBT",
    "아이로봇": "IRBT",
    "apple": "AAPL",
    "애플": "AAPL",
    "microsoft": "MSFT",
    "마이크로소프트": "MSFT",
    "nvidia": "NVDA",
    "엔비디아": "NVDA",
    "tesla": "TSLA",
    "테슬라": "TSLA",
    "meta": "META",
    "amazon": "AMZN",
    "아마존": "AMZN",
}

MARKET_INDEX_SYMBOLS = {
    "KOREA": ["^KS11", "^KQ11", "KRW=X"],
    "KR": ["^KS11", "^KQ11", "KRW=X"],
    "US": ["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX"],
    "ALL": ["^KS11", "^KQ11", "^GSPC", "^IXIC", "KRW=X"],
}

PUBLIC_WATCH_UNIVERSE = [
    "005930.KS",
    "000660.KS",
    "005380.KS",
    "000270.KS",
    "035420.KS",
    "035720.KS",
    "373220.KS",
    "207940.KS",
    "068270.KS",
    "042660.KS",
    "034020.KS",
    "001440.KS",
    "010140.KS",
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "META",
    "AMZN",
    "IRBT",
]

QUOTE_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
CACHE_TTL_SECONDS = 45

DEMO_STATE: dict[str, Any] = {
    "as_of": "public-preview",
    "market_brief": {
        "summary": "CodexStock public preview is running in read-only demo mode.",
        "focus": ["market regime", "liquidity", "theme strength", "risk events"],
        "warning": "This is research software, not investment advice.",
    },
    "risk_events": [
        {"event": "macro calendar", "risk": "Check rates, CPI, FX, and major central-bank events."},
        {"event": "market flow", "risk": "Check foreign/institutional flow and index breadth."},
    ],
    "themes": [
        {"theme": "AI infrastructure", "strength": "watch", "evidence": ["large-cap attention", "repeated news themes"]},
        {"theme": "shipbuilding/energy", "strength": "watch", "evidence": ["order-cycle headlines", "sector rotation checks"]},
    ],
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
        return "live_public" if USE_LIVE_PUBLIC_DATA else "sample"
    return str(_read_state().get("data_mode", "delayed"))


def _private_key(key: str) -> bool:
    return any(pattern.search(key) for pattern in PRIVATE_KEY_PATTERNS)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _redact(v) for k, v in value.items() if not _private_key(str(k))}
    if isinstance(value, list):
        return [_redact(v) for v in value[:MAX_ITEMS]]
    if isinstance(value, str):
        text = value[:MAX_TEXT]
        for pattern in PRIVATE_VALUE_PATTERNS:
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


def _http_json(url: str) -> dict[str, Any] | None:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 CodexStockResearchPublic/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=PUBLIC_HTTP_TIMEOUT) as response:
            if response.status >= 400:
                return None
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _resolve_public_symbol(symbol_or_name: str) -> str:
    raw = symbol_or_name.strip()
    lowered = raw.lower()
    if lowered in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[lowered]
    if re.fullmatch(r"\d{6}", raw):
        return f"{raw}.KS"
    return raw.upper()


def _quote_yahoo(symbol_or_name: str) -> dict[str, Any] | None:
    if not USE_LIVE_PUBLIC_DATA:
        return None
    symbol = _resolve_public_symbol(symbol_or_name)
    cached_at, cached = QUOTE_CACHE.get(symbol, (0.0, None))
    if time.time() - cached_at < CACHE_TTL_SECONDS:
        return cached

    encoded = urllib.parse.quote(symbol)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range=5d&interval=1d"
    data = _http_json(url)
    result = (data or {}).get("chart", {}).get("result") or []
    if not result:
        QUOTE_CACHE[symbol] = (time.time(), None)
        return None
    item = result[0]
    meta = item.get("meta", {})
    quote = ((item.get("indicators") or {}).get("quote") or [{}])[0]
    closes = [value for value in (quote.get("close") or []) if isinstance(value, (int, float))]
    volumes = [value for value in (quote.get("volume") or []) if isinstance(value, (int, float))]
    price = meta.get("regularMarketPrice")
    previous_close = meta.get("previousClose")
    if price is None and closes:
        price = closes[-1]
    if previous_close is None and len(closes) >= 2:
        previous_close = closes[-2]
    change_percent = None
    if isinstance(price, (int, float)) and isinstance(previous_close, (int, float)) and previous_close:
        change_percent = round((price - previous_close) / previous_close * 100, 2)
    payload = {
        "symbol": symbol,
        "name": meta.get("shortName") or meta.get("longName") or symbol,
        "exchange": meta.get("exchangeName"),
        "currency": meta.get("currency"),
        "price": price,
        "previous_close": previous_close,
        "change_percent": change_percent,
        "volume": volumes[-1] if volumes else meta.get("regularMarketVolume"),
        "market_state": meta.get("marketState"),
        "source": "Yahoo Finance public chart endpoint",
        "source_mode": "live_public",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    QUOTE_CACHE[symbol] = (time.time(), payload)
    return payload


def _quote_many(symbols: list[str], limit: int = MAX_ITEMS) -> list[dict[str, Any]]:
    quotes = []
    for symbol in symbols[: max(1, min(limit, len(symbols)))]:
        quote = _quote_yahoo(symbol)
        if quote:
            quotes.append(quote)
    return quotes


def _live_market_brief(market: str) -> dict[str, Any] | None:
    symbols = MARKET_INDEX_SYMBOLS.get(market.upper(), MARKET_INDEX_SYMBOLS["ALL"])
    quotes = _quote_many(symbols, limit=len(symbols))
    if not quotes:
        return None
    positives = [quote for quote in quotes if (quote.get("change_percent") or 0) > 0]
    negatives = [quote for quote in quotes if (quote.get("change_percent") or 0) < 0]
    tone = "mixed"
    if len(positives) > len(negatives):
        tone = "positive"
    elif len(negatives) > len(positives):
        tone = "negative"
    return {
        "summary": f"Public market snapshot is {tone}. {len(positives)} up, {len(negatives)} down among tracked indices.",
        "tone": tone,
        "indices": quotes,
        "focus": ["index direction", "FX", "theme rotation", "liquidity"],
        "warning": "Public delayed/live source snapshot. Research reference only, not investment advice.",
    }


def _live_candidates(market: str, limit: int) -> list[dict[str, Any]]:
    symbols = PUBLIC_WATCH_UNIVERSE
    if market.upper() in {"KR", "KOREA", "KOSPI", "KOSDAQ"}:
        symbols = [symbol for symbol in symbols if symbol.endswith(".KS") or symbol.endswith(".KQ")]
    elif market.upper() == "US":
        symbols = [symbol for symbol in symbols if "." not in symbol]
    quotes = _quote_many(symbols, limit=len(symbols))
    quotes.sort(key=lambda item: (item.get("change_percent") is not None, item.get("change_percent") or -999), reverse=True)
    candidates = []
    for quote in quotes[: max(1, min(limit, MAX_ITEMS))]:
        candidates.append({
            "symbol": quote.get("symbol"),
            "name": quote.get("name"),
            "market": "KR" if str(quote.get("symbol", "")).endswith((".KS", ".KQ")) else "US",
            "price": quote.get("price"),
            "currency": quote.get("currency"),
            "change_percent": quote.get("change_percent"),
            "volume": quote.get("volume"),
            "reason": "Public watch-universe momentum and price-change scan.",
            "risk": "Needs catalyst, liquidity, and validation checks before any private decision.",
            "source_mode": quote.get("source_mode"),
        })
    return candidates


def _find_candidate(symbol_or_name: str) -> dict[str, Any] | None:
    needle = symbol_or_name.strip().lower()
    live = _quote_yahoo(symbol_or_name)
    if live:
        return {
            "symbol": live.get("symbol"),
            "name": live.get("name"),
            "market": "KR" if str(live.get("symbol", "")).endswith((".KS", ".KQ")) else "US",
            "price": live.get("price"),
            "currency": live.get("currency"),
            "change_percent": live.get("change_percent"),
            "volume": live.get("volume"),
            "reason": "Public quote snapshot matched this query.",
            "risk": "Live/public data can be delayed or incomplete. Use as research input only.",
        }
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
def market_brief(market: str = "ALL") -> dict[str, Any]:
    """Summarize the broad market regime, tone, themes, and key risks."""
    state = _read_state()
    live_brief = _live_market_brief(market)
    return _response({
        "ok": True,
        "market": market,
        "brief": live_brief or state.get("market_brief", {}),
        "fallback_used": live_brief is None,
    })


@mcp.tool()
def market_risk_events(market: str = "ALL") -> dict[str, Any]:
    """Summarize macro, flow, calendar, and event risks to watch today."""
    state = _read_state()
    return _response({
        "ok": True,
        "market": market,
        "risk_events": state.get("risk_events", DEMO_STATE["risk_events"]),
        "how_to_use": "Use this before candidate promotion to avoid ignoring market-wide risk.",
    })


@mcp.tool()
def sector_theme_brief(market: str = "ALL", limit: int = 5) -> dict[str, Any]:
    """Summarize strong sectors, themes, and evidence categories."""
    state = _read_state()
    themes = state.get("themes", DEMO_STATE["themes"])[: max(1, min(limit, MAX_ITEMS))]
    return _response({
        "ok": True,
        "market": market,
        "themes": themes,
        "how_to_use": "Compare candidate stocks against active themes before watchlist promotion.",
    })


@mcp.tool()
def resolve_stock(query: str, market: str = "ALL", limit: int = 5) -> dict[str, Any]:
    """Resolve a stock name or code using public preview candidates."""
    matches = []
    needle = query.strip().lower()
    live = _quote_yahoo(query)
    if live and (market == "ALL" or market.upper() in {"KR", "KOREA", "US"}):
        matches.append({
            "symbol": live.get("symbol"),
            "name": live.get("name"),
            "market": "KR" if str(live.get("symbol", "")).endswith((".KS", ".KQ")) else "US",
            "source_mode": "live_public",
        })
    for candidate in _read_state().get("candidates", []):
        haystack = f"{candidate.get('symbol', '')} {candidate.get('name', '')} {candidate.get('market', '')}".lower()
        if not needle or needle in haystack:
            if market == "ALL" or candidate.get("market") == market:
                matches.append(candidate)
    return _response({"ok": True, "query": query, "matches": matches[: max(1, min(limit, MAX_ITEMS))]})


@mcp.tool()
def stock_snapshot(symbol_or_name: str) -> dict[str, Any]:
    """Return a compact public snapshot for a candidate."""
    live = _quote_yahoo(symbol_or_name)
    if live:
        return _response({
            "ok": True,
            "snapshot": live,
            "note": "Public market-data snapshot. It may be delayed or incomplete and is not investment advice.",
        })
    candidate = _find_candidate(symbol_or_name)
    if not candidate:
        return _response({"ok": False, "message": "No public snapshot found. Connect redacted snapshots for live data."})
    return _response({"ok": True, "snapshot": candidate, "note": "Public preview snapshot, not investment advice."})


@mcp.tool()
def market_movers(market: str = "ALL", ranking_type: str = "theme_strength") -> dict[str, Any]:
    """Show hot-stock or theme movement categories without private account data."""
    live_candidates = _live_candidates(market, MAX_ITEMS)
    candidates = live_candidates or _read_state().get("candidates", [])
    return _response({
        "ok": True,
        "market": market,
        "ranking_type": ranking_type,
        "items": candidates[:MAX_ITEMS],
        "fallback_used": not bool(live_candidates),
    })


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
def catalyst_check(symbol_or_name: str) -> dict[str, Any]:
    """Check likely public catalysts behind a stock or theme move."""
    candidate = _find_candidate(symbol_or_name)
    target = candidate or {"symbol": symbol_or_name, "name": symbol_or_name}
    return _response({
        "ok": True,
        "target": target,
        "likely_catalyst_checks": [
            "fresh news or disclosure",
            "sector/theme rotation",
            "unusual liquidity or trading value",
            "macro-sensitive move",
            "external signal repetition",
        ],
        "research_note": "Treat catalyst results as hypotheses until source quality and timing are verified.",
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
    capped_limit = max(1, min(limit, MAX_ITEMS))
    live_candidates = _live_candidates(market, capped_limit)
    candidates = live_candidates or _read_state().get("candidates", [])[:capped_limit]
    return _response({
        "ok": True,
        "market": market,
        "style": style,
        "candidates": candidates,
        "fallback_used": not bool(live_candidates),
    })


@mcp.tool()
def candidate_compare(symbols_or_names: str, market: str = "ALL") -> dict[str, Any]:
    """Compare multiple public watch candidates by evidence, risk, and next checks."""
    names = [part.strip() for part in re.split(r"[,/|]", symbols_or_names) if part.strip()]
    compared = []
    for name in names[:MAX_ITEMS]:
        candidate = _find_candidate(name) or {"symbol": name, "name": name, "reason": "No public candidate match.", "risk": "Needs evidence."}
        compared.append({
            "candidate": candidate,
            "strength_checks": ["theme fit", "liquidity", "catalyst clarity", "risk level"],
            "research_status": "watch_only_no_trade_recommendation",
        })
    return _response({
        "ok": True,
        "market": market,
        "compared": compared,
        "how_to_use": "Use comparison to decide what deserves deeper private research, not to issue a trade.",
    })


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
def watchlist_plan(symbol_or_name: str = "market", horizon: str = "today") -> dict[str, Any]:
    """Create a public watchlist plan with keep/drop conditions."""
    return _response({
        "ok": True,
        "target": symbol_or_name,
        "horizon": horizon,
        "keep_watching_if": [
            "theme remains active",
            "liquidity confirms interest",
            "news catalyst remains fresh",
            "risk level stays acceptable",
        ],
        "drop_or_deprioritize_if": [
            "volume fades",
            "theme leadership rotates away",
            "risk event dominates the market",
            "candidate fails validation or replay checks",
        ],
        "action_boundary": "Public MCP creates a research watch plan only. No trade instruction is produced.",
    })


@mcp.tool()
def ai_staff_opinions(symbol_or_name: str = "market") -> dict[str, Any]:
    """Show public AI staff viewpoints."""
    return _response({"ok": True, "target": symbol_or_name, "staff": _read_state().get("staff", [])})


@mcp.tool()
def ai_research_consensus(symbol_or_name: str = "market", allocation_percent: float = 0.0) -> dict[str, Any]:
    """Show a public CodexStock-style AI research consensus observation."""
    candidate = _find_candidate(symbol_or_name) or {
        "symbol": symbol_or_name,
        "name": symbol_or_name,
        "reason": "No exact public candidate match. Treat as a watch-only research request.",
        "risk": "Insufficient public evidence.",
    }
    risk_level = _risk_level(allocation_percent)
    return _response({
        "ok": True,
        "mode": "public_read_only_ai_research_consensus",
        "target": candidate,
        "lead_observation": "Review candidate strength, catalyst quality, liquidity, risk concentration, and validation evidence before any private decision process.",
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
def learning_summary(period: str = "latest") -> dict[str, Any]:
    """Summarize public learning-loop output."""
    return _response({
        "ok": True,
        "period": period,
        "learning_loop": ["journal", "replay", "missed-name review", "rule candidate", "validation before promotion"],
    })


if __name__ == "__main__":
    # Default stdio is useful for local MCP smoke tests.
    # For PlayMCP endpoint testing:
    # $env:CODEXSTOCK_PUBLIC_MCP_TRANSPORT="streamable-http"
    # $env:CODEXSTOCK_PUBLIC_MCP_HOST="127.0.0.1"
    # $env:CODEXSTOCK_PUBLIC_MCP_PORT="8000"
    # $env:CODEXSTOCK_PUBLIC_DISABLE_DNS_REBINDING="1"  # quick-tunnel testing only
    # python server.py
    mcp.run(transport=MCP_TRANSPORT)
