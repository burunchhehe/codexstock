from __future__ import annotations

import hashlib
import html
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse


MAX_ITEMS = 8
MAX_TEXT = 12000
PUBLIC_SCAN_LIMIT = max(MAX_ITEMS, min(int(os.environ.get("CODEXSTOCK_PUBLIC_SCAN_LIMIT", "24")), 40))
PUBLIC_DATA_DIR = os.environ.get("CODEXSTOCK_PUBLIC_DATA_DIR")
MCP_HOST = os.environ.get("CODEXSTOCK_PUBLIC_MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("CODEXSTOCK_PUBLIC_MCP_PORT", "8000"))
MCP_TRANSPORT = os.environ.get("CODEXSTOCK_PUBLIC_MCP_TRANSPORT", "stdio")
USE_LIVE_PUBLIC_DATA = os.environ.get("CODEXSTOCK_PUBLIC_USE_LIVE_DATA", "1") != "0"
PUBLIC_HTTP_TIMEOUT = float(os.environ.get("CODEXSTOCK_PUBLIC_HTTP_TIMEOUT", "4.0"))
PUBLIC_MAX_WORKERS = max(1, min(int(os.environ.get("CODEXSTOCK_PUBLIC_MAX_WORKERS", "4")), 8))
KIS_APP_KEY = os.environ.get("KIS_APP_KEY") or os.environ.get("KOREAINVESTMENT_APP_KEY")
KIS_APP_SECRET = os.environ.get("KIS_APP_SECRET") or os.environ.get("KOREAINVESTMENT_APP_SECRET")
KIS_BASE_URL = os.environ.get("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443").rstrip("/")
DART_API_KEY = os.environ.get("DART_API_KEY") or os.environ.get("OPENDART_API_KEY")
USER_CREDENTIAL_MODE = os.environ.get("CODEXSTOCK_PUBLIC_CREDENTIAL_MODE", "server_or_public").lower()
USER_CREDENTIAL_DIR = Path(os.environ.get("CODEXSTOCK_PUBLIC_CREDENTIAL_DIR", str(Path.cwd() / ".codexstock_credentials")))
USER_CREDENTIAL_MASTER_KEY = os.environ.get("CODEXSTOCK_CREDENTIAL_MASTER_KEY")
USER_CONNECT_CODE = os.environ.get("CODEXSTOCK_PUBLIC_CONNECT_CODE", "")
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
    "lg화학": "051910.KS",
    "posco홀딩스": "005490.KS",
    "포스코홀딩스": "005490.KS",
    "포스코퓨처엠": "003670.KS",
    "삼성sdi": "006400.KS",
    "lg전자": "066570.KS",
    "kb금융": "105560.KS",
    "신한지주": "055550.KS",
    "하나금융지주": "086790.KS",
    "카카오뱅크": "323410.KS",
    "삼성물산": "028260.KS",
    "현대모비스": "012330.KS",
    "hd현대중공업": "329180.KS",
    "hd한국조선해양": "009540.KS",
    "삼양식품": "003230.KS",
    "에코프로": "086520.KQ",
    "에코프로비엠": "247540.KQ",
    "알테오젠": "196170.KQ",
    "리노공업": "058470.KQ",
    "hpsp": "403870.KQ",
    "실리콘투": "257720.KQ",
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

CODE_NAME_ALIASES = {
    "005930": "삼성전자",
    "005935": "삼성전자우",
    "000660": "SK하이닉스",
    "005380": "현대차",
    "000270": "기아",
    "035420": "NAVER",
    "035720": "카카오",
    "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스",
    "068270": "셀트리온",
    "042660": "한화오션",
    "034020": "두산에너빌리티",
    "001440": "대한전선",
    "010140": "삼성중공업",
    "051910": "LG화학",
    "005490": "POSCO홀딩스",
    "003670": "포스코퓨처엠",
    "006400": "삼성SDI",
    "066570": "LG전자",
    "105560": "KB금융",
    "055550": "신한지주",
    "086790": "하나금융지주",
    "323410": "카카오뱅크",
    "028260": "삼성물산",
    "012330": "현대모비스",
    "329180": "HD현대중공업",
    "009540": "HD한국조선해양",
    "003230": "삼양식품",
    "086520": "에코프로",
    "247540": "에코프로비엠",
    "196170": "알테오젠",
    "058470": "리노공업",
    "403870": "HPSP",
    "257720": "실리콘투",
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
    "051910.KS",
    "005490.KS",
    "003670.KS",
    "006400.KS",
    "066570.KS",
    "105560.KS",
    "055550.KS",
    "086790.KS",
    "323410.KS",
    "028260.KS",
    "012330.KS",
    "329180.KS",
    "009540.KS",
    "003230.KS",
    "086520.KQ",
    "247540.KQ",
    "196170.KQ",
    "058470.KQ",
    "403870.KQ",
    "257720.KQ",
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "META",
    "AMZN",
    "IRBT",
]

QUOTE_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
PUBLIC_QUOTE_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
DART_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
KIS_TOKEN_CACHE: dict[str, Any] = {"token": None, "expires_at": 0.0}
USER_KIS_TOKEN_CACHE: dict[str, dict[str, Any]] = {}
CACHE_TTL_SECONDS = 45
DART_CACHE_TTL_SECONDS = 60 * 60 * 6
CACHE_MAX_ENTRIES = 256

CORP_CODE_ALIASES = {
    "005930": "00126380",
    "005935": "00126380",
    "000660": "00164779",
    "005380": "00164742",
    "000270": "00106641",
    "035420": "00266961",
    "035720": "00258801",
    "373220": "01515323",
    "207940": "00877059",
    "068270": "00413046",
    "042660": "00111704",
    "034020": "00159616",
    "001440": "00148914",
    "010140": "00126446",
    "051910": "00356361",
    "005490": "00155319",
    "003670": "00155276",
    "006400": "00126256",
    "066570": "00401731",
    "105560": "00688996",
    "055550": "00382199",
    "086790": "00547583",
    "323410": "01276540",
    "028260": "00149655",
    "012330": "00164788",
    "329180": "01350869",
    "009540": "00164645",
    "003230": "00126901",
    "086520": "00495861",
    "247540": "01206873",
    "196170": "00995845",
    "058470": "00386916",
    "403870": "01591438",
    "257720": "01137236",
}

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


def _trim_cache(cache: dict[str, tuple[float, Any]]) -> None:
    if len(cache) <= CACHE_MAX_ENTRIES:
        return
    for key, _ in sorted(cache.items(), key=lambda item: item[1][0])[: len(cache) - CACHE_MAX_ENTRIES]:
        cache.pop(key, None)


def _cache_get(cache: dict[str, tuple[float, Any]], key: str, ttl: float) -> Any:
    cached_at, cached = cache.get(key, (0.0, None))
    if time.time() - cached_at < ttl:
        return cached
    return None


def _cache_set(cache: dict[str, tuple[float, Any]], key: str, value: Any) -> Any:
    cache[key] = (time.time(), value)
    _trim_cache(cache)
    return value


def _http_post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any] | None:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": "Mozilla/5.0 CodexStockResearchPublic/1.0",
            "Content-Type": "application/json; charset=utf-8",
            **(headers or {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=PUBLIC_HTTP_TIMEOUT) as response:
            if response.status >= 400:
                return None
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _fernet():
    if not USER_CREDENTIAL_MASTER_KEY:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(USER_CREDENTIAL_MASTER_KEY.encode("utf-8"))
    except Exception:
        return None


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _request_headers(ctx: Context | None) -> dict[str, str]:
    if ctx is None:
        return {}
    try:
        request = getattr(ctx.request_context, "request", None)
    except Exception:
        return {}
    headers = getattr(request, "headers", None)
    if headers:
        try:
            return {str(k).lower(): str(v) for k, v in dict(headers).items()}
        except Exception:
            pass
    scope = getattr(request, "scope", None)
    raw_headers = (scope or {}).get("headers") if isinstance(scope, dict) else None
    parsed = {}
    for key, value in raw_headers or []:
        try:
            parsed[key.decode("latin1").lower()] = value.decode("latin1")
        except Exception:
            continue
    return parsed


def _bearer_token(ctx: Context | None) -> str | None:
    headers = _request_headers(ctx)
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return headers.get("x-codexstock-user-token") or None


def _load_user_credentials(ctx: Context | None = None) -> dict[str, str]:
    token = _bearer_token(ctx)
    if not token:
        return {}
    fernet = _fernet()
    if not fernet:
        return {}
    profile_path = USER_CREDENTIAL_DIR / f"{_token_hash(token)}.json"
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
        encrypted = payload.get("encrypted_credentials")
        if not encrypted:
            return {}
        loaded = json.loads(fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8"))
        return {str(k): str(v) for k, v in loaded.items() if v}
    except Exception:
        return {}


def _profile_path_for_token(token: str) -> Path:
    return USER_CREDENTIAL_DIR / f"{_token_hash(token)}.json"


def _require_master_key() -> tuple[bool, str]:
    if not USER_CREDENTIAL_MASTER_KEY:
        return False, "CODEXSTOCK_CREDENTIAL_MASTER_KEY is not configured."
    try:
        from cryptography.fernet import Fernet

        Fernet(USER_CREDENTIAL_MASTER_KEY.encode("utf-8"))
    except Exception as exc:
        return False, f"Invalid CODEXSTOCK_CREDENTIAL_MASTER_KEY: {exc}"
    return True, "ok"


def _create_user_profile(
    *,
    kis_app_key: str,
    kis_app_secret: str,
    dart_api_key: str,
    label: str = "",
) -> dict[str, str]:
    from cryptography.fernet import Fernet

    ok, message = _require_master_key()
    if not ok:
        raise RuntimeError(message)

    token = secrets.token_urlsafe(32)
    fernet = Fernet(str(USER_CREDENTIAL_MASTER_KEY).encode("utf-8"))
    credentials = {
        "kis_app_key": kis_app_key.strip(),
        "kis_app_secret": kis_app_secret.strip(),
        "dart_api_key": dart_api_key.strip(),
    }
    encrypted = fernet.encrypt(json.dumps(credentials, ensure_ascii=False).encode("utf-8")).decode("utf-8")
    USER_CREDENTIAL_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = _profile_path_for_token(token)
    profile_path.write_text(
        json.dumps(
            {
                "version": 1,
                "token_hash": _token_hash(token),
                "label": label.strip()[:80],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "encrypted_credentials": encrypted,
                "note": "Read-only KIS/DART credential profile for CodexStock public MCP.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"token": token, "token_hash": _token_hash(token), "profile_path": str(profile_path)}


def _connect_page_html(*, message: str = "", token: str = "", status_code: int = 200) -> HTMLResponse:
    ok, key_message = _require_master_key()
    escaped_message = html.escape(message)
    escaped_token = html.escape(token)
    disabled = "" if ok else "disabled"
    invite_input = (
        """
        <label>Connection code
          <input name="connect_code" autocomplete="one-time-code" placeholder="Provided by the server operator" />
        </label>
        """
        if USER_CONNECT_CODE
        else ""
    )
    token_block = (
        f"""
        <section class="result">
          <h2>Connection token issued</h2>
          <p>Copy this token once and put it into PlayMCP authentication as a bearer token.</p>
          <pre>Authorization: Bearer {escaped_token}</pre>
          <p class="warn">This token is shown only on this screen. Do not share it publicly.</p>
        </section>
        """
        if token
        else ""
    )
    html_body = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CodexStock Research 연결</title>
  <style>
    body {{ margin:0; font-family:Segoe UI, sans-serif; color:#e9fbff; background:#071115; }}
    main {{ max-width:780px; margin:40px auto; padding:28px; border:1px solid #1b6675; border-radius:20px; background:#0b1b22; }}
    h1 {{ margin:0 0 8px; color:#41e6ff; }}
    p {{ color:#b7c8d0; line-height:1.55; }}
    form {{ display:grid; gap:14px; margin-top:20px; }}
    label {{ display:grid; gap:6px; color:#dff8ff; font-weight:600; }}
    input {{ padding:12px; border-radius:10px; border:1px solid #244b55; background:#071115; color:#f6feff; }}
    button {{ width:max-content; padding:12px 18px; border:0; border-radius:999px; background:#31d0aa; color:#03201a; font-weight:800; cursor:pointer; }}
    button:disabled {{ opacity:.45; cursor:not-allowed; }}
    .notice,.result {{ margin-top:18px; padding:14px; border-radius:14px; background:#102832; border:1px solid #245765; }}
    .warn {{ color:#ffd479; }}
    pre {{ white-space:pre-wrap; word-break:break-all; padding:12px; border-radius:12px; background:#02080a; border:1px solid #244b55; }}
    small {{ color:#8ca4ad; }}
  </style>
</head>
<body>
<main>
  <h1>CodexStock Research 연결</h1>
  <p>사용자의 KIS Open API 앱키, 앱 시크릿, OpenDART 키를 서버에 암호화 저장하고 PlayMCP에는 연결 토큰 하나만 등록하는 페이지입니다.</p>
  <p class="warn">읽기 전용 조회만 사용합니다. 실전 주문, 계좌, 잔고, 체결, 개인 매매기록은 이 공개 MCP에 없습니다.</p>
  <div class="notice">서버 키 상태: {html.escape(key_message if not ok else "ready")}</div>
  {f'<div class="notice">{escaped_message}</div>' if message else ''}
  {token_block}
  <form method="post" action="/connect">
    {invite_input}
    <label>Profile label
      <input name="label" maxlength="80" placeholder="예: jinwoo-playmcp" />
    </label>
    <label>KIS App Key
      <input name="kis_app_key" autocomplete="off" placeholder="KIS read-only app key" />
    </label>
    <label>KIS App Secret
      <input name="kis_app_secret" type="password" autocomplete="off" placeholder="KIS read-only app secret" />
    </label>
    <label>OpenDART API Key
      <input name="dart_api_key" autocomplete="off" placeholder="Optional DART API key" />
    </label>
    <button type="submit" {disabled}>연결 토큰 발급</button>
  </form>
  <p><small>발급 후 PlayMCP 인증 값에는 raw KIS/DART 키가 아니라 <code>Authorization: Bearer &lt;token&gt;</code>만 넣습니다.</small></p>
</main>
</body>
</html>"""
    return HTMLResponse(html_body, status_code=status_code)


@mcp.custom_route("/connect", methods=["GET"], include_in_schema=False)
async def connect_page(request: Request) -> HTMLResponse:
    return _connect_page_html()


@mcp.custom_route("/connect", methods=["POST"], include_in_schema=False)
async def connect_submit(request: Request) -> HTMLResponse:
    body = (await request.body()).decode("utf-8", errors="replace")
    form = {key: values[-1] for key, values in urllib.parse.parse_qs(body, keep_blank_values=True).items()}
    if USER_CONNECT_CODE and not hmac.compare_digest(form.get("connect_code", ""), USER_CONNECT_CODE):
        return _connect_page_html(message="Connection code is invalid.", status_code=403)
    if not (form.get("kis_app_key") and form.get("kis_app_secret") or form.get("dart_api_key")):
        return _connect_page_html(message="At least KIS app key/secret or DART API key is required.", status_code=400)
    try:
        created = _create_user_profile(
            kis_app_key=form.get("kis_app_key", ""),
            kis_app_secret=form.get("kis_app_secret", ""),
            dart_api_key=form.get("dart_api_key", ""),
            label=form.get("label", ""),
        )
    except Exception as exc:
        return _connect_page_html(message=f"Could not create credential profile: {exc}", status_code=500)
    return _connect_page_html(message="Credential profile created.", token=created["token"])


@mcp.custom_route("/connect/status", methods=["GET"], include_in_schema=False)
async def connect_status(request: Request) -> JSONResponse:
    token = request.query_params.get("token", "")
    active = bool(token and _profile_path_for_token(token).exists())
    return JSONResponse(
        {
            "ok": True,
            "credential_mode": USER_CREDENTIAL_MODE,
            "master_key_configured": bool(USER_CREDENTIAL_MASTER_KEY),
            "connect_page": "/connect",
            "user_profile_active": active,
            "token_hash_prefix": _token_hash(token)[:12] if token else None,
            "safety": {
                "raw_api_keys_in_tool_params": False,
                "order_tools": False,
                "account_balance_tools": False,
                "read_only_kis_dart": True,
            },
        }
    )


def _credential_context(ctx: Context | None = None) -> dict[str, Any]:
    user_credentials = _load_user_credentials(ctx)
    if user_credentials:
        return {
            "mode": "user_profile",
            "profile_token_hash": _token_hash(_bearer_token(ctx) or "")[:12],
            "kis_app_key": user_credentials.get("kis_app_key") or user_credentials.get("KIS_APP_KEY"),
            "kis_app_secret": user_credentials.get("kis_app_secret") or user_credentials.get("KIS_APP_SECRET"),
            "dart_api_key": user_credentials.get("dart_api_key") or user_credentials.get("DART_API_KEY"),
        }
    if USER_CREDENTIAL_MODE == "user_profiles":
        return {"mode": "user_profile_missing", "kis_app_key": None, "kis_app_secret": None, "dart_api_key": None}
    return {
        "mode": "server_or_public",
        "kis_app_key": KIS_APP_KEY,
        "kis_app_secret": KIS_APP_SECRET,
        "dart_api_key": DART_API_KEY,
    }


def _kis_configured(ctx: Context | None = None) -> bool:
    credentials = _credential_context(ctx)
    return bool(credentials.get("kis_app_key") and credentials.get("kis_app_secret"))


def _dart_configured(ctx: Context | None = None) -> bool:
    return bool(_credential_context(ctx).get("dart_api_key"))


def _stock_code(symbol_or_name: str) -> str | None:
    symbol = _resolve_public_symbol(symbol_or_name)
    match = re.search(r"(\d{6})", symbol)
    return match.group(1) if match else None


def _kis_access_token(ctx: Context | None = None) -> str | None:
    credentials = _credential_context(ctx)
    app_key = credentials.get("kis_app_key")
    app_secret = credentials.get("kis_app_secret")
    if not (app_key and app_secret):
        return None
    now = time.time()
    if credentials.get("mode") == "user_profile":
        profile_hash = str(credentials.get("profile_token_hash"))
        cached = USER_KIS_TOKEN_CACHE.get(profile_hash, {})
        if cached.get("token") and float(cached.get("expires_at") or 0) > now + 60:
            return str(cached["token"])
    elif KIS_TOKEN_CACHE.get("token") and float(KIS_TOKEN_CACHE.get("expires_at") or 0) > now + 60:
        return str(KIS_TOKEN_CACHE["token"])
    data = _http_post_json(
        f"{KIS_BASE_URL}/oauth2/tokenP",
        {"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret},
    )
    token = (data or {}).get("access_token")
    expires_in = float((data or {}).get("expires_in") or 3600)
    if not token:
        return None
    cache_item = {"token": token, "expires_at": now + min(expires_in, 60 * 60 * 6)}
    if credentials.get("mode") == "user_profile":
        USER_KIS_TOKEN_CACHE[str(credentials.get("profile_token_hash"))] = cache_item
    else:
        KIS_TOKEN_CACHE.update(cache_item)
    return str(token)


def _kis_headers(tr_id: str, ctx: Context | None = None) -> dict[str, str] | None:
    credentials = _credential_context(ctx)
    app_key = credentials.get("kis_app_key")
    app_secret = credentials.get("kis_app_secret")
    token = _kis_access_token(ctx)
    if not token or not app_key or not app_secret:
        return None
    return {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
        "custtype": "P",
    }


def _kis_get(path: str, params: dict[str, str], tr_id: str, ctx: Context | None = None) -> dict[str, Any] | None:
    headers = _kis_headers(tr_id, ctx)
    if not headers:
        return None
    query = urllib.parse.urlencode(params)
    url = f"{KIS_BASE_URL}{path}?{query}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=PUBLIC_HTTP_TIMEOUT) as response:
            if response.status >= 400:
                return None
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _kis_quote(symbol_or_name: str, ctx: Context | None = None) -> dict[str, Any] | None:
    code = _stock_code(symbol_or_name)
    if not code or not _kis_configured(ctx):
        return None
    data = _kis_get(
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        "FHKST01010100",
        ctx,
    )
    output = (data or {}).get("output") or {}
    if not output:
        return None

    def as_float(key: str) -> float | None:
        raw = output.get(key)
        try:
            return float(str(raw).replace(",", ""))
        except Exception:
            return None

    return {
        "symbol": f"{code}.KS",
        "name": CODE_NAME_ALIASES.get(code, code),
        "exchange": "KIS domestic stock",
        "currency": "KRW",
        "price": as_float("stck_prpr"),
        "previous_close": as_float("stck_sdpr"),
        "change_percent": as_float("prdy_ctrt"),
        "volume": as_float("acml_vol"),
        "trading_value": as_float("acml_tr_pbmn"),
        "market_cap": as_float("hts_avls"),
        "open": as_float("stck_oprc"),
        "high": as_float("stck_hgpr"),
        "low": as_float("stck_lwpr"),
        "source": "KIS Open API domestic-stock inquire-price",
        "source_mode": "kis_read_only",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _kis_orderbook(symbol_or_name: str, depth: int = 5, ctx: Context | None = None) -> dict[str, Any] | None:
    code = _stock_code(symbol_or_name)
    if not code or not _kis_configured(ctx):
        return None
    data = _kis_get(
        "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        "FHKST01010200",
        ctx,
    )
    output = (data or {}).get("output1") or (data or {}).get("output") or {}
    if not output:
        return None
    asks = []
    bids = []
    for i in range(1, max(1, min(depth, 10)) + 1):
        asks.append({"price": output.get(f"askp{i}"), "volume": output.get(f"askp_rsqn{i}")})
        bids.append({"price": output.get(f"bidp{i}"), "volume": output.get(f"bidp_rsqn{i}")})
    return {
        "symbol": f"{code}.KS",
        "asks": asks,
        "bids": bids,
        "expected_price": output.get("antc_cnpr"),
        "expected_volume": output.get("antc_cntg_vrss"),
        "source": "KIS Open API domestic-stock orderbook",
        "source_mode": "kis_read_only",
    }


def _kis_history(symbol_or_name: str, limit: int = 20, ctx: Context | None = None) -> list[dict[str, Any]]:
    code = _stock_code(symbol_or_name)
    if not code or not _kis_configured(ctx):
        return []
    today = datetime.now().strftime("%Y%m%d")
    data = _kis_get(
        "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": "20000101",
            "FID_INPUT_DATE_2": today,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "1",
        },
        "FHKST03010100",
        ctx,
    )
    rows = (data or {}).get("output2") or []
    history = []
    for row in rows[: max(1, min(limit, 100))]:
        history.append({
            "date": row.get("stck_bsop_date"),
            "open": row.get("stck_oprc"),
            "high": row.get("stck_hgpr"),
            "low": row.get("stck_lwpr"),
            "close": row.get("stck_clpr"),
            "volume": row.get("acml_vol"),
            "trading_value": row.get("acml_tr_pbmn"),
        })
    return history


def _kis_market_ranking(market: str = "ALL", ranking_type: str = "change_rate", limit: int = MAX_ITEMS, ctx: Context | None = None) -> list[dict[str, Any]]:
    if not _kis_configured(ctx):
        return []
    # KIS ranking TR variants differ by ranking type. Keep this conservative: use public watch scan unless a curated
    # deployment maps its preferred KIS ranking endpoints into redacted snapshots.
    return []


def _dart_get(path: str, params: dict[str, str], ctx: Context | None = None) -> dict[str, Any] | None:
    credentials = _credential_context(ctx)
    dart_api_key = credentials.get("dart_api_key")
    if not dart_api_key:
        return None
    query = urllib.parse.urlencode({"crtfc_key": dart_api_key, **params})
    source = str(credentials.get("profile_token_hash") or "server")
    cache_key = f"{source}:{path}?{query}"
    cached = _cache_get(DART_CACHE, cache_key, DART_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached
    return _cache_set(DART_CACHE, cache_key, _http_json(f"https://opendart.fss.or.kr/api/{path}?{query}"))


def _dart_corp_code(symbol_or_name: str) -> str | None:
    code = _stock_code(symbol_or_name)
    return CORP_CODE_ALIASES.get(code or "")


def _dart_company(symbol_or_name: str, ctx: Context | None = None) -> dict[str, Any] | None:
    corp_code = _dart_corp_code(symbol_or_name)
    if not corp_code:
        return None
    data = _dart_get("company.json", {"corp_code": corp_code}, ctx)
    if not data or data.get("status") not in {None, "000"}:
        return None
    return data


def _dart_financial(symbol_or_name: str, year: str | None = None, report_code: str = "11011", ctx: Context | None = None) -> dict[str, Any] | None:
    corp_code = _dart_corp_code(symbol_or_name)
    if not corp_code:
        return None
    target_year = year or str(datetime.now().year - 1)
    data = _dart_get("fnlttSinglAcnt.json", {
        "corp_code": corp_code,
        "bsns_year": target_year,
        "reprt_code": report_code,
    }, ctx)
    if not data or data.get("status") not in {None, "000"}:
        return None
    rows = []
    for row in (data.get("list") or [])[:MAX_ITEMS]:
        rows.append({
            "account": row.get("account_nm"),
            "statement": row.get("sj_nm"),
            "current_amount": row.get("thstrm_amount"),
            "previous_amount": row.get("frmtrm_amount"),
            "currency": row.get("currency"),
        })
    return {
        "corp_code": corp_code,
        "year": target_year,
        "report_code": report_code,
        "accounts": rows,
        "source": "OpenDART fnlttSinglAcnt",
        "source_mode": "dart_read_only",
    }


def _dart_filings(symbol_or_name: str, limit: int = 5, ctx: Context | None = None) -> list[dict[str, Any]]:
    corp_code = _dart_corp_code(symbol_or_name)
    if not corp_code:
        return []
    end = datetime.now().strftime("%Y%m%d")
    start = f"{datetime.now().year}0101"
    data = _dart_get("list.json", {
        "corp_code": corp_code,
        "bgn_de": start,
        "end_de": end,
        "page_no": "1",
        "page_count": str(max(1, min(limit, 100))),
    }, ctx)
    rows = []
    for row in (data or {}).get("list", [])[: max(1, min(limit, MAX_ITEMS))]:
        rows.append({
            "date": row.get("rcept_dt"),
            "report": row.get("report_nm"),
            "receipt_no": row.get("rcept_no"),
            "submitter": row.get("flr_nm"),
            "source": "OpenDART list",
        })
    return rows


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
        _cache_set(QUOTE_CACHE, symbol, None)
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
    return _cache_set(QUOTE_CACHE, symbol, payload)


def _history_yahoo(symbol_or_name: str, limit: int = 20) -> list[dict[str, Any]]:
    if not USE_LIVE_PUBLIC_DATA:
        return []
    symbol = _resolve_public_symbol(symbol_or_name)
    encoded = urllib.parse.quote(symbol)
    data = _http_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range=3mo&interval=1d")
    result = (data or {}).get("chart", {}).get("result") or []
    if not result:
        return []
    item = result[0]
    timestamps = item.get("timestamp") or []
    quote = ((item.get("indicators") or {}).get("quote") or [{}])[0]
    rows = []
    for idx, ts in enumerate(timestamps[-max(1, min(limit, 60)):]):
        def pick(key: str) -> Any:
            values = quote.get(key) or []
            return values[idx + max(0, len(timestamps) - max(1, min(limit, 60)))] if idx + max(0, len(timestamps) - max(1, min(limit, 60))) < len(values) else None
        rows.append({
            "date": datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
            "open": pick("open"),
            "high": pick("high"),
            "low": pick("low"),
            "close": pick("close"),
            "volume": pick("volume"),
            "source": "Yahoo Finance public chart endpoint",
        })
    return rows


def _price_history(symbol_or_name: str, limit: int = 20, ctx: Context | None = None) -> list[dict[str, Any]]:
    return _kis_history(symbol_or_name, limit, ctx) or _history_yahoo(symbol_or_name, limit)


def _quote_public(symbol_or_name: str, ctx: Context | None = None) -> dict[str, Any] | None:
    symbol = _resolve_public_symbol(symbol_or_name)
    credentials = _credential_context(ctx)
    source_key = f"kis:{credentials.get('profile_token_hash') or 'server'}" if _kis_configured(ctx) and _stock_code(symbol_or_name) else "public"
    cache_key = f"{source_key}:{symbol}"
    cached_at, cached = PUBLIC_QUOTE_CACHE.get(cache_key, (0.0, None))
    if time.time() - cached_at < CACHE_TTL_SECONDS:
        return cached
    return _cache_set(PUBLIC_QUOTE_CACHE, cache_key, _kis_quote(symbol_or_name, ctx) or _quote_yahoo(symbol_or_name))


def _quote_many(symbols: list[str], limit: int = MAX_ITEMS, ctx: Context | None = None) -> list[dict[str, Any]]:
    capped = max(1, min(limit, len(symbols)))
    unique_symbols = list(dict.fromkeys(symbols))[:capped]
    quotes_by_symbol: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(PUBLIC_MAX_WORKERS, len(unique_symbols))) as executor:
        futures = {executor.submit(_quote_public, symbol, ctx): symbol for symbol in unique_symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                quote = future.result()
            except Exception:
                quote = None
            if quote:
                quotes_by_symbol[symbol] = quote
    return [quotes_by_symbol[symbol] for symbol in unique_symbols if symbol in quotes_by_symbol]


def _rank_quotes(quotes: list[dict[str, Any]], ranking_type: str) -> list[dict[str, Any]]:
    rank = ranking_type.lower()
    if rank in {"volume", "거래량"}:
        key = lambda item: item.get("volume") or -1
    elif rank in {"trading_value", "amount", "거래대금"}:
        key = lambda item: item.get("trading_value") or ((item.get("price") or 0) * (item.get("volume") or 0))
    elif rank in {"decliners", "bottom", "fall", "하락률"}:
        return sorted(quotes, key=lambda item: item.get("change_percent") if item.get("change_percent") is not None else 999)
    else:
        key = lambda item: item.get("change_percent") if item.get("change_percent") is not None else -999
    return sorted(quotes, key=key, reverse=True)


def _theme_tags(symbol: str, name: str | None = None) -> list[str]:
    code = symbol.split(".")[0]
    tags = {
        "005930": ["반도체", "대형주", "AI 인프라"],
        "000660": ["반도체", "HBM", "AI 인프라"],
        "042660": ["조선", "방산", "수주"],
        "010140": ["조선", "해양플랜트"],
        "329180": ["조선", "수주"],
        "009540": ["조선", "지주"],
        "034020": ["원전", "에너지", "인프라"],
        "373220": ["2차전지", "배터리"],
        "051910": ["화학", "2차전지"],
        "003670": ["2차전지", "소재"],
        "006400": ["2차전지", "배터리"],
        "086520": ["2차전지", "코스닥"],
        "247540": ["2차전지", "소재", "코스닥"],
        "207940": ["바이오", "CDMO"],
        "068270": ["바이오", "헬스케어"],
        "196170": ["바이오", "플랫폼", "코스닥"],
        "035420": ["인터넷", "플랫폼", "AI"],
        "035720": ["인터넷", "플랫폼"],
        "257720": ["화장품", "수출", "코스닥"],
        "003230": ["음식료", "수출"],
    }
    return tags.get(code, ["공개 관심 유니버스"])


def _research_summary(candidate: dict[str, Any]) -> str:
    change = candidate.get("change_percent")
    name = candidate.get("name") or candidate.get("symbol")
    tags = ", ".join(candidate.get("theme_tags") or _theme_tags(str(candidate.get("symbol", "")), str(name)))
    if isinstance(change, (int, float)):
        direction = "강세" if change > 0 else "약세" if change < 0 else "보합"
        return f"{name}: {direction} {change:.2f}%, 주요 점검 테마는 {tags}."
    return f"{name}: 가격 변화율 확인 필요, 주요 점검 테마는 {tags}."


def _candidate_score(candidate: dict[str, Any]) -> dict[str, Any]:
    change = candidate.get("change_percent")
    volume = candidate.get("volume") or 0
    trading_value = candidate.get("trading_value") or ((candidate.get("price") or 0) * volume)
    momentum = 50 + max(-25, min(25, float(change or 0) * 3))
    liquidity = 50
    try:
        if trading_value >= 1_000_000_000_000:
            liquidity = 90
        elif trading_value >= 300_000_000_000:
            liquidity = 78
        elif trading_value >= 100_000_000_000:
            liquidity = 66
        elif trading_value >= 30_000_000_000:
            liquidity = 55
    except Exception:
        liquidity = 50
    theme = 70 if candidate.get("theme_tags") else 50
    risk_penalty = 15 if abs(float(change or 0)) > 12 else 0
    score = round(max(0, min(100, momentum * 0.4 + liquidity * 0.35 + theme * 0.25 - risk_penalty)), 1)
    return {
        "score": score,
        "momentum": round(momentum, 1),
        "liquidity": liquidity,
        "theme": theme,
        "risk_penalty": risk_penalty,
        "interpretation": "research_watch_candidate" if score >= 60 else "needs_more_evidence",
    }


def _augment_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(candidate)
    enriched.setdefault("trading_value", (enriched.get("price") or 0) * (enriched.get("volume") or 0))
    enriched.setdefault("theme_tags", _theme_tags(str(enriched.get("symbol", "")), str(enriched.get("name", ""))))
    enriched["scorecard"] = _candidate_score(enriched)
    enriched["summary"] = _research_summary(enriched)
    return enriched


def _live_market_brief(market: str, ctx: Context | None = None) -> dict[str, Any] | None:
    symbols = MARKET_INDEX_SYMBOLS.get(market.upper(), MARKET_INDEX_SYMBOLS["ALL"])
    quotes = _quote_many(symbols, limit=len(symbols), ctx=ctx)
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


def _live_candidates(market: str, limit: int, ranking_type: str = "change_rate", ctx: Context | None = None) -> list[dict[str, Any]]:
    symbols = PUBLIC_WATCH_UNIVERSE
    if market.upper() in {"KR", "KOREA", "KOSPI", "KOSDAQ"}:
        symbols = [symbol for symbol in symbols if symbol.endswith(".KS") or symbol.endswith(".KQ")]
    elif market.upper() == "US":
        symbols = [symbol for symbol in symbols if "." not in symbol]
    scan_limit = min(len(symbols), max(limit, PUBLIC_SCAN_LIMIT))
    ranking = _kis_market_ranking(market, ranking_type, limit=scan_limit, ctx=ctx)
    quotes = ranking or _quote_many(symbols, limit=scan_limit, ctx=ctx)
    quotes = _rank_quotes(quotes, ranking_type)
    candidates = []
    for quote in quotes[: max(1, min(limit, MAX_ITEMS))]:
        candidates.append(_augment_candidate({
            "symbol": quote.get("symbol"),
            "name": quote.get("name"),
            "market": "KR" if str(quote.get("symbol", "")).endswith((".KS", ".KQ")) else "US",
            "price": quote.get("price"),
            "currency": quote.get("currency"),
            "change_percent": quote.get("change_percent"),
            "volume": quote.get("volume"),
            "trading_value": quote.get("trading_value") or ((quote.get("price") or 0) * (quote.get("volume") or 0)),
            "theme_tags": _theme_tags(str(quote.get("symbol", "")), str(quote.get("name", ""))),
            "reason": "Public watch-universe momentum and price-change scan.",
            "risk": "Needs catalyst, liquidity, and validation checks before any private decision.",
            "source_mode": quote.get("source_mode"),
        }))
    return candidates


def _find_candidate(symbol_or_name: str, ctx: Context | None = None) -> dict[str, Any] | None:
    needle = symbol_or_name.strip().lower()
    live = _quote_public(symbol_or_name, ctx)
    if live:
        return _augment_candidate({
            "symbol": live.get("symbol"),
            "name": live.get("name"),
            "market": "KR" if str(live.get("symbol", "")).endswith((".KS", ".KQ")) else "US",
            "price": live.get("price"),
            "currency": live.get("currency"),
            "change_percent": live.get("change_percent"),
            "volume": live.get("volume"),
            "trading_value": live.get("trading_value") or ((live.get("price") or 0) * (live.get("volume") or 0)),
            "theme_tags": _theme_tags(str(live.get("symbol", "")), str(live.get("name", ""))),
            "reason": "Public quote snapshot matched this query.",
            "risk": "Live/public data can be delayed or incomplete. Use as research input only.",
        })
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
def system_health(ctx: Context = None) -> dict[str, Any]:
    """Return public server health and safety boundaries."""
    state = _read_state()
    sub_engines = state.get("sub_engines", [])
    active_engines = [engine for engine in sub_engines if engine.get("status") in {"ready", "optional"}]
    credentials = _credential_context(ctx)
    return _response({
        "ok": True,
        "server": "CodexStock Research Public MCP",
        "server_status": "online",
        "data_mode": _data_mode(),
        "last_data_update": state.get("as_of", "unknown"),
        "tool_count": len(PUBLIC_TOOLS),
        "private_runtime_connected": bool(PUBLIC_DATA_DIR),
        "credential_mode": USER_CREDENTIAL_MODE,
        "active_credential_source": credentials.get("mode"),
        "user_profile_active": credentials.get("mode") == "user_profile",
        "kis_read_only_configured": _kis_configured(ctx),
        "dart_read_only_configured": _dart_configured(ctx),
        "enabled_public_sources": [
            source for source, enabled in {
                "KIS Open API read-only quote": _kis_configured(ctx),
                "OpenDART read-only disclosure/financial": _dart_configured(ctx),
                "Yahoo Finance public fallback": USE_LIVE_PUBLIC_DATA,
                "redacted CodexStock snapshots": bool(PUBLIC_DATA_DIR),
            }.items() if enabled
        ],
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
def market_brief(market: str = "ALL", ctx: Context = None) -> dict[str, Any]:
    """Summarize the broad market regime, tone, themes, and key risks."""
    state = _read_state()
    live_brief = _live_market_brief(market, ctx)
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
def resolve_stock(query: str, market: str = "ALL", limit: int = 5, ctx: Context = None) -> dict[str, Any]:
    """Resolve a stock name or code using public preview candidates."""
    matches = []
    needle = query.strip().lower()
    live = _quote_public(query, ctx)
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
def stock_snapshot(symbol_or_name: str, ctx: Context = None) -> dict[str, Any]:
    """Return a compact public snapshot for a candidate."""
    live = _quote_public(symbol_or_name, ctx)
    if live:
        return _response({
            "ok": True,
            "snapshot": _augment_candidate(live),
            "orderbook": _kis_orderbook(symbol_or_name, depth=5, ctx=ctx),
            "recent_price_history": _price_history(symbol_or_name, limit=10, ctx=ctx),
            "note": "Public market-data snapshot. It may be delayed or incomplete and is not investment advice.",
        })
    candidate = _find_candidate(symbol_or_name)
    if not candidate:
        return _response({"ok": False, "message": "No public snapshot found. Connect redacted snapshots for live data."})
    return _response({"ok": True, "snapshot": candidate, "note": "Public preview snapshot, not investment advice."})


@mcp.tool()
def market_movers(market: str = "ALL", ranking_type: str = "theme_strength", ctx: Context = None) -> dict[str, Any]:
    """Show hot-stock or theme movement categories without private account data."""
    live_candidates = _live_candidates(market, MAX_ITEMS, ranking_type, ctx)
    candidates = live_candidates or _read_state().get("candidates", [])
    return _response({
        "ok": True,
        "market": market,
        "ranking_type": ranking_type,
        "items": candidates[:MAX_ITEMS],
        "fallback_used": not bool(live_candidates),
    })


@mcp.tool()
def news_signal_summary(symbol_or_theme: str = "market", ctx: Context = None) -> dict[str, Any]:
    """Summarize public news and external signal themes."""
    candidate = _find_candidate(symbol_or_theme, ctx)
    themes = _theme_tags(str((candidate or {}).get("symbol", symbol_or_theme)), str((candidate or {}).get("name", symbol_or_theme)))
    return _response({
        "ok": True,
        "target": symbol_or_theme,
        "theme_tags": themes,
        "summary": f"Check whether {symbol_or_theme} is moving with {', '.join(themes)} themes, repeated news, disclosure timing, and market movers overlap.",
        "checks": ["source repetition", "recency", "theme relevance", "risk language", "overlap with movers", "disclosure timing"],
        "next_step": "Use catalyst_check and disclosure_financial_summary for source quality before promoting the candidate.",
    })


@mcp.tool()
def catalyst_check(symbol_or_name: str, ctx: Context = None) -> dict[str, Any]:
    """Check likely public catalysts behind a stock or theme move."""
    candidate = _find_candidate(symbol_or_name, ctx)
    target = candidate or {"symbol": symbol_or_name, "name": symbol_or_name}
    return _response({
        "ok": True,
        "target": target,
        "theme_tags": _theme_tags(str(target.get("symbol", symbol_or_name)), str(target.get("name", symbol_or_name))),
        "likely_catalyst_checks": [
            "fresh news or disclosure",
            "sector/theme rotation",
            "unusual liquidity or trading value",
            "macro-sensitive move",
            "external signal repetition",
        ],
        "quick_read": _research_summary(target) if isinstance(target, dict) else "Candidate requires public quote confirmation.",
        "research_note": "Treat catalyst results as hypotheses until source quality and timing are verified.",
    })


@mcp.tool()
def disclosure_financial_summary(symbol_or_name: str, ctx: Context = None) -> dict[str, Any]:
    """Summarize disclosure and fundamental context in public-preview form."""
    company = _dart_company(symbol_or_name, ctx)
    financial = _dart_financial(symbol_or_name, ctx=ctx)
    filings = _dart_filings(symbol_or_name, limit=5, ctx=ctx)
    if company or financial or filings:
        return _response({
            "ok": True,
            "target": symbol_or_name,
            "company": company,
            "financial": financial,
            "recent_filings": filings,
            "summary": "OpenDART read-only company and major-account data are attached when configured.",
            "checks": ["recent filings", "revenue trend", "profitability", "debt/liquidity", "one-off events"],
        })
    return _response({
        "ok": True,
        "target": symbol_or_name,
        "summary": "Disclosure and financial context should be checked before promotion.",
        "checks": ["recent filings", "revenue trend", "profitability", "debt/liquidity", "one-off events"],
    })


@mcp.tool()
def discover_candidates(market: str = "ALL", style: str = "balanced", limit: int = 5, ctx: Context = None) -> dict[str, Any]:
    """Return CodexStock watch candidates after public evidence filtering."""
    capped_limit = max(1, min(limit, MAX_ITEMS))
    ranking_type = "trading_value" if style.lower() in {"liquidity", "거래대금", "active"} else "change_rate"
    live_candidates = _live_candidates(market, capped_limit, ranking_type, ctx)
    candidates = live_candidates or _read_state().get("candidates", [])[:capped_limit]
    return _response({
        "ok": True,
        "market": market,
        "style": style,
        "candidates": candidates,
        "fallback_used": not bool(live_candidates),
        "how_to_read": "Candidates are research watch ideas ranked by public evidence. They are not buy recommendations.",
    })


@mcp.tool()
def candidate_compare(symbols_or_names: str, market: str = "ALL", ctx: Context = None) -> dict[str, Any]:
    """Compare multiple public watch candidates by evidence, risk, and next checks."""
    names = [part.strip() for part in re.split(r"[,/|]", symbols_or_names) if part.strip()]
    compared = []
    for name in names[:MAX_ITEMS]:
        candidate = _find_candidate(name, ctx) or {"symbol": name, "name": name, "reason": "No public candidate match.", "risk": "Needs evidence."}
        candidate = _augment_candidate(candidate)
        compared.append({
            "candidate": candidate,
            "scorecard": candidate.get("scorecard"),
            "strength_checks": ["theme fit", "liquidity", "catalyst clarity", "risk level"],
            "research_status": "watch_only_no_trade_recommendation",
        })
    compared.sort(key=lambda item: (item.get("scorecard") or {}).get("score", -1), reverse=True)
    return _response({
        "ok": True,
        "market": market,
        "compared": compared,
        "leader": compared[0]["candidate"] if compared else None,
        "how_to_use": "Use comparison to decide what deserves deeper private research, not to issue a trade.",
    })


@mcp.tool()
def explain_candidate(symbol_or_name: str, ctx: Context = None) -> dict[str, Any]:
    """Explain one watch candidate's evidence, weakness, and invalidation checks."""
    candidate = _find_candidate(symbol_or_name, ctx)
    if not candidate:
        return _response({"ok": False, "message": "Candidate not found in public preview data."})
    return _response({
        "ok": True,
        "candidate": candidate,
        "scorecard": candidate.get("scorecard"),
        "recent_price_history": _price_history(symbol_or_name, limit=10, ctx=ctx),
        "recent_filings": _dart_filings(symbol_or_name, limit=3, ctx=ctx),
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
def ai_staff_opinions(symbol_or_name: str = "market", ctx: Context = None) -> dict[str, Any]:
    """Show public AI staff viewpoints."""
    return _response({"ok": True, "target": symbol_or_name, "staff": _read_state().get("staff", [])})


@mcp.tool()
def ai_research_consensus(symbol_or_name: str = "market", allocation_percent: float = 0.0, ctx: Context = None) -> dict[str, Any]:
    """Show a public CodexStock-style AI research consensus observation."""
    candidate = _find_candidate(symbol_or_name, ctx) or {
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
def strategy_validation_summary(strategy_name: str = "public-preview", ctx: Context = None) -> dict[str, Any]:
    """Summarize strategy validation status without private performance claims."""
    history = _price_history(strategy_name, limit=20, ctx=ctx)
    history_note = "Attached public recent price history for the requested symbol-like strategy name." if history else "No symbol-like price history attached."
    return _response({
        "ok": True,
        "strategy": strategy_name,
        "status": "research preview",
        "required_evidence": ["walk-forward", "out-of-sample", "cost/slippage", "stress test", "paper observation"],
        "recent_price_history": history,
        "history_note": history_note,
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
