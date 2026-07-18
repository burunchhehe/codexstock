from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


TOSS_INFO_BASE_URL = "https://wts-info-api.tossinvest.com"
TOSS_CERT_BASE_URL = "https://wts-cert-api.tossinvest.com"
DEFAULT_TIMEOUT_SEC = 8
DEFAULT_CACHE_TTL_SEC = 20

ALLOWED_CHART_RANGES = {"min:1", "day:1", "week:1", "month:1"}
ALLOWED_SECURITIES_TYPES = {"kr-s", "us-s"}


def normalize_product_code(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    if value.isdigit() and len(value) == 6:
        return f"A{value}"
    return value


def company_code(symbol: str) -> str:
    code = normalize_product_code(symbol)
    return code[1:] if code.startswith("A") and code[1:].isdigit() else code


def _as_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _build_path(path: str, params: dict[str, Any] | None = None) -> str:
    if not params:
        return path
    query = urllib.parse.urlencode(
        {key: value for key, value in params.items() if value is not None}
    )
    return f"{path}?{query}" if query else path


def _extract_result(payload: dict[str, Any]) -> Any:
    if "result" not in payload:
        raise RuntimeError("토스 공개 API 응답에 result가 없습니다.")
    return payload["result"]


def _limited(items: Any, limit: int) -> list[Any]:
    if isinstance(items, list):
        return items[: max(0, limit)]
    return []


def _sma(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < period:
            result.append(None)
            continue
        window = values[index + 1 - period : index + 1]
        result.append(round(sum(window) / period, 4))
    return result


def _rsi(values: list[float], period: int = 14) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result
    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, period + 1):
        delta = values[index] - values[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    result[period] = 100.0 if avg_loss == 0 else round(100 - (100 / (1 + avg_gain / avg_loss)), 4)
    for index in range(period + 1, len(values)):
        delta = values[index] - values[index - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        result[index] = 100.0 if avg_loss == 0 else round(100 - (100 / (1 + avg_gain / avg_loss)), 4)
    return result


@dataclass
class TossPublicDataAdapter:
    """Read-only adapter for public TossInvest web market data.

    This intentionally excludes login, account, balance, holding, and order endpoints.
    """

    timeout_sec: int = DEFAULT_TIMEOUT_SEC
    cache_ttl_sec: int = DEFAULT_CACHE_TTL_SEC
    user_agent: str = "Mozilla/5.0 CodexStock/1.0"
    _cache: dict[str, tuple[float, dict[str, Any]]] = field(default_factory=dict)
    _last_request_at: float = 0.0

    def status(self) -> dict[str, Any]:
        return {
            "provider": "TossInvest public web",
            "configured": True,
            "readonly": True,
            "order_allowed": False,
            "account_allowed": False,
            "official_open_api": False,
            "base_url": TOSS_INFO_BASE_URL,
            "cache_ttl_sec": self.cache_ttl_sec,
            "message": "토스증권 공개 웹 데이터만 읽는 보조 레이더입니다. 주문/계좌/로그인은 사용하지 않습니다.",
        }

    def summary(self, symbol: str = "005930", include_overview: bool = False) -> dict[str, Any]:
        code = normalize_product_code(symbol)
        try:
            info = _extract_result(self._get(f"/api/v2/stock-infos/{code}"))
            prices = _extract_result(
                self._get(_build_path("/api/v3/stock-prices/details", {"productCodes": code}))
            )
            price = self._find_price(prices, code)
            overview = None
            if include_overview:
                overview = _extract_result(self._get(f"/api/v2/stock-infos/{code}/overview"))
            return {
                "ok": True,
                "source": "toss_public",
                "symbol": company_code(code),
                "product_code": code,
                "name": info.get("name") or info.get("companyName") or company_code(code),
                "market": (info.get("market") or {}).get("displayName") if isinstance(info.get("market"), dict) else info.get("market"),
                "currency": info.get("currency"),
                "price": self._normalize_price(price),
                "info": info,
                "overview": overview,
                "safety": "공개 웹 데이터 읽기전용. 주문/계좌 데이터가 아닙니다.",
            }
        except Exception as exc:
            return self._error(symbol, "summary", exc)

    def quote(self, symbol: str = "005930", ticks: int = 5) -> dict[str, Any]:
        code = normalize_product_code(symbol)
        ticks = max(0, min(int(ticks or 0), 30))
        try:
            quote = _extract_result(
                self._get(
                    _build_path(
                        f"/api/v3/stock-prices/{code}/quotes",
                        {"investMode": "krx", "fallbackKrx": "true"},
                    )
                )
            )
            tick_rows: list[Any] = []
            if ticks:
                tick_rows = _limited(
                    _extract_result(
                        self._get(
                            _build_path(
                                f"/api/v2/stock-prices/{code}/ticks",
                                {"viewType": "krx", "count": ticks, "investMode": "krx"},
                            )
                        )
                    ),
                    ticks,
                )
            return {
                "ok": True,
                "source": "toss_public",
                "symbol": company_code(code),
                "product_code": code,
                "quote": quote,
                "ticks": tick_rows,
                "safety": "토스 공개 호가/틱 조회입니다. 주문 전송 기능은 없습니다.",
            }
        except Exception as exc:
            return self._error(symbol, "quote", exc)

    def chart(
        self,
        symbol: str = "005930",
        range_value: str = "day:1",
        count: int = 120,
        securities_type: str = "kr-s",
        include_indicators: bool = True,
    ) -> dict[str, Any]:
        code = normalize_product_code(symbol)
        range_value = range_value if range_value in ALLOWED_CHART_RANGES else "day:1"
        securities_type = securities_type if securities_type in ALLOWED_SECURITIES_TYPES else "kr-s"
        count = max(1, min(int(count or 120), 300))
        try:
            chart = _extract_result(
                self._get(
                    _build_path(
                        f"/api/v1/c-chart/{securities_type}/{code}/{range_value}",
                        {
                            "count": count,
                            "session": "all",
                            "investMode": "krx",
                            "useAdjustedRate": "true",
                        },
                    )
                )
            )
            candles = chart.get("candles", []) if isinstance(chart, dict) else []
            normalized = [self._normalize_candle(row) for row in _limited(candles, count)]
            indicators = self._indicators(normalized) if include_indicators else {}
            return {
                "ok": True,
                "source": "toss_public",
                "symbol": company_code(code),
                "product_code": code,
                "range": range_value,
                "securities_type": securities_type,
                "count": len(normalized),
                "candles": normalized,
                "indicators": indicators,
                "raw_meta": {key: value for key, value in chart.items() if key != "candles"} if isinstance(chart, dict) else {},
                "safety": "토스 공개 차트 데이터와 로컬 보조지표 계산입니다.",
            }
        except Exception as exc:
            return self._error(symbol, "chart", exc)

    def radar(self, symbols: list[str] | None = None) -> dict[str, Any]:
        target_symbols = symbols or ["005930", "000660", "083450"]
        rows = []
        for symbol in target_symbols[:8]:
            summary = self.summary(symbol, include_overview=False)
            chart = self.chart(symbol, count=80, include_indicators=True)
            rows.append(self._radar_row(symbol, summary, chart))
            time.sleep(0.12)
        ok_rows = [row for row in rows if row.get("ok")]
        return {
            "ok": bool(ok_rows),
            "source": "toss_public",
            "items": rows,
            "summary": {
                "checked": len(rows),
                "ok": len(ok_rows),
                "top": ok_rows[0].get("symbol") if ok_rows else None,
            },
            "safety": "토스 공개 데이터 기반 보조 레이더입니다. 주문/투자자문이 아닙니다.",
        }

    def _radar_row(self, symbol: str, summary: dict[str, Any], chart: dict[str, Any]) -> dict[str, Any]:
        price = summary.get("price", {}) if isinstance(summary.get("price"), dict) else {}
        indicators = chart.get("indicators", {}) if isinstance(chart.get("indicators"), dict) else {}
        latest = indicators.get("latest", {}) if isinstance(indicators.get("latest"), dict) else {}
        close = _as_float(price.get("close"))
        change_pct = _as_float(price.get("change_pct"))
        rsi = latest.get("rsi14")
        score = 50.0
        score += max(-15.0, min(15.0, change_pct * 1.5))
        if isinstance(rsi, (int, float)):
            if rsi < 35:
                score += 8
            elif rsi > 75:
                score -= 8
        return {
            "ok": bool(summary.get("ok")) and bool(chart.get("ok")),
            "symbol": summary.get("symbol") or company_code(symbol),
            "product_code": summary.get("product_code") or normalize_product_code(symbol),
            "name": summary.get("name") or symbol,
            "price": close,
            "change_pct": change_pct,
            "volume": _as_int(price.get("volume")),
            "market_cap": _as_float(price.get("market_cap")),
            "rsi14": rsi,
            "sma20": latest.get("sma20"),
            "score": round(max(0.0, min(100.0, score)), 2),
            "message": "토스 공개 보조 데이터 정상" if summary.get("ok") else summary.get("message"),
        }

    def _get(self, path: str, base_url: str = TOSS_INFO_BASE_URL) -> dict[str, Any]:
        self._validate_path(path, base_url)
        key = f"GET {base_url}{path}"
        now = time.time()
        cached = self._cache.get(key)
        if cached and cached[0] > now:
            return cached[1]
        self._throttle()
        request = urllib.request.Request(
            base_url + path,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.tossinvest.com",
                "Referer": "https://www.tossinvest.com/",
                "User-Agent": self.user_agent,
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {403, 429}:
                raise RuntimeError(f"토스 공개 API HTTP {exc.code}: 자동 재시도 없이 중단합니다.") from exc
            raise RuntimeError(f"토스 공개 API HTTP {exc.code}: {path}") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            raise RuntimeError(f"토스 공개 API 요청 실패: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("토스 공개 API가 JSON 객체를 반환하지 않았습니다.")
        self._cache[key] = (now + self.cache_ttl_sec, payload)
        return payload

    def _validate_path(self, path: str, base_url: str) -> None:
        parsed = urllib.parse.urlsplit(path)
        if parsed.scheme or parsed.netloc:
            raise RuntimeError("토스 공개 API 경로는 상대경로만 허용합니다.")
        lowered = parsed.path.lower()
        denied = ("account", "balance", "holding", "holdings", "login", "order", "orders", "transfer", "auth", "token")
        if any(marker in lowered for marker in denied):
            raise RuntimeError(f"토스 공개 API 금지 경로 차단: {parsed.path}")
        if base_url == TOSS_INFO_BASE_URL and not parsed.path.startswith(("/api/v1/", "/api/v2/", "/api/v3/")):
            raise RuntimeError(f"허용되지 않은 토스 공개 API 경로: {parsed.path}")
        if base_url == TOSS_CERT_BASE_URL:
            allowed = {"/api/v1/screener/screen/count", "/api/v2/screener/screen"}
            if parsed.path not in allowed:
                raise RuntimeError(f"허용되지 않은 토스 cert API 경로: {parsed.path}")

    def _throttle(self) -> None:
        wait = 0.12 - (time.time() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.time()

    def _find_price(self, rows: Any, code: str) -> dict[str, Any]:
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and str(row.get("code", "")).upper() == code:
                    return row
            if rows and isinstance(rows[0], dict):
                return rows[0]
        return {}

    def _normalize_price(self, row: dict[str, Any]) -> dict[str, Any]:
        close = _as_float(row.get("close"))
        base = _as_float(row.get("base")) or close
        change_pct = ((close / base) - 1) * 100 if base else 0.0
        return {
            "close": close,
            "open": _as_float(row.get("open")),
            "high": _as_float(row.get("high")),
            "low": _as_float(row.get("low")),
            "base": base,
            "change_pct": round(change_pct, 2),
            "change_type": row.get("changeType"),
            "volume": _as_int(row.get("volume")),
            "value": _as_float(row.get("value")),
            "market_cap": _as_float(row.get("marketCap")),
            "trade_datetime": row.get("tradeDateTime"),
        }

    def _normalize_candle(self, row: Any) -> dict[str, Any]:
        if not isinstance(row, dict):
            return {}
        return {
            "dt": row.get("dt"),
            "open": _as_float(row.get("open")),
            "high": _as_float(row.get("high")),
            "low": _as_float(row.get("low")),
            "close": _as_float(row.get("close")),
            "volume": _as_int(row.get("volume")),
            "amount": _as_float(row.get("amount")),
            "base": _as_float(row.get("base")),
        }

    def _indicators(self, candles: list[dict[str, Any]]) -> dict[str, Any]:
        ordered = sorted(
            [row for row in candles if isinstance(row, dict) and row.get("dt")],
            key=lambda row: str(row.get("dt")),
        )
        if not ordered:
            ordered = [row for row in candles if isinstance(row, dict)]
        closes = [_as_float(row.get("close")) for row in ordered if row.get("close") is not None]
        if not closes:
            return {"latest": {}}
        rsi14 = _rsi(closes, 14)
        sma5 = _sma(closes, 5)
        sma20 = _sma(closes, 20)
        latest = {
            "dt": ordered[-1].get("dt") if ordered else None,
            "close": closes[-1],
            "rsi14": rsi14[-1],
            "sma5": sma5[-1],
            "sma20": sma20[-1],
        }
        return {
            "latest": latest,
            "series": {
                "rsi14": rsi14[-30:],
                "sma5": sma5[-30:],
                "sma20": sma20[-30:],
            },
            "source": "local calculation from TossInvest c-chart candles",
        }

    def _error(self, symbol: str, action: str, exc: Exception) -> dict[str, Any]:
        return {
            "ok": False,
            "source": "toss_public",
            "symbol": company_code(symbol),
            "product_code": normalize_product_code(symbol),
            "action": action,
            "message": str(exc),
            "safety": "오류 발생 시 자동 재시도/우회 없이 중단합니다.",
        }
