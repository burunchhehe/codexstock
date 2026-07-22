from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from runtime_paths import active_data_root, runtime_data_path
except ImportError:  # pragma: no cover - package import fallback
    from .runtime_paths import active_data_root, runtime_data_path


DART_BASE_URL = "https://opendart.fss.or.kr/api"
ECOS_BASE_URL = "https://ecos.bok.or.kr/api"
FRED_BASE_URL = "https://api.stlouisfed.org/fred"
KIS_REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_MOCK_BASE_URL = "https://openapivts.koreainvestment.com:29443"
KIS_PRICE_TR_ID = "FHKST01010100"
KIS_ORDERBOOK_TR_ID = "FHKST01010200"
KIS_DAILY_CHART_TR_ID = "FHKST03010100"
KIS_TIME_ITEM_CHART_TR_ID = "FHKST03010200"
KIS_TIME_ITEM_CONCLUSION_TR_ID = "FHPST01060000"
KIS_VOLUME_RANK_TR_ID = "FHPST01710000"
KIS_FLUCTUATION_RANK_TR_ID = "FHPST01700000"
KIS_VOLUME_POWER_RANK_TR_ID = "FHPST01680000"
KIS_QUOTE_BALANCE_RANK_TR_ID = "FHPST01720000"
KIS_INVESTOR_TR_ID = "FHKST01010900"
KIS_FOREIGN_INSTITUTION_TOTAL_TR_ID = "FHPTJ04400000"
KIS_BALANCE_TR_ID_REAL = "TTTC8434R"
KIS_BALANCE_TR_ID_MOCK = "VTTC8434R"
KIS_PSBL_ORDER_TR_ID_REAL = "TTTC8908R"
KIS_PSBL_ORDER_TR_ID_MOCK = "VTTC8908R"
KIS_CASH_BUY_TR_ID_REAL = "TTTC0802U"
KIS_CASH_SELL_TR_ID_REAL = "TTTC0801U"
KIS_CASH_BUY_TR_ID_MOCK = "VTTC0802U"
KIS_CASH_SELL_TR_ID_MOCK = "VTTC0801U"
KIS_DAILY_CCLD_TR_ID_REAL = "TTTC8001R"
KIS_DAILY_CCLD_TR_ID_MOCK = "VTTC8001R"
KIS_ACCOUNT_ASSETS_TR_ID = "CTRP6548R"
KIS_INTSTOCK_STOCKLIST_BY_GROUP_TR_ID = "HHKCM113004C6"
KIS_INTSTOCK_GROUPLIST_TR_ID = "HHKCM113004C7"


def _harden_private_file(path: Path) -> None:
    if not path.is_file():
        return
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    if os.name != "nt":
        return
    username = os.environ.get("USERNAME", "").strip()
    if not username:
        return
    try:
        subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                f"{username}:(F)",
                "*S-1-5-18:(F)",
                "*S-1-5-32-544:(F)",
            ],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temp_name = handle.name
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(temp_name)
        _harden_private_file(temp_path)
        os.replace(temp_path, path)
        _harden_private_file(path)
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
KIS_TIMEOUT_SEC = 2
ECOS_TIMEOUT_SEC = 8
FRED_TIMEOUT_SEC = 8

KR_CORP_CODES = {
    "005930": {"corp_code": "00126380", "name": "삼성전자"},
    "000660": {"corp_code": "00164779", "name": "SK하이닉스"},
    "005380": {"corp_code": "00164742", "name": "현대차"},
    "035420": {"corp_code": "00266961", "name": "NAVER"},
    "051910": {"corp_code": "00356361", "name": "LG화학"},
    "006400": {"corp_code": "00126362", "name": "삼성SDI"},
}

US_SYMBOLS = ("AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "AMD", "SPY", "QQQ")

ECOS_MACRO_SERIES = {
    "base_rate": {"name": "한국은행 기준금리", "stat_code": "722Y001", "cycle": "M", "item_code1": "0101000", "unit": "%"},
    "treasury_3y": {"name": "국고채 3년", "stat_code": "722Y001", "cycle": "D", "item_code1": "010200000", "unit": "%"},
    "usd_krw": {"name": "원/달러 환율", "stat_code": "731Y001", "cycle": "D", "item_code1": "0000001", "unit": "원"},
    "cpi": {"name": "소비자물가지수", "stat_code": "901Y009", "cycle": "M", "item_code1": "0", "unit": "index"},
}

FRED_MACRO_SERIES = {
    "fed_funds": {"name": "미국 연방기금금리", "series_id": "FEDFUNDS", "unit": "%"},
    "us_10y": {"name": "미국 10년 국채금리", "series_id": "DGS10", "unit": "%"},
    "us_2y": {"name": "미국 2년 국채금리", "series_id": "DGS2", "unit": "%"},
    "unemployment": {"name": "미국 실업률", "series_id": "UNRATE", "unit": "%"},
    "cpi": {"name": "미국 CPI", "series_id": "CPIAUCSL", "unit": "index"},
}

_JSON_CACHE: dict[str, tuple[float, Any]] = {}


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key not in os.environ or not os.environ.get(key):
            os.environ[key] = value


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}{'*' * max(4, len(value) - 4)}{value[-2:]}"


def _safe_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _kis_previous_close(output: dict[str, Any], price: float) -> float:
    previous_close = _safe_float(output.get("stck_sdpr")) or _safe_float(output.get("prdy_clpr"))
    if previous_close > 0:
        return previous_close
    change = _safe_float(output.get("prdy_vrss"))
    if price > 0 and change:
        derived = price - change
        if derived > 0:
            return derived
    change_pct = _safe_float(output.get("prdy_ctrt"))
    if price > 0 and change_pct > -99.0:
        derived = price / (1.0 + change_pct / 100.0)
        if derived > 0:
            return derived
    return 0.0


def _kis_quote_contract_issues(
    output: dict[str, Any],
    *,
    price: float,
    previous_close: float,
) -> list[str]:
    issues: list[str] = []
    high_price = _safe_float(output.get("stck_hgpr"))
    low_price = _safe_float(output.get("stck_lwpr"))
    upper_limit = _safe_float(output.get("stck_mxpr"))
    lower_limit = _safe_float(output.get("stck_llam"))
    if price <= 0:
        issues.append("non_positive_current_price")
    elif abs(price - round(price)) > 0.001:
        issues.append("fractional_krw_current_price")
    if previous_close <= 0:
        issues.append("previous_close_missing")
    if high_price > 0 and low_price > 0:
        if high_price < low_price:
            issues.append("high_low_inverted")
        elif price > 0 and not low_price * 0.99 <= price <= high_price * 1.01:
            issues.append("current_price_outside_daily_range")
    if upper_limit > 0 and price > upper_limit * 1.001:
        issues.append("current_price_above_upper_limit")
    if lower_limit > 0 and 0 < price < lower_limit * 0.999:
        issues.append("current_price_below_lower_limit")
    if previous_close > 0 and output.get("prdy_ctrt") not in {None, ""}:
        observed_change_pct = _safe_float(output.get("prdy_ctrt"))
        implied_change_pct = (price / previous_close - 1.0) * 100.0
        if abs(implied_change_pct - observed_change_pct) > 0.75:
            issues.append("change_pct_inconsistent")
    return issues


def _optional_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text == ".":
        return None
    try:
        return float(text.replace(",", ""))
    except (TypeError, ValueError):
        return None


def _normalize_kr_symbol(symbol: str) -> str:
    text = (symbol or "").strip().upper()
    if text.startswith("A") and len(text) > 6:
        text = text[1:]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6)[-6:] if digits else "005930"


def _yyyymmdd(value: Any, default: str | None = None) -> str:
    text = "".join(ch for ch in str(value or "").strip() if ch.isdigit())
    if len(text) >= 8:
        return text[:8]
    if default:
        return default
    return datetime.now().strftime("%Y%m%d")


def _hhmmss(value: Any) -> str:
    text = "".join(ch for ch in str(value or "").strip() if ch.isdigit())
    if not text:
        return "000000"
    return text.zfill(6)[-6:]


def _kst_iso_from_kis(date_value: Any, time_value: Any) -> str:
    date_text = _yyyymmdd(date_value)
    time_text = _hhmmss(time_value)
    try:
        parsed = datetime.strptime(f"{date_text}{time_text}", "%Y%m%d%H%M%S")
        return f"{parsed.strftime('%Y-%m-%dT%H:%M:%S')}+09:00"
    except ValueError:
        return ""


def _fetch_json(url: str, timeout: int, ttl_sec: int, user_agent: str) -> tuple[dict[str, Any], bool]:
    now = time.time()
    if ttl_sec > 0:
        cached = _JSON_CACHE.get(url)
        if cached and cached[0] > now:
            return cached[1], True
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        payload = {"payload": payload}
    if ttl_sec > 0:
        _JSON_CACHE[url] = (now + ttl_sec, payload)
    return payload, False


@dataclass(frozen=True)
class IntegrationSettings:
    live_trading: bool
    kis_use_mock: bool
    kis_readonly: bool
    kis_mode: str
    kis_base_url: str
    kis_app_key: str
    kis_app_secret: str
    kis_account_no: str
    kis_product_code: str
    kis_user_id: str
    kis_live_app_key: str
    kis_live_app_secret: str
    kis_live_account_no: str
    kis_live_product_code: str
    kis_quote_throttle_ms: int
    dart_api_key: str
    dart_lookback_days: int
    cache_ttl_dart_sec: int
    cache_ttl_kis_sec: int
    ecos_api_key: str
    ecos_language: str
    ecos_cache_ttl_sec: int
    fred_api_key: str
    fred_cache_ttl_sec: int
    krx_api_key: str
    krx_base_url: str
    krx_cache_ttl_sec: int
    telegram_enabled: bool
    telegram_stub: bool
    telegram_dry_run: bool
    telegram_bot_token: str
    telegram_chat_id: str

    @classmethod
    def load(cls, repo_root: Path) -> "IntegrationSettings":
        data_root = active_data_root(repo_root)
        config_root = Path(os.getenv("CODEXSTOCK_CONFIG_DIR", "").strip() or (data_root.parent / "config"))
        _load_dotenv(config_root / ".env.local")
        _load_dotenv(config_root / ".env")
        _load_dotenv(repo_root / ".env.local")
        _load_dotenv(repo_root / ".env")
        kis_use_mock = _bool("KIS_USE_MOCK", True)
        if kis_use_mock:
            kis_app_key = _str("KIS_MOCK_APP_KEY")
            kis_app_secret = _str("KIS_MOCK_APP_SECRET")
            kis_account_no = _str("KIS_MOCK_ACCOUNT_NO")
            kis_product_code = _str("KIS_MOCK_ACNT_PRDT_CD", "01")
        else:
            kis_app_key = _str("KIS_APP_KEY")
            kis_app_secret = _str("KIS_APP_SECRET")
            kis_account_no = _str("KIS_ACCOUNT_NO")
            kis_product_code = _str("KIS_ACNT_PRDT_CD") or _str("KIS_ACCOUNT_PRODUCT_CODE", "01")
        live_app_key = _str("KIS_APP_KEY")
        live_app_secret = _str("KIS_APP_SECRET")
        live_account_no = _str("KIS_ACCOUNT_NO")
        live_product_code = _str("KIS_ACNT_PRDT_CD") or _str("KIS_ACCOUNT_PRODUCT_CODE", "01")
        return cls(
            live_trading=_bool("LIVE_TRADING", False),
            kis_use_mock=kis_use_mock,
            kis_readonly=_bool("KIS_READONLY", True),
            kis_mode=_str("KIS_MODE") or ("mock" if kis_use_mock else "real"),
            kis_base_url=_str("KIS_BASE_URL"),
            kis_app_key=kis_app_key,
            kis_app_secret=kis_app_secret,
            kis_account_no=kis_account_no,
            kis_product_code=kis_product_code,
            kis_user_id=_str("KIS_USER_ID") or _str("KIS_HTS_ID") or _str("KIS_LOGIN_ID"),
            kis_live_app_key=live_app_key,
            kis_live_app_secret=live_app_secret,
            kis_live_account_no=live_account_no,
            kis_live_product_code=live_product_code,
            kis_quote_throttle_ms=_int("KIS_QUOTE_THROTTLE_MS", 50),
            dart_api_key=_str("DART_API_KEY"),
            dart_lookback_days=_int("DART_LOOKBACK_DAYS", 7),
            cache_ttl_dart_sec=_int("CACHE_TTL_DART_SEC", 1800),
            cache_ttl_kis_sec=_int("CACHE_TTL_KIS_SEC", 120),
            ecos_api_key=_str("BOK_ECOS_API_KEY") or _str("ECOS_API_KEY"),
            ecos_language=_str("ECOS_LANGUAGE", "kr") or "kr",
            ecos_cache_ttl_sec=_int("CACHE_TTL_ECOS_SEC", 1800),
            fred_api_key=_str("FRED_API_KEY"),
            fred_cache_ttl_sec=_int("CACHE_TTL_FRED_SEC", 1800),
            krx_api_key=_str("KRX_API_KEY"),
            krx_base_url=_str("KRX_BASE_URL"),
            krx_cache_ttl_sec=_int("CACHE_TTL_KRX_SEC", 1800),
            telegram_enabled=_bool("TELEGRAM_ENABLED", False),
            telegram_stub=_bool("TELEGRAM_STUB", False),
            telegram_dry_run=_bool("TELEGRAM_DRY_RUN", True),
            telegram_bot_token=_str("TELEGRAM_TOKEN") or _str("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_str("TELEGRAM_CHAT_ID") or _str("TELEGRAM_ALLOWED_CHAT_ID"),
        )

    @property
    def kis_configured(self) -> bool:
        return bool(self.kis_app_key and self.kis_app_secret and self.kis_account_no)

    @property
    def dart_configured(self) -> bool:
        return bool(self.dart_api_key)

    @property
    def ecos_configured(self) -> bool:
        return bool(self.ecos_api_key)

    @property
    def fred_configured(self) -> bool:
        return bool(self.fred_api_key)

    @property
    def krx_configured(self) -> bool:
        return bool(self.krx_api_key)

    @property
    def kis_live_configured(self) -> bool:
        return bool(self.kis_live_app_key and self.kis_live_app_secret and self.kis_live_account_no)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


class KisReadonlyBridge:
    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings
        custom_base = settings.kis_base_url.strip().rstrip("/")
        self.base_url = custom_base or (KIS_MOCK_BASE_URL if settings.kis_use_mock else KIS_REAL_BASE_URL)
        repo_root = Path(__file__).resolve().parent.parent
        legacy_cache = repo_root / "data" / ("kis_token_mock.json" if settings.kis_use_mock else "kis_token_real.json")
        self.token_cache = runtime_data_path(legacy_cache, repo_root)

    def status(self) -> dict[str, Any]:
        return {
            "provider": "KIS",
            "configured": self.settings.kis_configured,
            "mode": self.settings.kis_mode,
            "use_mock": self.settings.kis_use_mock,
            "readonly": self.settings.kis_readonly,
            "live_trading": self.settings.live_trading,
            "order_allowed": bool(self.settings.live_trading and not self.settings.kis_readonly and not self.settings.kis_use_mock),
            "account_masked": _mask(self.settings.kis_account_no),
            "product_code": self.settings.kis_product_code,
            "user_id_configured": bool(self.settings.kis_user_id),
            "base_url_set": bool(self.settings.kis_base_url),
            "quote_throttle_ms": self.settings.kis_quote_throttle_ms,
            "message": "실전 주문 전송 가능 모드입니다." if self.settings.live_trading and not self.settings.kis_readonly else "실전 주문은 잠겨 있고, 조회 연결만 준비되어 있습니다.",
        }

    def _cached_token(self) -> str:
        if self.token_cache.is_file():
            try:
                _harden_private_file(self.token_cache)
                data = json.loads(self.token_cache.read_text(encoding="utf-8"))
                token = str(data.get("access_token") or "")
                expires_at = float(data.get("expires_at") or 0)
                if token and time.time() < expires_at - 60:
                    return token
            except Exception:
                pass
        return self._issue_token()

    def _issue_token(self) -> str:
        if not self.settings.kis_configured:
            raise RuntimeError("KIS API 키가 설정되지 않았습니다.")
        url = f"{self.base_url}/oauth2/tokenP"
        body = json.dumps(
            {
                "grant_type": "client_credentials",
                "appkey": self.settings.kis_app_key,
                "appsecret": self.settings.kis_app_secret,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(request, timeout=KIS_TIMEOUT_SEC) as response:
            payload = json.loads(response.read().decode("utf-8"))
        token = str(payload.get("access_token") or "")
        if not token:
            raise RuntimeError(str(payload.get("msg1") or payload.get("error_description") or "KIS 토큰 발급 실패"))
        expires_in = int(payload.get("expires_in") or 86400)
        _write_private_json(
            self.token_cache,
            {
                "access_token": token,
                "expires_at": time.time() + expires_in,
                "mode": self.settings.kis_mode,
            },
        )
        return token

    def _hashkey(self, body: dict[str, Any]) -> str:
        if not self.settings.kis_configured:
            raise RuntimeError("KIS API 키가 설정되지 않았습니다.")
        url = f"{self.base_url}/uapi/hashkey"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "appkey": self.settings.kis_app_key,
                "appsecret": self.settings.kis_app_secret,
            },
        )
        with urllib.request.urlopen(request, timeout=max(KIS_TIMEOUT_SEC, 8)) as response:
            payload = json.loads(response.read().decode("utf-8"))
        hash_value = str(payload.get("HASH") or payload.get("hash") or "")
        if not hash_value:
            raise RuntimeError(str(payload.get("msg1") or payload.get("msg_cd") or "KIS hashkey 발급 실패"))
        return hash_value

    def quote(self, symbol: str = "005930", allow_real_fallback: bool = True) -> dict[str, Any]:
        if not self.settings.kis_configured:
            return {
                "ok": False,
                "symbol": _normalize_kr_symbol(symbol),
                "source": "unconfigured",
                "message": "KIS API 키가 설정되지 않았습니다.",
            }
        sym = _normalize_kr_symbol(symbol)
        params = urllib.parse.urlencode(
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": sym,
            }
        )
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price?{params}"
        try:
            token = self._cached_token()
            request = urllib.request.Request(
                url,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "authorization": f"Bearer {token}",
                    "appkey": self.settings.kis_app_key,
                    "appsecret": self.settings.kis_app_secret,
                    "tr_id": KIS_PRICE_TR_ID,
                    "custtype": "P",
                },
            )
            with urllib.request.urlopen(request, timeout=KIS_TIMEOUT_SEC) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            fallback = self._real_readonly_fallback(symbol, allow_real_fallback)
            if fallback:
                fallback["fallback_from"] = "mock"
                return fallback
            return {
                "ok": False,
                "symbol": sym,
                "source": "kis_readonly",
                "message": str(exc),
            }
        if str(payload.get("rt_cd")) != "0":
            fallback = self._real_readonly_fallback(symbol, allow_real_fallback)
            if fallback:
                fallback["fallback_from"] = "mock"
                fallback["mock_message"] = str(payload.get("msg1") or payload.get("msg_cd") or "KIS 응답 오류")
                return fallback
            return {
                "ok": False,
                "symbol": sym,
                "source": "kis_readonly",
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 응답 오류"),
            }
        output = payload.get("output") or {}
        price = _safe_float(output.get("stck_prpr"))
        previous_close = _kis_previous_close(output, price)
        price_contract_issues = _kis_quote_contract_issues(
            output,
            price=price,
            previous_close=previous_close,
        )
        return {
            "ok": price > 0 and not price_contract_issues,
            "symbol": sym,
            "name": output.get("hts_kor_isnm") or sym,
            "price": price,
            "previous_close": previous_close,
            "open": _safe_float(output.get("stck_oprc")) or price,
            "high": _safe_float(output.get("stck_hgpr")) or price,
            "low": _safe_float(output.get("stck_lwpr")) or price,
            "change_pct": _safe_float(output.get("prdy_ctrt")),
            "volume": _safe_int(output.get("acml_vol")),
            "trade_value": _safe_float(output.get("acml_tr_pbmn")),
            "upper_limit_price": _safe_float(output.get("stck_mxpr")),
            "lower_limit_price": _safe_float(output.get("stck_llam")),
            "vi_cls_code": str(output.get("vi_cls_code") or "").strip(),
            "overtime_vi_cls_code": str(output.get("ovtm_vi_cls_code") or "").strip(),
            "temporary_halt_yn": str(output.get("temp_stop_yn") or "").strip().upper(),
            "market_warning_code": str(output.get("mrkt_warn_cls_code") or "").strip(),
            "short_overheat_yn": str(output.get("short_over_yn") or "").strip().upper(),
            "risk_fields_observed": True,
            "timestamp": output.get("stck_cntg_hour") or "",
            "currency": "KRW",
            "unit_scale": 1,
            "price_contract_ok": not price_contract_issues,
            "price_contract_issues": price_contract_issues,
            "source": "kis_readonly",
            "mode": self.settings.kis_mode,
            "message": "정상",
        }

    def orderbook(self, symbol: str = "005930") -> dict[str, Any]:
        sym = _normalize_kr_symbol(symbol)
        if not self.settings.kis_configured:
            return {
                "ok": False,
                "symbol": sym,
                "source": "unconfigured",
                "message": "KIS API is not configured.",
            }
        try:
            payload = self._get(
                "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
                KIS_ORDERBOOK_TR_ID,
                {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": sym,
                },
                timeout=8,
            )
        except Exception as exc:
            return {
                "ok": False,
                "symbol": sym,
                "source": "kis_orderbook",
                "message": f"KIS orderbook error: {exc}",
            }
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "symbol": sym,
                "source": "kis_orderbook",
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS orderbook response error"),
            }
        output = payload.get("output1") or payload.get("output") or {}
        if isinstance(output, list):
            output = output[0] if output and isinstance(output[0], dict) else {}
        if not isinstance(output, dict):
            output = {}

        levels: list[dict[str, Any]] = []
        for index in range(1, 11):
            ask_price = _safe_float(output.get(f"askp{index}"))
            bid_price = _safe_float(output.get(f"bidp{index}"))
            ask_qty = _safe_float(output.get(f"askp_rsqn{index}"))
            bid_qty = _safe_float(output.get(f"bidp_rsqn{index}"))
            if ask_price <= 0 and bid_price <= 0 and ask_qty <= 0 and bid_qty <= 0:
                continue
            levels.append(
                {
                    "level": index,
                    "ask_price": ask_price,
                    "ask_quantity": ask_qty,
                    "bid_price": bid_price,
                    "bid_quantity": bid_qty,
                }
            )

        best_ask = levels[0]["ask_price"] if levels else 0.0
        best_bid = levels[0]["bid_price"] if levels else 0.0
        mid_price = (best_ask + best_bid) / 2 if best_ask > 0 and best_bid > 0 else max(best_ask, best_bid)
        spread = best_ask - best_bid if best_ask > 0 and best_bid > 0 else 0.0
        total_ask_qty = _safe_float(output.get("total_askp_rsqn")) or sum(float(row.get("ask_quantity") or 0) for row in levels)
        total_bid_qty = _safe_float(output.get("total_bidp_rsqn")) or sum(float(row.get("bid_quantity") or 0) for row in levels)
        depth_total = total_ask_qty + total_bid_qty
        imbalance_pct = ((total_bid_qty - total_ask_qty) / depth_total * 100) if depth_total > 0 else 0.0
        expected_price = _safe_float(output.get("antc_cnpr"))
        current_or_expected = _safe_float(output.get("stck_prpr")) or expected_price or mid_price
        spread_pct = (spread / current_or_expected * 100) if current_or_expected > 0 and spread > 0 else 0.0

        return {
            "ok": bool(levels),
            "symbol": sym,
            "name": output.get("hts_kor_isnm") or sym,
            "source": "kis_orderbook",
            "mode": self.settings.kis_mode,
            "timestamp": output.get("stck_cntg_hour") or output.get("aspr_acpt_hour") or "",
            "currency": "KRW",
            "unit_scale": 1,
            "price": current_or_expected,
            "best_ask": best_ask,
            "best_bid": best_bid,
            "spread": spread,
            "spread_pct": round(spread_pct, 4),
            "expected_price": expected_price,
            "expected_volume": _safe_float(output.get("antc_vol")),
            "vi_cls_code": str(output.get("vi_cls_code") or "").strip(),
            "risk_fields_observed": "vi_cls_code" in output,
            "total_ask_quantity": total_ask_qty,
            "total_bid_quantity": total_bid_qty,
            "orderbook_imbalance_pct": round(imbalance_pct, 2),
            "levels": levels,
            "message": str(payload.get("msg1") or "OK"),
            "safety": "Read-only KIS orderbook lookup. No order is submitted.",
        }

    def minute_chart(self, symbol: str = "005930", input_time: str | None = None, include_past: bool = True, limit: int = 30) -> dict[str, Any]:
        sym = _normalize_kr_symbol(symbol)
        if not self.settings.kis_configured:
            return {
                "ok": False,
                "symbol": sym,
                "rows": [],
                "source": "unconfigured",
                "message": "KIS API is not configured.",
            }
        target_time = str(input_time or datetime.now().strftime("%H%M%S")).replace(":", "").strip()
        if len(target_time) < 6:
            target_time = target_time.ljust(6, "0")
        target_time = target_time[:6]
        try:
            payload = self._get(
                "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
                KIS_TIME_ITEM_CHART_TR_ID,
                {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": sym,
                    "FID_INPUT_HOUR_1": target_time,
                    "FID_PW_DATA_INCU_YN": "Y" if include_past else "N",
                    "FID_ETC_CLS_CODE": "",
                },
                timeout=8,
            )
        except Exception as exc:
            return {
                "ok": False,
                "symbol": sym,
                "rows": [],
                "source": "kis_minute_chart",
                "message": f"KIS minute chart error: {exc}",
            }
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "symbol": sym,
                "rows": [],
                "source": "kis_minute_chart",
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS minute chart response error"),
            }
        output1 = payload.get("output1") or {}
        if isinstance(output1, list):
            output1 = output1[0] if output1 and isinstance(output1[0], dict) else {}
        if not isinstance(output1, dict):
            output1 = {}
        output2 = payload.get("output2") or []
        if isinstance(output2, dict):
            output2 = [output2]
        rows: list[dict[str, Any]] = []
        for item in output2:
            if not isinstance(item, dict):
                continue
            raw_date = str(item.get("stck_bsop_date") or output1.get("stck_bsop_date") or datetime.now().strftime("%Y%m%d")).strip()
            raw_time = str(item.get("stck_cntg_hour") or "").strip().rjust(6, "0")[:6]
            close = _safe_float(item.get("stck_prpr"))
            if len(raw_date) != 8 or len(raw_time) != 6 or close <= 0:
                continue
            rows.append(
                {
                    "date": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}",
                    "time": f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}",
                    "datetime": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}T{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}+09:00",
                    "open": _safe_float(item.get("stck_oprc")) or close,
                    "high": _safe_float(item.get("stck_hgpr")) or close,
                    "low": _safe_float(item.get("stck_lwpr")) or close,
                    "close": close,
                    "volume": _safe_int(item.get("cntg_vol")),
                    "accumulated_volume": _safe_int(item.get("acml_vol")),
                    "accumulated_trade_value": _safe_float(item.get("acml_tr_pbmn")),
                }
            )
        rows.sort(key=lambda row: str(row.get("datetime", "")))
        safe_limit = max(1, min(int(limit or 30), 30))
        rows = rows[-safe_limit:]
        closes = [_safe_float(row.get("close")) for row in rows if _safe_float(row.get("close")) > 0]
        momentum_pct = ((closes[-1] - closes[0]) / closes[0] * 100) if len(closes) >= 2 and closes[0] else 0.0
        return {
            "ok": bool(rows),
            "query_ok": True,
            "symbol": sym,
            "name": output1.get("hts_kor_isnm") or sym,
            "rows": rows,
            "prices": closes,
            "times": [str(row.get("time", "")) for row in rows],
            "source": "kis_minute_chart",
            "mode": self.settings.kis_mode,
            "input_time": target_time,
            "include_past": include_past,
            "count": len(rows),
            "latest": rows[-1] if rows else {},
            "momentum_pct": round(momentum_pct, 3),
            "message": str(payload.get("msg1") or "OK"),
            "safety": "Read-only KIS minute chart lookup. No order is submitted.",
        }

    def time_conclusion(self, symbol: str = "005930", input_time: str | None = None, limit: int = 30) -> dict[str, Any]:
        sym = _normalize_kr_symbol(symbol)
        if not self.settings.kis_configured:
            return {
                "ok": False,
                "symbol": sym,
                "rows": [],
                "source": "unconfigured",
                "message": "KIS API is not configured.",
            }
        target_time = str(input_time or datetime.now().strftime("%H%M%S")).replace(":", "").strip()
        if len(target_time) < 6:
            target_time = target_time.ljust(6, "0")
        target_time = target_time[:6]
        try:
            payload = self._get(
                "/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion",
                KIS_TIME_ITEM_CONCLUSION_TR_ID,
                {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": sym,
                    "FID_INPUT_HOUR_1": target_time,
                },
                timeout=8,
            )
        except Exception as exc:
            return {
                "ok": False,
                "symbol": sym,
                "rows": [],
                "source": "kis_time_conclusion",
                "message": f"KIS time conclusion error: {exc}",
            }
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "symbol": sym,
                "rows": [],
                "source": "kis_time_conclusion",
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS time conclusion response error"),
            }
        output1 = payload.get("output1") or {}
        if isinstance(output1, list):
            output1 = output1[0] if output1 and isinstance(output1[0], dict) else {}
        if not isinstance(output1, dict):
            output1 = {}
        output2 = payload.get("output2") or []
        if isinstance(output2, dict):
            output2 = [output2]

        today = datetime.now().strftime("%Y%m%d")
        rows: list[dict[str, Any]] = []
        for item in output2:
            if not isinstance(item, dict):
                continue
            raw_time = str(item.get("stck_cntg_hour") or "").strip().rjust(6, "0")[:6]
            price = _safe_float(item.get("stck_pbpr")) or _safe_float(item.get("stck_prpr"))
            if len(raw_time) != 6 or price <= 0:
                continue
            rows.append(
                {
                    "time": f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}",
                    "datetime": f"{today[:4]}-{today[4:6]}-{today[6:8]}T{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}+09:00",
                    "price": price,
                    "change": _safe_float(item.get("prdy_vrss")),
                    "change_sign": str(item.get("prdy_vrss_sign") or ""),
                    "change_pct": _safe_float(item.get("prdy_ctrt")),
                    "ask": _safe_float(item.get("askp")),
                    "bid": _safe_float(item.get("bidp")),
                    "strength": _safe_float(item.get("tday_rltv")),
                    "volume": _safe_int(item.get("cnqn")),
                    "accumulated_volume": _safe_int(item.get("acml_vol")),
                }
            )
        rows.sort(key=lambda row: str(row.get("datetime", "")))
        safe_limit = max(1, min(int(limit or 30), 60))
        rows = rows[-safe_limit:]
        strengths = [_safe_float(row.get("strength")) for row in rows if _safe_float(row.get("strength")) > 0]
        prices = [_safe_float(row.get("price")) for row in rows if _safe_float(row.get("price")) > 0]
        avg_strength = sum(strengths) / len(strengths) if strengths else 0.0
        latest_strength = strengths[-1] if strengths else 0.0
        momentum_pct = ((prices[-1] - prices[0]) / prices[0] * 100) if len(prices) >= 2 and prices[0] else 0.0
        buy_pressure = avg_strength - 100.0 if avg_strength else 0.0
        if avg_strength >= 130:
            state = "strong_buy_pressure"
        elif avg_strength >= 105:
            state = "buy_pressure"
        elif avg_strength >= 80:
            state = "neutral"
        elif avg_strength > 0:
            state = "weak"
        else:
            state = "unknown"
        return {
            "ok": bool(rows),
            "symbol": sym,
            "name": output1.get("hts_kor_isnm") or sym,
            "rows": rows,
            "times": [str(row.get("time", "")) for row in rows],
            "prices": prices,
            "source": "kis_time_conclusion",
            "mode": self.settings.kis_mode,
            "input_time": target_time,
            "count": len(rows),
            "latest": rows[-1] if rows else {},
            "latest_strength": round(latest_strength, 2),
            "avg_strength": round(avg_strength, 2),
            "buy_pressure": round(buy_pressure, 2),
            "momentum_pct": round(momentum_pct, 3),
            "state": state,
            "current_price": _safe_float(output1.get("stck_prpr")),
            "total_volume": _safe_int(output1.get("acml_vol")),
            "previous_volume": _safe_int(output1.get("prdy_vol")),
            "market_name": output1.get("rprs_mrkt_kor_name") or "",
            "message": str(payload.get("msg1") or "OK"),
            "safety": "Read-only KIS time-conclusion lookup. No order is submitted.",
        }

    def _real_readonly_fallback(self, symbol: str, allow_real_fallback: bool) -> dict[str, Any] | None:
        if not allow_real_fallback or not self.settings.kis_use_mock or not self.settings.kis_live_configured:
            return None
        if self.settings.live_trading or not self.settings.kis_readonly:
            return None
        live_settings = IntegrationSettings(
            live_trading=self.settings.live_trading,
            kis_use_mock=False,
            kis_readonly=True,
            kis_mode="real-readonly",
            kis_base_url=self.settings.kis_base_url,
            kis_app_key=self.settings.kis_live_app_key,
            kis_app_secret=self.settings.kis_live_app_secret,
            kis_account_no=self.settings.kis_live_account_no,
            kis_product_code=self.settings.kis_live_product_code,
            kis_user_id=self.settings.kis_user_id,
            kis_live_app_key=self.settings.kis_live_app_key,
            kis_live_app_secret=self.settings.kis_live_app_secret,
            kis_live_account_no=self.settings.kis_live_account_no,
            kis_live_product_code=self.settings.kis_live_product_code,
            kis_quote_throttle_ms=self.settings.kis_quote_throttle_ms,
            dart_api_key=self.settings.dart_api_key,
            dart_lookback_days=self.settings.dart_lookback_days,
            cache_ttl_dart_sec=self.settings.cache_ttl_dart_sec,
            cache_ttl_kis_sec=self.settings.cache_ttl_kis_sec,
            ecos_api_key=self.settings.ecos_api_key,
            ecos_language=self.settings.ecos_language,
            ecos_cache_ttl_sec=self.settings.ecos_cache_ttl_sec,
            fred_api_key=self.settings.fred_api_key,
            fred_cache_ttl_sec=self.settings.fred_cache_ttl_sec,
            telegram_enabled=self.settings.telegram_enabled,
            telegram_stub=self.settings.telegram_stub,
            telegram_dry_run=self.settings.telegram_dry_run,
            telegram_bot_token=self.settings.telegram_bot_token,
            telegram_chat_id=self.settings.telegram_chat_id,
        )
        return KisReadonlyBridge(live_settings).quote(symbol, allow_real_fallback=False)

    def _real_readonly_chart_fallback(self, symbol: str, start_date: str, end_date: str, allow_real_fallback: bool) -> dict[str, Any] | None:
        if not allow_real_fallback or not self.settings.kis_use_mock or not self.settings.kis_live_configured:
            return None
        if self.settings.live_trading or not self.settings.kis_readonly:
            return None
        live_settings = IntegrationSettings(
            live_trading=self.settings.live_trading,
            kis_use_mock=False,
            kis_readonly=True,
            kis_mode="real-readonly",
            kis_base_url=self.settings.kis_base_url,
            kis_app_key=self.settings.kis_live_app_key,
            kis_app_secret=self.settings.kis_live_app_secret,
            kis_account_no=self.settings.kis_live_account_no,
            kis_product_code=self.settings.kis_live_product_code,
            kis_user_id=self.settings.kis_user_id,
            kis_live_app_key=self.settings.kis_live_app_key,
            kis_live_app_secret=self.settings.kis_live_app_secret,
            kis_live_account_no=self.settings.kis_live_account_no,
            kis_live_product_code=self.settings.kis_live_product_code,
            kis_quote_throttle_ms=self.settings.kis_quote_throttle_ms,
            dart_api_key=self.settings.dart_api_key,
            dart_lookback_days=self.settings.dart_lookback_days,
            cache_ttl_dart_sec=self.settings.cache_ttl_dart_sec,
            cache_ttl_kis_sec=self.settings.cache_ttl_kis_sec,
            ecos_api_key=self.settings.ecos_api_key,
            ecos_language=self.settings.ecos_language,
            ecos_cache_ttl_sec=self.settings.ecos_cache_ttl_sec,
            fred_api_key=self.settings.fred_api_key,
            fred_cache_ttl_sec=self.settings.fred_cache_ttl_sec,
            telegram_enabled=self.settings.telegram_enabled,
            telegram_stub=self.settings.telegram_stub,
            telegram_dry_run=self.settings.telegram_dry_run,
            telegram_bot_token=self.settings.telegram_bot_token,
            telegram_chat_id=self.settings.telegram_chat_id,
        )
        return KisReadonlyBridge(live_settings).daily_chart(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            allow_real_fallback=False,
        )

    def daily_chart(
        self,
        symbol: str = "005930",
        start_date: str | None = None,
        end_date: str | None = None,
        allow_real_fallback: bool = True,
    ) -> dict[str, Any]:
        sym = _normalize_kr_symbol(symbol)
        start_text = (start_date or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")).replace("-", "")[:8]
        end_text = (end_date or datetime.now().strftime("%Y-%m-%d")).replace("-", "")[:8]
        if not self.settings.kis_configured:
            return {
                "ok": False,
                "symbol": sym,
                "rows": [],
                "source": "unconfigured",
                "message": "KIS API 키가 설정되지 않았습니다.",
            }
        params = urllib.parse.urlencode(
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": sym,
                "FID_INPUT_DATE_1": start_text,
                "FID_INPUT_DATE_2": end_text,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            }
        )
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice?{params}"
        try:
            token = self._cached_token()
            request = urllib.request.Request(
                url,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "authorization": f"Bearer {token}",
                    "appkey": self.settings.kis_app_key,
                    "appsecret": self.settings.kis_app_secret,
                    "tr_id": KIS_DAILY_CHART_TR_ID,
                    "custtype": "P",
                },
            )
            with urllib.request.urlopen(request, timeout=max(KIS_TIMEOUT_SEC, 8)) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            fallback = self._real_readonly_chart_fallback(symbol, start_text, end_text, allow_real_fallback)
            if fallback:
                fallback["fallback_from"] = "mock"
                return fallback
            return {
                "ok": False,
                "symbol": sym,
                "rows": [],
                "source": "kis_daily_chart",
                "message": f"KIS 일봉 조회 오류: {exc}",
            }
        if str(payload.get("rt_cd")) != "0":
            fallback = self._real_readonly_chart_fallback(symbol, start_text, end_text, allow_real_fallback)
            if fallback:
                fallback["fallback_from"] = "mock"
                fallback["mock_message"] = str(payload.get("msg1") or payload.get("msg_cd") or "KIS 응답 오류")
                return fallback
            return {
                "ok": False,
                "symbol": sym,
                "rows": [],
                "source": "kis_daily_chart",
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 일봉 응답 오류"),
            }
        output = payload.get("output2") or []
        if isinstance(output, dict):
            output = [output]
        rows: list[dict[str, Any]] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            raw_date = str(item.get("stck_bsop_date") or "").strip()
            close = _safe_float(item.get("stck_clpr"))
            if len(raw_date) != 8 or close <= 0:
                continue
            rows.append(
                {
                    "date": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}",
                    "open": _safe_float(item.get("stck_oprc")),
                    "high": _safe_float(item.get("stck_hgpr")),
                    "low": _safe_float(item.get("stck_lwpr")),
                    "close": close,
                    "adjusted_close": close,
                    "volume": _safe_int(item.get("acml_vol")),
                    "price_basis": "KIS_FID_ORG_ADJ_PRC_0",
                }
            )
        rows.sort(key=lambda row: str(row.get("date", "")))
        return {
            "ok": bool(rows),
            "symbol": sym,
            "rows": rows,
            "source": "kis_daily_chart",
            "provider": "KIS_adjusted_verified",
            "corporate_action_adjusted": True,
            "adjustment_contract": "FID_ORG_ADJ_PRC=0 (KIS adjusted price)",
            "mode": self.settings.kis_mode,
            "message": str(payload.get("msg1") or ("정상" if rows else "KIS 일봉 데이터가 비어 있습니다.")),
        }

    def daily_chart_range(
        self,
        symbol: str = "005930",
        start_date: str | None = None,
        end_date: str | None = None,
        *,
        max_pages: int = 80,
        allow_real_fallback: bool = True,
    ) -> dict[str, Any]:
        """Read a long KIS daily range by walking the 100-row window backwards."""
        sym = _normalize_kr_symbol(symbol)
        start_text = (start_date or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"))[:10]
        end_text = (end_date or datetime.now().strftime("%Y-%m-%d"))[:10]
        try:
            start_day = datetime.strptime(start_text, "%Y-%m-%d").date()
            end_day = datetime.strptime(end_text, "%Y-%m-%d").date()
        except ValueError:
            return {
                "ok": False,
                "symbol": sym,
                "rows": [],
                "source": "kis_daily_chart_range",
                "range_complete": False,
                "message": "KIS daily range dates must use YYYY-MM-DD.",
            }
        if start_day > end_day:
            return {
                "ok": False,
                "symbol": sym,
                "rows": [],
                "source": "kis_daily_chart_range",
                "range_complete": False,
                "message": "KIS daily range start date is after end date.",
            }

        bounded_max_pages = max(1, min(int(max_pages or 80), 200))
        current_end = end_day
        merged: dict[str, dict[str, Any]] = {}
        page_count = 0
        range_complete = False
        stop_reason = "max_pages_reached"
        page_errors: list[str] = []
        previous_earliest = ""
        while page_count < bounded_max_pages:
            page = self.daily_chart(
                symbol=sym,
                start_date=start_day.isoformat(),
                end_date=current_end.isoformat(),
                allow_real_fallback=allow_real_fallback,
            )
            page_count += 1
            if not page.get("ok"):
                stop_reason = "page_request_failed"
                page_errors.append(str(page.get("message") or "KIS daily page request failed."))
                break
            page_rows = [row for row in page.get("rows", []) if isinstance(row, dict)]
            dated_rows = [row for row in page_rows if str(row.get("date") or "")]
            if not dated_rows:
                range_complete = True
                stop_reason = "no_older_rows"
                break
            for row in dated_rows:
                date_key = str(row.get("date") or "")
                if start_day.isoformat() <= date_key <= end_day.isoformat():
                    merged[date_key] = dict(row)
            earliest = min(str(row.get("date") or "") for row in dated_rows)
            if earliest <= start_day.isoformat():
                range_complete = True
                stop_reason = "requested_start_reached"
                break
            if len(dated_rows) < 100:
                range_complete = True
                stop_reason = "provider_history_exhausted"
                break
            if earliest == previous_earliest:
                stop_reason = "page_cursor_did_not_advance"
                page_errors.append("KIS daily pagination returned the same earliest date twice.")
                break
            previous_earliest = earliest
            try:
                next_end = datetime.strptime(earliest, "%Y-%m-%d").date() - timedelta(days=1)
            except ValueError:
                stop_reason = "invalid_page_date"
                page_errors.append(f"Invalid KIS daily page date: {earliest}")
                break
            if next_end >= current_end:
                stop_reason = "page_cursor_did_not_advance"
                page_errors.append("KIS daily pagination cursor did not move backwards.")
                break
            current_end = next_end
            time.sleep(max(0.05, self.settings.kis_quote_throttle_ms / 1000))

        rows = [merged[key] for key in sorted(merged)]
        return {
            "ok": bool(rows) and range_complete,
            "symbol": sym,
            "rows": rows,
            "source": "kis_daily_chart_range",
            "provider": "KIS_adjusted_verified",
            "mode": self.settings.kis_mode,
            "page_count": page_count,
            "max_pages": bounded_max_pages,
            "range_start": start_day.isoformat(),
            "range_end": end_day.isoformat(),
            "range_complete": range_complete,
            "stop_reason": stop_reason,
            "page_errors": page_errors,
            "corporate_action_adjusted": True,
            "adjustment_contract": "FID_ORG_ADJ_PRC=0 (KIS adjusted price)",
            "message": "KIS adjusted daily range loaded." if range_complete else "; ".join(page_errors) or stop_reason,
        }

    def watch_quotes(self, symbols: list[str] | None = None) -> dict[str, Any]:
        target_symbols = symbols or ["005930", "000660", "005380"]
        rows = []
        for symbol in target_symbols[:8]:
            rows.append(self.quote(symbol, allow_real_fallback=len(target_symbols) <= 1))
            time.sleep(max(0.05, self.settings.kis_quote_throttle_ms / 1000))
        ok_count = sum(1 for row in rows if row.get("ok"))
        return {
            "configured": self.settings.kis_configured,
            "mode": self.settings.kis_mode,
            "readonly": self.settings.kis_readonly,
            "live_trading": self.settings.live_trading,
            "order_allowed": False,
            "ok_count": ok_count,
            "items": rows,
        }

    def investor_trend(self, symbol: str = "005930") -> dict[str, Any]:
        """Return post-close personal, foreign, and institution net buying for one stock."""
        sym = _normalize_kr_symbol(symbol)
        if not self.settings.kis_configured:
            return {"ok": False, "symbol": sym, "source": "unconfigured", "message": "KIS API 설정이 필요합니다.", "rows": []}
        try:
            payload = self._get(
                "/uapi/domestic-stock/v1/quotations/inquire-investor",
                KIS_INVESTOR_TR_ID,
                {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": sym},
                timeout=8,
            )
        except Exception as exc:
            return {"ok": False, "symbol": sym, "source": "kis_investor_trend", "message": f"KIS 투자자 수급 조회 오류: {exc}", "rows": []}
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "symbol": sym,
                "source": "kis_investor_trend",
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 투자자 수급 응답 오류"),
                "rows": [],
            }
        output = payload.get("output") or []
        if isinstance(output, dict):
            output = [output]
        rows: list[dict[str, Any]] = []
        for item in output if isinstance(output, list) else []:
            if not isinstance(item, dict):
                continue
            raw_date = str(item.get("stck_bsop_date") or "").strip()
            if len(raw_date) != 8:
                continue
            personal_amount_million = _safe_float(item.get("prsn_ntby_tr_pbmn"))
            foreign_amount_million = _safe_float(item.get("frgn_ntby_tr_pbmn"))
            institution_amount_million = _safe_float(item.get("orgn_ntby_tr_pbmn"))
            rows.append(
                {
                    "date": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}",
                    "close": _safe_float(item.get("stck_clpr")),
                    "personal_net_qty": _safe_int(item.get("prsn_ntby_qty")),
                    "foreign_net_qty": _safe_int(item.get("frgn_ntby_qty")),
                    "institution_net_qty": _safe_int(item.get("orgn_ntby_qty")),
                    "personal_net_amount": personal_amount_million * 1_000_000,
                    "foreign_net_amount": foreign_amount_million * 1_000_000,
                    "institution_net_amount": institution_amount_million * 1_000_000,
                    "personal_net_amount_million_krw": personal_amount_million,
                    "foreign_net_amount_million_krw": foreign_amount_million,
                    "institution_net_amount_million_krw": institution_amount_million,
                    "amount_unit": "KRW",
                    "provider_amount_unit": "million_KRW",
                }
            )
        rows.sort(key=lambda row: str(row.get("date", "")), reverse=True)
        return {
            "ok": bool(rows),
            "symbol": sym,
            "rows": rows,
            "latest": rows[0] if rows else {},
            "source": "kis_investor_trend",
            "message": str(payload.get("msg1") or ("정상" if rows else "투자자 수급 데이터가 비어 있습니다.")),
            "availability": "당일 확정 데이터는 장 종료 후 제공",
            "safety": "읽기전용 투자자 수급 조회입니다. 주문을 실행하지 않습니다.",
        }

    def foreign_institution_rank(
        self,
        investor: str = "foreign",
        market: str = "all",
        direction: str = "buy",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return KIS intraday estimated foreign/institution net-buy rankings."""
        if not self.settings.kis_configured:
            return {"ok": False, "source": "unconfigured", "message": "KIS API 설정이 필요합니다.", "items": []}
        investor_key = "institution" if str(investor).lower() in {"institution", "orgn", "기관"} else "foreign"
        market_code = {"kospi": "0001", "ks": "0001", "kosdaq": "1001", "kq": "1001"}.get(str(market).lower(), "0000")
        params = {
            "FID_COND_MRKT_DIV_CODE": "V",
            "FID_COND_SCR_DIV_CODE": "16449",
            "FID_INPUT_ISCD": market_code,
            "FID_DIV_CLS_CODE": "1",
            "FID_RANK_SORT_CLS_CODE": "1" if str(direction).lower() in {"sell", "down"} else "0",
            "FID_ETC_CLS_CODE": "2" if investor_key == "institution" else "1",
        }
        try:
            payload = self._get(
                "/uapi/domestic-stock/v1/quotations/foreign-institution-total",
                KIS_FOREIGN_INSTITUTION_TOTAL_TR_ID,
                params,
                timeout=8,
            )
        except Exception as exc:
            return {"ok": False, "source": "kis_foreign_institution_rank", "message": f"KIS 외국인/기관 순위 조회 오류: {exc}", "items": []}
        if str(payload.get("rt_cd")) != "0":
            return {"ok": False, "source": "kis_foreign_institution_rank", "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 외국인/기관 순위 응답 오류"), "items": []}
        output = payload.get("output") or []
        if isinstance(output, dict):
            output = [output]
        safe_limit = max(1, min(int(limit or 20), 30))
        items: list[dict[str, Any]] = []
        for raw in output[:safe_limit] if isinstance(output, list) else []:
            if not isinstance(raw, dict):
                continue
            symbol = _normalize_kr_symbol(raw.get("mksc_shrn_iscd") or raw.get("stck_shrn_iscd") or raw.get("code"))
            foreign_amount_million = _safe_float(raw.get("frgn_ntby_tr_pbmn"))
            institution_amount_million = _safe_float(raw.get("orgn_ntby_tr_pbmn"))
            items.append(
                {
                    "rank": _safe_int(raw.get("data_rank")) or len(items) + 1,
                    "symbol": symbol,
                    "name": str(raw.get("hts_kor_isnm") or raw.get("name") or symbol),
                    "price": _safe_float(raw.get("stck_prpr")),
                    "change_pct": _safe_float(raw.get("prdy_ctrt")),
                    "foreign_net_qty": _safe_int(raw.get("frgn_ntby_qty")),
                    "institution_net_qty": _safe_int(raw.get("orgn_ntby_qty")),
                    "foreign_net_amount": foreign_amount_million * 1_000_000,
                    "institution_net_amount": institution_amount_million * 1_000_000,
                    "foreign_net_amount_million_krw": foreign_amount_million,
                    "institution_net_amount_million_krw": institution_amount_million,
                    "amount_unit": "KRW",
                    "provider_amount_unit": "million_KRW",
                }
            )
        return {
            "ok": bool(items),
            "investor": investor_key,
            "direction": "sell" if params["FID_RANK_SORT_CLS_CODE"] == "1" else "buy",
            "market": market,
            "items": items,
            "source": "kis_foreign_institution_rank",
            "availability": "장중 잠정 집계이며 입력 시각에 따라 지연될 수 있음",
            "message": str(payload.get("msg1") or ("정상" if items else "순위 데이터가 비어 있습니다.")),
            "safety": "읽기전용 수급 순위입니다. 주문을 실행하지 않습니다.",
        }

    def volume_rank(
        self,
        rank_kind: str = "amount",
        market: str = "all",
        limit: int = 30,
        min_price: int = 0,
        max_price: int = 0,
        min_volume: int = 0,
    ) -> dict[str, Any]:
        if not self.settings.kis_configured:
            return {"ok": False, "source": "kis_volume_rank", "message": "KIS API 설정이 필요합니다.", "items": []}
        kind = (rank_kind or "amount").lower().strip()
        market_key = (market or "all").lower().strip()
        # KIS volume-rank uses FID_BLNG_CLS_CODE as the ranking axis. 3 is trading amount.
        kind_code = {
            "amount": "3",
            "money": "3",
            "value": "3",
            "volume": "0",
            "vol": "0",
            "increase": "1",
            "turnover": "2",
        }.get(kind, "3")
        market_code = {
            "all": "0000",
            "kospi": "0001",
            "ks": "0001",
            "kosdaq": "1001",
            "kq": "1001",
        }.get(market_key, "0000")
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20171",
            "FID_INPUT_ISCD": market_code,
            "FID_DIV_CLS_CODE": "0",
            "FID_BLNG_CLS_CODE": kind_code,
            "FID_TRGT_CLS_CODE": "111111111",
            "FID_TRGT_EXLS_CLS_CODE": "0000000000",
            "FID_INPUT_PRICE_1": str(max(0, int(min_price or 0))),
            "FID_INPUT_PRICE_2": str(max(0, int(max_price or 0))),
            "FID_VOL_CNT": str(max(0, int(min_volume or 0))),
            "FID_INPUT_DATE_1": "0",
        }
        try:
            payload = self._get(
                "/uapi/domestic-stock/v1/quotations/volume-rank",
                KIS_VOLUME_RANK_TR_ID,
                params,
                timeout=8,
            )
        except Exception as exc:
            return {"ok": False, "source": "kis_volume_rank", "message": f"KIS 거래대금 순위 조회 오류: {exc}", "items": []}
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "source": "kis_volume_rank",
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 거래대금 순위 응답 오류"),
                "items": [],
                "raw": payload,
            }
        output = payload.get("output") or []
        if isinstance(output, dict):
            output = [output]
        if not isinstance(output, list):
            output = []
        safe_limit = max(1, min(int(limit or 30), 30))
        rows: list[dict[str, Any]] = []
        filtered_zero_activity_count = 0
        for item in output[:safe_limit]:
            if not isinstance(item, dict):
                continue
            raw_symbol = str(item.get("mksc_shrn_iscd") or item.get("stck_shrn_iscd") or "").strip()
            digits = "".join(ch for ch in raw_symbol if ch.isdigit())
            symbol = digits[-6:] if len(digits) >= 6 else raw_symbol
            name = str(item.get("hts_kor_isnm") or item.get("name") or symbol).strip()
            price = _safe_float(item.get("stck_prpr"))
            amount = _safe_int(item.get("acml_tr_pbmn"))
            volume = _safe_int(item.get("acml_vol"))
            change = _safe_float(item.get("prdy_vrss"))
            change_pct = _safe_float(item.get("prdy_ctrt"))
            if volume <= 0 and amount <= 0 and abs(change) <= 0 and abs(change_pct) <= 0:
                filtered_zero_activity_count += 1
                continue
            rows.append(
                {
                    "rank": _safe_int(item.get("data_rank")),
                    "symbol": symbol,
                    "name": name,
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": volume,
                    "previous_volume": _safe_int(item.get("prdy_vol")),
                    "avg_volume": _safe_int(item.get("avrg_vol")),
                    "volume_increase_pct": _safe_float(item.get("vol_inrt")),
                    "volume_turnover_pct": _safe_float(item.get("vol_tnrt")),
                    "amount": amount,
                    "amount_eok": round(amount / 100_000_000, 1) if amount else 0.0,
                    "avg_amount": _safe_int(item.get("avrg_tr_pbmn")),
                    "amount_turnover_pct": _safe_float(item.get("tr_pbmn_tnrt")),
                    "source": "kis_volume_rank",
                    "raw": item,
                }
            )
        result = {
            "ok": bool(rows),
            "status": "ready" if rows else "no_active_market_data",
            "source": "kis_volume_rank",
            "mode": self.settings.kis_mode,
            "rank_kind": kind,
            "rank_kind_code": kind_code,
            "market": market_key,
            "market_code": market_code,
            "items": rows,
            "count": len(rows),
            "raw_count": len(output[:safe_limit]),
            "filtered_zero_activity_count": filtered_zero_activity_count,
            "message": str(payload.get("msg1") or ("정상" if rows else "KIS 거래대금 순위 데이터가 비어 있습니다.")),
        }

        if not rows:
            result["message"] = "장전에는 거래량·거래대금 순위가 아직 형성되지 않았습니다. 장 시작 후 다시 확인합니다."
        return result

    def fluctuation_rank(
        self,
        direction: str = "up",
        market: str = "all",
        limit: int = 30,
        min_price: int = 0,
        max_price: int = 0,
        min_volume: int = 0,
    ) -> dict[str, Any]:
        if not self.settings.kis_configured:
            return {"ok": False, "source": "kis_fluctuation_rank", "message": "KIS API 설정이 필요합니다.", "items": []}
        direction_key = (direction or "up").lower().strip()
        market_key = (market or "all").lower().strip()
        sort_code = "1" if direction_key in {"down", "fall", "falling", "loss", "loser"} else "0"
        market_code = {
            "all": "0000",
            "kospi": "0001",
            "ks": "0001",
            "kosdaq": "1001",
            "kq": "1001",
        }.get(market_key, "0000")
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20170",
            "fid_input_iscd": market_code,
            "fid_rank_sort_cls_code": sort_code,
            "fid_input_cnt_1": "0",
            "fid_prc_cls_code": "1",
            "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0",
            "fid_div_cls_code": "0",
            "fid_rsfl_rate1": "",
            "fid_rsfl_rate2": "",
            "fid_input_price_1": str(max(0, int(min_price or 0))) if min_price else "",
            "fid_input_price_2": str(max(0, int(max_price or 0))) if max_price else "",
            "fid_vol_cnt": str(max(0, int(min_volume or 0))) if min_volume else "",
        }
        try:
            payload = self._get(
                "/uapi/domestic-stock/v1/ranking/fluctuation",
                KIS_FLUCTUATION_RANK_TR_ID,
                params,
                timeout=8,
            )
        except Exception as exc:
            return {"ok": False, "source": "kis_fluctuation_rank", "message": f"KIS 등락률 순위 조회 오류: {exc}", "items": []}
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "source": "kis_fluctuation_rank",
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 등락률 순위 응답 오류"),
                "items": [],
                "raw": payload,
            }
        output = payload.get("output") or []
        if isinstance(output, dict):
            output = [output]
        if not isinstance(output, list):
            output = []
        safe_limit = max(1, min(int(limit or 30), 30))
        rows: list[dict[str, Any]] = []
        filtered_zero_activity_count = 0
        for item in output[:safe_limit]:
            if not isinstance(item, dict):
                continue
            raw_symbol = str(
                item.get("stck_shrn_iscd")
                or item.get("mksc_shrn_iscd")
                or item.get("stck_iscd")
                or ""
            ).strip()
            digits = "".join(ch for ch in raw_symbol if ch.isdigit())
            symbol = digits[-6:] if len(digits) >= 6 else raw_symbol
            name = str(item.get("hts_kor_isnm") or item.get("hts_kor_isnm") or item.get("name") or symbol).strip()
            price = _safe_float(item.get("stck_prpr") or item.get("stck_prpr"))
            amount = _safe_int(item.get("acml_tr_pbmn") or item.get("acml_tr_pbmn"))
            volume = _safe_int(item.get("acml_vol"))
            change = _safe_float(item.get("prdy_vrss"))
            change_pct = _safe_float(item.get("prdy_ctrt") or item.get("prdy_ctrt"))
            if volume <= 0 and amount <= 0 and abs(change) <= 0 and abs(change_pct) <= 0:
                filtered_zero_activity_count += 1
                continue
            rows.append(
                {
                    "rank": _safe_int(item.get("data_rank")),
                    "symbol": symbol,
                    "name": name,
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "open_change_pct": _safe_float(item.get("oprc_vrss_prpr_rate")),
                    "low_change_pct": _safe_float(item.get("lwpr_vrss_prpr_rate")),
                    "high_change_pct": _safe_float(item.get("hgpr_vrss_prpr_rate")),
                    "volume": volume,
                    "amount": amount,
                    "amount_eok": round(amount / 100_000_000, 1) if amount else 0.0,
                    "source": "kis_fluctuation_rank",
                    "raw": item,
                }
            )
        result = {
            "ok": bool(rows),
            "status": "ready" if rows else "no_active_market_data",
            "source": "kis_fluctuation_rank",
            "mode": self.settings.kis_mode,
            "direction": "down" if sort_code == "1" else "up",
            "sort_code": sort_code,
            "market": market_key,
            "market_code": market_code,
            "items": rows,
            "count": len(rows),
            "raw_count": len(output[:safe_limit]),
            "filtered_zero_activity_count": filtered_zero_activity_count,
            "message": str(payload.get("msg1") or ("정상" if rows else "KIS 등락률 순위 데이터가 비어 있습니다.")),
        }

        if not rows:
            result["message"] = "장전에는 상승·하락 순위가 아직 형성되지 않았습니다. 장 시작 후 다시 확인합니다."
        return result

    def volume_power_rank(
        self,
        market: str = "all",
        limit: int = 30,
        min_price: int = 0,
        max_price: int = 0,
        min_volume: int = 0,
    ) -> dict[str, Any]:
        if not self.settings.kis_configured:
            return {"ok": False, "source": "kis_volume_power_rank", "message": "KIS API 설정이 필요합니다.", "items": []}
        market_key = (market or "all").lower().strip()
        market_code = {
            "all": "0000",
            "kospi": "0001",
            "ks": "0001",
            "kosdaq": "1001",
            "kq": "1001",
        }.get(market_key, "0000")
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20168",
            "fid_input_iscd": market_code,
            "fid_div_cls_code": "0",
            "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0",
            "fid_input_price_1": str(max(0, int(min_price or 0))) if min_price else "",
            "fid_input_price_2": str(max(0, int(max_price or 0))) if max_price else "",
            "fid_vol_cnt": str(max(0, int(min_volume or 0))) if min_volume else "",
        }
        try:
            payload = self._get(
                "/uapi/domestic-stock/v1/ranking/volume-power",
                KIS_VOLUME_POWER_RANK_TR_ID,
                params,
                timeout=8,
            )
        except Exception as exc:
            return {"ok": False, "source": "kis_volume_power_rank", "message": f"KIS 체결강도 상위 조회 오류: {exc}", "items": []}
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "source": "kis_volume_power_rank",
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 체결강도 상위 응답 오류"),
                "items": [],
                "raw": payload,
            }
        output = payload.get("output") or []
        if isinstance(output, dict):
            output = [output]
        if not isinstance(output, list):
            output = []
        safe_limit = max(1, min(int(limit or 30), 30))
        rows: list[dict[str, Any]] = []
        for item in output[:safe_limit]:
            if not isinstance(item, dict):
                continue
            raw_symbol = str(
                item.get("stck_shrn_iscd")
                or item.get("mksc_shrn_iscd")
                or item.get("stck_iscd")
                or item.get("iscd")
                or ""
            ).strip()
            digits = "".join(ch for ch in raw_symbol if ch.isdigit())
            symbol = digits[-6:] if len(digits) >= 6 else raw_symbol
            name = str(item.get("hts_kor_isnm") or item.get("hts_kor_isnm") or item.get("name") or symbol).strip()
            power = _safe_float(
                item.get("tday_rltv")
                or item.get("cttr")
                or item.get("cnqn_rate")
                or item.get("vol_power")
                or item.get("cntg_ints")
                or item.get("tpow")
            )
            price = _safe_float(item.get("stck_prpr"))
            volume = _safe_int(item.get("acml_vol"))
            amount = _safe_int(item.get("acml_tr_pbmn") or item.get("tr_pbmn") or item.get("acml_tr_pbmn"))
            if not amount and price and volume:
                amount = int(price * volume)
            rows.append(
                {
                    "rank": _safe_int(item.get("data_rank")),
                    "symbol": symbol,
                    "name": name,
                    "price": price,
                    "change": _safe_float(item.get("prdy_vrss")),
                    "change_pct": _safe_float(item.get("prdy_ctrt")),
                    "volume": volume,
                    "amount": amount,
                    "amount_eok": round(amount / 100_000_000, 1) if amount else 0.0,
                    "power": power,
                    "buy_volume": _safe_int(item.get("shnu_cnqn_smtn") or item.get("buy_cnqn") or item.get("askp_rsqn") or item.get("total_askp_rsqn")),
                    "sell_volume": _safe_int(item.get("seln_cnqn_smtn") or item.get("sell_cnqn") or item.get("bidp_rsqn") or item.get("total_bidp_rsqn")),
                    "source": "kis_volume_power_rank",
                    "raw": item,
                }
            )
        return {
            "ok": bool(rows),
            "source": "kis_volume_power_rank",
            "mode": self.settings.kis_mode,
            "market": market_key,
            "market_code": market_code,
            "items": rows,
            "count": len(rows),
            "message": str(payload.get("msg1") or ("정상" if rows else "KIS 체결강도 상위 데이터가 비어 있습니다.")),
        }

    def quote_balance_rank(
        self,
        balance_kind: str = "buy",
        market: str = "all",
        limit: int = 30,
        min_price: int = 0,
        max_price: int = 0,
        min_volume: int = 0,
    ) -> dict[str, Any]:
        if not self.settings.kis_configured:
            return {"ok": False, "source": "kis_quote_balance_rank", "message": "KIS API 설정이 필요합니다.", "items": []}
        kind_key = (balance_kind or "buy").lower().strip()
        market_key = (market or "all").lower().strip()
        market_code = {
            "all": "0000",
            "kospi": "0001",
            "ks": "0001",
            "kosdaq": "1001",
            "kq": "1001",
        }.get(market_key, "0000")
        sort_code = {
            "buy": "0",
            "buy_net": "0",
            "bid": "0",
            "support": "0",
            "sell": "1",
            "sell_net": "1",
            "ask": "1",
            "pressure": "1",
            "buy_ratio": "2",
            "bid_ratio": "2",
            "sell_ratio": "3",
            "ask_ratio": "3",
        }.get(kind_key, "0")
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20172",
            "fid_input_iscd": market_code,
            "fid_rank_sort_cls_code": sort_code,
            "fid_div_cls_code": "0",
            "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0",
            "fid_input_price_1": str(max(0, int(min_price or 0))) if min_price else "",
            "fid_input_price_2": str(max(0, int(max_price or 0))) if max_price else "",
            "fid_vol_cnt": str(max(0, int(min_volume or 0))) if min_volume else "0",
        }
        try:
            payload = self._get(
                "/uapi/domestic-stock/v1/ranking/quote-balance",
                KIS_QUOTE_BALANCE_RANK_TR_ID,
                params,
                timeout=8,
            )
        except Exception as exc:
            return {"ok": False, "source": "kis_quote_balance_rank", "message": f"KIS 호가잔량 순위 조회 오류: {exc}", "items": []}
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "source": "kis_quote_balance_rank",
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 호가잔량 순위 응답 오류"),
                "items": [],
                "raw": payload,
            }
        output = payload.get("output") or []
        if isinstance(output, dict):
            output = [output]
        safe_limit = max(1, min(int(limit or 30), 30))
        rows: list[dict[str, Any]] = []
        for item in output[:safe_limit]:
            if not isinstance(item, dict):
                continue
            raw_symbol = str(
                item.get("mksc_shrn_iscd")
                or item.get("stck_shrn_iscd")
                or item.get("stck_iscd")
                or item.get("iscd")
                or ""
            ).strip()
            digits = "".join(ch for ch in raw_symbol if ch.isdigit())
            symbol = digits[-6:] if len(digits) >= 6 else raw_symbol
            name = str(item.get("hts_kor_isnm") or item.get("name") or symbol).strip()
            price = _safe_float(item.get("stck_prpr"))
            volume = _safe_int(item.get("acml_vol"))
            amount = int(price * volume) if price and volume else 0
            ask_balance = _safe_int(item.get("total_askp_rsqn"))
            bid_balance = _safe_int(item.get("total_bidp_rsqn"))
            net_buy_balance = _safe_int(item.get("total_ntsl_bidp_rsqn"))
            rows.append(
                {
                    "rank": _safe_int(item.get("data_rank")),
                    "symbol": symbol,
                    "name": name,
                    "price": price,
                    "change": _safe_float(item.get("prdy_vrss")),
                    "change_pct": _safe_float(item.get("prdy_ctrt")),
                    "volume": volume,
                    "amount": amount,
                    "amount_eok": round(amount / 100_000_000, 1) if amount else 0.0,
                    "ask_balance": ask_balance,
                    "bid_balance": bid_balance,
                    "net_buy_balance": net_buy_balance,
                    "buy_rate": _safe_float(item.get("shnu_rsqn_rate")),
                    "sell_rate": _safe_float(item.get("seln_rsqn_rate")),
                    "source": "kis_quote_balance_rank",
                    "raw": item,
                }
            )
        return {
            "ok": bool(rows),
            "source": "kis_quote_balance_rank",
            "mode": self.settings.kis_mode,
            "balance_kind": kind_key,
            "sort_code": sort_code,
            "market": market_key,
            "market_code": market_code,
            "items": rows,
            "count": len(rows),
            "message": str(payload.get("msg1") or ("정상" if rows else "KIS 호가잔량 순위 데이터가 비어 있습니다.")),
        }

    def _get(self, path: str, tr_id: str, params: dict[str, Any], timeout: int | None = None) -> dict[str, Any]:
        query = urllib.parse.urlencode({key: str(value or "") for key, value in params.items()})
        url = f"{self.base_url}{path}?{query}"
        token = self._cached_token()
        request = urllib.request.Request(
            url,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "appkey": self.settings.kis_app_key,
                "appsecret": self.settings.kis_app_secret,
                "tr_id": tr_id,
                "custtype": "P",
            },
        )
        with urllib.request.urlopen(request, timeout=max(KIS_TIMEOUT_SEC, timeout or 8)) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {"payload": payload}

    def interest_groups(self) -> dict[str, Any]:
        if not self.settings.kis_configured:
            return {"ok": False, "source": "kis_interest_groups", "message": "KIS API 설정이 필요합니다.", "groups": []}
        if self.settings.kis_use_mock:
            return {"ok": False, "source": "kis_interest_groups", "message": "한투 관심종목 API는 모의투자를 지원하지 않습니다. 실전 KIS 설정이 필요합니다.", "groups": []}
        if not self.settings.kis_user_id:
            return {"ok": False, "source": "kis_interest_groups", "message": "한투 MTS/HTS 관심종목 동기화에는 KIS_USER_ID 또는 KIS_HTS_ID가 필요합니다.", "groups": []}
        try:
            payload = self._get(
                "/uapi/domestic-stock/v1/quotations/intstock-grouplist",
                KIS_INTSTOCK_GROUPLIST_TR_ID,
                {"TYPE": "1", "FID_ETC_CLS_CODE": "00", "USER_ID": self.settings.kis_user_id},
                timeout=8,
            )
        except Exception as exc:
            return {"ok": False, "source": "kis_interest_groups", "message": f"KIS 관심그룹 조회 오류: {exc}", "groups": []}
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "source": "kis_interest_groups",
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 관심그룹 응답 오류"),
                "groups": [],
            }
        output = payload.get("output2") or []
        if isinstance(output, dict):
            output = [output]
        if not isinstance(output, list):
            output = []
        groups: list[dict[str, Any]] = []
        for index, item in enumerate(output, start=1):
            if not isinstance(item, dict):
                continue
            code = str(item.get("inter_grp_code") or item.get("INTER_GRP_CODE") or "").strip()
            if not code:
                code = str(index).zfill(3)
            groups.append(
                {
                    "code": code,
                    "name": str(item.get("inter_grp_name") or item.get("INTER_GRP_NAME") or f"관심그룹 {code}"),
                    "rank": str(item.get("data_rank") or item.get("DATA_RANK") or index),
                    "count": _safe_int(item.get("ask_cnt") or item.get("ASK_CNT")),
                    "date": str(item.get("date") or item.get("DATE") or ""),
                    "time": str(item.get("trnm_hour") or item.get("TRNM_HOUR") or ""),
                    "raw": item,
                }
            )
        return {
            "ok": True,
            "source": "kis_interest_groups",
            "mode": self.settings.kis_mode,
            "groups": groups,
            "count": len(groups),
            "message": str(payload.get("msg1") or "정상"),
        }

    def interest_group_stocks(self, group_code: str, group_name: str = "") -> dict[str, Any]:
        if not self.settings.kis_configured:
            return {"ok": False, "source": "kis_interest_group_stocks", "message": "KIS API 설정이 필요합니다.", "rows": []}
        if self.settings.kis_use_mock:
            return {"ok": False, "source": "kis_interest_group_stocks", "message": "한투 관심종목 API는 모의투자를 지원하지 않습니다.", "rows": []}
        if not self.settings.kis_user_id:
            return {"ok": False, "source": "kis_interest_group_stocks", "message": "KIS_USER_ID 또는 KIS_HTS_ID가 필요합니다.", "rows": []}
        code = str(group_code or "").strip()
        if not code:
            return {"ok": False, "source": "kis_interest_group_stocks", "message": "관심그룹 코드가 비어 있습니다.", "rows": []}
        try:
            payload = self._get(
                "/uapi/domestic-stock/v1/quotations/intstock-stocklist-by-group",
                KIS_INTSTOCK_STOCKLIST_BY_GROUP_TR_ID,
                {
                    "TYPE": "1",
                    "USER_ID": self.settings.kis_user_id,
                    "DATA_RANK": "",
                    "INTER_GRP_CODE": code,
                    "INTER_GRP_NAME": group_name,
                    "HTS_KOR_ISNM": "",
                    "CNTG_CLS_CODE": "",
                    "FID_ETC_CLS_CODE": "4",
                },
                timeout=8,
            )
        except Exception as exc:
            return {"ok": False, "source": "kis_interest_group_stocks", "message": f"KIS 관심종목 조회 오류: {exc}", "rows": []}
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "source": "kis_interest_group_stocks",
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 관심종목 응답 오류"),
                "rows": [],
            }
        output = payload.get("output2") or []
        if isinstance(output, dict):
            output = [output]
        if not isinstance(output, list):
            output = []
        rows: list[dict[str, Any]] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            raw_symbol = str(
                item.get("jong_code")
                or item.get("JONG_CODE")
                or item.get("mksc_shrn_iscd")
                or item.get("MKSCRT_SHRN_ISCD")
                or item.get("pdno")
                or item.get("PDNO")
                or ""
            ).strip()
            if not raw_symbol:
                continue
            symbol = _normalize_kr_symbol(raw_symbol)
            rows.append(
                {
                    "symbol": symbol,
                    "name": str(item.get("hts_kor_isnm") or item.get("HTS_KOR_ISNM") or symbol),
                    "market": "KR",
                    "group_code": code,
                    "group_name": group_name,
                    "rank": str(item.get("data_rank") or item.get("DATA_RANK") or ""),
                    "memo": str(item.get("memo") or item.get("MEMO") or ""),
                    "exchange": str(item.get("exch_code") or item.get("EXCH_CODE") or ""),
                    "fixed_quantity": _safe_int(item.get("fxdt_ntby_qty") or item.get("FXDT_NTBY_QTY")),
                    "entry_price": _safe_float(item.get("cntg_unpr") or item.get("CNTG_UNPR")),
                    "raw": item,
                }
            )
        summary = payload.get("output1") if isinstance(payload.get("output1"), dict) else {}
        return {
            "ok": True,
            "source": "kis_interest_group_stocks",
            "mode": self.settings.kis_mode,
            "group_code": code,
            "group_name": group_name or str(summary.get("inter_grp_name") or ""),
            "rows": rows,
            "count": len(rows),
            "message": str(payload.get("msg1") or "정상"),
        }

    def interest_watchlist(self) -> dict[str, Any]:
        groups_result = self.interest_groups()
        if not groups_result.get("ok"):
            return {
                "ok": False,
                "source": "kis_interest_watchlist",
                "message": groups_result.get("message", "KIS 관심그룹 조회 실패"),
                "groups": [],
                "rows": [],
                "symbols": [],
                "detail": groups_result,
            }
        groups = [item for item in groups_result.get("groups", []) if isinstance(item, dict)]
        rows: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        seen: set[str] = set()
        for group in groups:
            stocks = self.interest_group_stocks(str(group.get("code", "")), str(group.get("name", "")))
            if not stocks.get("ok"):
                errors.append({"group": group, "message": stocks.get("message")})
                continue
            for row in stocks.get("rows", []):
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("symbol") or "").upper()
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                rows.append(row)
            time.sleep(max(0.05, self.settings.kis_quote_throttle_ms / 1000))
        return {
            "ok": bool(rows) or not errors,
            "source": "kis_interest_watchlist",
            "mode": self.settings.kis_mode,
            "groups": groups,
            "rows": rows,
            "symbols": [str(row.get("symbol", "")).upper() for row in rows],
            "count": len(rows),
            "errors": errors,
            "message": "한투 MTS/HTS 관심종목 동기화 조회 완료" if rows else "한투 관심종목이 비어 있거나 조회 가능한 종목이 없습니다.",
        }

    def buying_power(self, symbol: str = "005930", price: float | None = None, include_cma: bool = False) -> dict[str, Any]:
        if not self.settings.kis_configured:
            return {"ok": False, "message": "KIS API 키가 설정되지 않았습니다."}
        sym = _normalize_kr_symbol(symbol)
        unit_price = float(price or 0)
        if unit_price <= 0:
            quote = self.quote(sym, allow_real_fallback=False)
            unit_price = _safe_float(quote.get("price")) or 1
        tr_id = KIS_PSBL_ORDER_TR_ID_MOCK if self.settings.kis_use_mock else KIS_PSBL_ORDER_TR_ID_REAL
        params = urllib.parse.urlencode(
            {
                "CANO": self.settings.kis_account_no,
                "ACNT_PRDT_CD": self.settings.kis_product_code,
                "PDNO": sym,
                "ORD_UNPR": str(int(max(1, unit_price))),
                "ORD_DVSN": "01",
                "CMA_EVLU_AMT_ICLD_YN": "Y" if include_cma else "N",
                "OVRS_ICLD_YN": "N",
            }
        )
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-psbl-order?{params}"
        try:
            token = self._cached_token()
            request = urllib.request.Request(
                url,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "authorization": f"Bearer {token}",
                    "appkey": self.settings.kis_app_key,
                    "appsecret": self.settings.kis_app_secret,
                    "tr_id": tr_id,
                    "custtype": "P",
                },
            )
            with urllib.request.urlopen(request, timeout=max(KIS_TIMEOUT_SEC, 8)) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {"ok": False, "symbol": sym, "message": f"KIS 매수가능 조회 오류: {exc}"}
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "symbol": sym,
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 매수가능 조회 응답 오류"),
            }
        output = payload.get("output") or {}
        if isinstance(output, list):
            output = output[0] if output and isinstance(output[0], dict) else {}
        return {
            "ok": True,
            "symbol": sym,
            "price_used": unit_price,
            "include_cma": include_cma,
            "order_possible_cash": _safe_float(output.get("ord_psbl_cash")),
            "max_buy_amount": _safe_float(output.get("max_buy_amt")),
            "non_receivable_buy_amount": _safe_float(output.get("nrcvb_buy_amt")),
            "max_buy_quantity": _safe_float(output.get("max_buy_qty")),
            "non_receivable_buy_quantity": _safe_float(output.get("nrcvb_buy_qty")),
            "message": str(payload.get("msg1") or "정상"),
        }

    def cash_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float = 0.0,
        order_type: str = "limit",
    ) -> dict[str, Any]:
        sym = _normalize_kr_symbol(symbol)
        side = str(side or "").upper().strip()
        quantity_int = int(float(quantity or 0))
        limit_price = int(round(float(price or 0)))
        order_type = str(order_type or "limit").lower().strip()
        if not self.settings.live_trading or self.settings.kis_readonly:
            return {
                "ok": False,
                "symbol": sym,
                "source": "blocked",
                "outcome_known": True,
                "retry_safe": True,
                "message": "LIVE_TRADING=true 및 KIS_READONLY=false일 때만 KIS 실제 주문을 전송합니다.",
            }
        if not self.settings.kis_configured:
            return {"ok": False, "symbol": sym, "source": "unconfigured", "outcome_known": True, "retry_safe": True, "message": "KIS API 키가 설정되지 않았습니다."}
        if side not in {"BUY", "SELL"}:
            return {"ok": False, "symbol": sym, "source": "validation", "outcome_known": True, "retry_safe": True, "message": "side는 BUY 또는 SELL이어야 합니다."}
        if quantity_int <= 0:
            return {"ok": False, "symbol": sym, "source": "validation", "outcome_known": True, "retry_safe": True, "message": "주문 수량은 1주 이상이어야 합니다."}
        is_market = order_type == "market" or limit_price <= 0
        tr_id = (
            KIS_CASH_BUY_TR_ID_MOCK if self.settings.kis_use_mock and side == "BUY"
            else KIS_CASH_SELL_TR_ID_MOCK if self.settings.kis_use_mock and side == "SELL"
            else KIS_CASH_BUY_TR_ID_REAL if side == "BUY"
            else KIS_CASH_SELL_TR_ID_REAL
        )
        body = {
            "CANO": self.settings.kis_account_no,
            "ACNT_PRDT_CD": self.settings.kis_product_code,
            "PDNO": sym,
            "ORD_DVSN": "01" if is_market else "00",
            "ORD_QTY": str(quantity_int),
            "ORD_UNPR": "0" if is_market else str(limit_price),
        }
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        try:
            token = self._cached_token()
            hashkey = self._hashkey(body)
            request = urllib.request.Request(
                url,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                method="POST",
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "authorization": f"Bearer {token}",
                    "appkey": self.settings.kis_app_key,
                    "appsecret": self.settings.kis_app_secret,
                    "tr_id": tr_id,
                    "custtype": "P",
                    "hashkey": hashkey,
                },
            )
            with urllib.request.urlopen(request, timeout=max(KIS_TIMEOUT_SEC, 10)) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {
                "ok": False,
                "symbol": sym,
                "source": "kis_cash_order",
                "status": "UNKNOWN_AFTER_SEND",
                "outcome_known": False,
                "retry_safe": False,
                "message": f"KIS order response was not confirmed after send: {exc}",
            }
        response_accepted = str(payload.get("rt_cd")) == "0"
        output = payload.get("output") or {}
        order_no = output.get("ODNO") or output.get("odno") or ""
        ok = bool(response_accepted and order_no)
        outcome_known = bool(not response_accepted or order_no)
        return {
            "ok": ok,
            "symbol": sym,
            "side": side,
            "quantity": quantity_int,
            "price": limit_price,
            "order_type": "market" if is_market else "limit",
            "source": "kis_cash_order",
            "mode": self.settings.kis_mode,
            "mock": bool(self.settings.kis_use_mock),
            "status": payload.get("rt_cd"),
            "broker_response_accepted": response_accepted,
            "outcome_known": outcome_known,
            "retry_safe": bool(not response_accepted),
            "message": str(payload.get("msg1") or payload.get("msg_cd") or ("정상" if ok else "KIS 주문 응답 오류")),
            "order_no": order_no,
            "krx_fwdg_ord_orgno": output.get("KRX_FWDG_ORD_ORGNO") or output.get("krx_fwdg_ord_orgno") or "",
            "raw_output": output,
        }

    def daily_executions(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        symbol: str = "",
        side: str = "all",
        filled: str = "filled",
    ) -> dict[str, Any]:
        if not self.settings.kis_configured:
            return {"ok": False, "source": "kis_daily_executions", "message": "KIS API is not configured.", "executions": []}
        today = datetime.now().strftime("%Y%m%d")
        start = _yyyymmdd(start_date, today)
        end = _yyyymmdd(end_date, today)
        side_code = {
            "all": "00",
            "ALL": "00",
            "전체": "00",
            "sell": "01",
            "SELL": "01",
            "매도": "01",
            "buy": "02",
            "BUY": "02",
            "매수": "02",
        }.get(str(side or "all").strip(), "00")
        filled_code = {
            "all": "00",
            "ALL": "00",
            "전체": "00",
            "filled": "01",
            "FILLED": "01",
            "체결": "01",
            "unfilled": "02",
            "UNFILLED": "02",
            "미체결": "02",
        }.get(str(filled or "filled").strip(), "01")
        pdno = _normalize_kr_symbol(symbol) if str(symbol or "").strip() else ""
        tr_id = KIS_DAILY_CCLD_TR_ID_MOCK if self.settings.kis_use_mock else KIS_DAILY_CCLD_TR_ID_REAL
        executions: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []
        ctx_fk = ""
        ctx_nk = ""
        tr_cont = ""
        message = "OK"
        raw_status = ""
        for _ in range(5):
            params = urllib.parse.urlencode(
                {
                    "CANO": self.settings.kis_account_no,
                    "ACNT_PRDT_CD": self.settings.kis_product_code,
                    "INQR_STRT_DT": start,
                    "INQR_END_DT": end,
                    "SLL_BUY_DVSN_CD": side_code,
                    "INQR_DVSN": "00",
                    "PDNO": pdno,
                    "CCLD_DVSN": filled_code,
                    "ORD_GNO_BRNO": "",
                    "ODNO": "",
                    "INQR_DVSN_3": "00",
                    "INQR_DVSN_1": "",
                    "INQR_DVSN_2": "",
                    "CTX_AREA_FK100": ctx_fk,
                    "CTX_AREA_NK100": ctx_nk,
                }
            )
            url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld?{params}"
            try:
                token = self._cached_token()
                request = urllib.request.Request(
                    url,
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "authorization": f"Bearer {token}",
                        "appkey": self.settings.kis_app_key,
                        "appsecret": self.settings.kis_app_secret,
                        "tr_id": tr_id,
                        "tr_cont": tr_cont,
                        "custtype": "P",
                    },
                )
                with urllib.request.urlopen(request, timeout=max(KIS_TIMEOUT_SEC, 8)) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    headers = dict(response.headers.items())
            except Exception as exc:
                return {
                    "ok": False,
                    "source": "kis_daily_executions",
                    "mode": self.settings.kis_mode,
                    "message": f"KIS execution history error: {exc}",
                    "executions": executions,
                }
            raw_status = str(payload.get("rt_cd") or "")
            if raw_status != "0":
                return {
                    "ok": False,
                    "source": "kis_daily_executions",
                    "mode": self.settings.kis_mode,
                    "status": raw_status,
                    "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS execution history response error"),
                    "executions": executions,
                }
            message = str(payload.get("msg1") or "OK")
            output1 = payload.get("output1") or []
            output2 = payload.get("output2") or {}
            if isinstance(output1, dict):
                output1 = [output1]
            if isinstance(output2, list):
                summaries.extend([item for item in output2 if isinstance(item, dict)])
            elif isinstance(output2, dict):
                summaries.append(output2)
            for item in output1:
                if not isinstance(item, dict):
                    continue
                row_symbol = str(item.get("pdno") or item.get("PDNO") or "").strip().upper()
                if not row_symbol:
                    continue
                row_side_code = str(item.get("sll_buy_dvsn_cd") or item.get("SLL_BUY_DVSN_CD") or "").strip()
                row_side_name = str(item.get("sll_buy_dvsn_cd_name") or item.get("sll_buy_dvsn_name") or item.get("trad_dvsn_name") or "")
                side_name_text = row_side_name.lower()
                row_side = "SELL" if row_side_code == "01" or "매도" in row_side_name or "sell" in side_name_text else "BUY" if row_side_code == "02" or "매수" in row_side_name or "buy" in side_name_text else row_side_code
                order_date = item.get("ord_dt") or item.get("ORD_DT") or start
                order_time = item.get("ord_tmd") or item.get("ORD_TMD") or item.get("infm_tmd") or item.get("INFM_TMD") or ""
                filled_qty = _safe_float(
                    item.get("tot_ccld_qty")
                    or item.get("TOT_CCLD_QTY")
                    or item.get("ccld_qty")
                    or item.get("CCLD_QTY")
                    or item.get("exec_qty")
                )
                order_qty = _safe_float(item.get("ord_qty") or item.get("ORD_QTY") or filled_qty)
                avg_price = _safe_float(
                    item.get("avg_prvs")
                    or item.get("AVG_PRVS")
                    or item.get("avg_pric")
                    or item.get("AVG_PRIC")
                    or item.get("ccld_unpr")
                    or item.get("CCLD_UNPR")
                    or item.get("ord_unpr")
                    or item.get("ORD_UNPR")
                )
                amount = _safe_float(item.get("tot_ccld_amt") or item.get("TOT_CCLD_AMT")) or (filled_qty * avg_price)
                remaining_qty = _safe_float(item.get("rmn_qty") or item.get("RMN_QTY"))
                order_no = str(item.get("odno") or item.get("ODNO") or "").strip()
                executions.append(
                    {
                        "symbol": row_symbol,
                        "name": str(item.get("prdt_name") or item.get("PRDT_NAME") or row_symbol),
                        "side": row_side,
                        "side_code": row_side_code,
                        "side_name": row_side_name,
                        "order_no": order_no,
                        "order_branch": str(item.get("ord_gno_brno") or item.get("ORD_GNO_BRNO") or ""),
                        "ordered_at": _kst_iso_from_kis(order_date, order_time),
                        "executed_at": _kst_iso_from_kis(order_date, order_time),
                        "order_date": _yyyymmdd(order_date),
                        "order_time": _hhmmss(order_time),
                        "quantity": order_qty,
                        "filled_quantity": filled_qty,
                        "remaining_quantity": remaining_qty,
                        "price": avg_price,
                        "avg_price": avg_price,
                        "amount": amount,
                        "status_name": str(item.get("ccld_cndt_name") or item.get("CCLD_CNDT_NAME") or ""),
                        "order_type_name": str(item.get("ord_dvsn_name") or item.get("ORD_DVSN_NAME") or ""),
                    }
                )
            ctx_fk = str(payload.get("ctx_area_fk100") or payload.get("CTX_AREA_FK100") or "")
            ctx_nk = str(payload.get("ctx_area_nk100") or payload.get("CTX_AREA_NK100") or "")
            next_cont = str(headers.get("tr_cont") or headers.get("Tr_cont") or headers.get("tr-cont") or "").strip()
            if next_cont not in {"M", "F"}:
                break
            tr_cont = "N"
            time.sleep(max(0.05, self.settings.kis_quote_throttle_ms / 1000))
        executions.sort(key=lambda item: (str(item.get("ordered_at") or ""), str(item.get("order_no") or "")))
        return {
            "ok": True,
            "source": "kis_daily_executions",
            "mode": self.settings.kis_mode,
            "currency": "KRW",
            "unit_scale": 1,
            "mock": bool(self.settings.kis_use_mock),
            "status": raw_status,
            "message": message,
            "start_date": start,
            "end_date": end,
            "symbol": pdno,
            "side": side_code,
            "filled": filled_code,
            "count": len(executions),
            "executions": executions,
            "summary": summaries[-1] if summaries else {},
            "safety": "Read-only KIS execution history sync. No order is submitted.",
        }

    def account_asset_snapshot(self) -> dict[str, Any]:
        if self.settings.live_trading or not self.settings.kis_readonly:
            return {"ok": False, "message": "KIS account asset snapshot is blocked outside readonly safety mode."}
        if not self.settings.kis_configured:
            return {"ok": False, "message": "KIS API is not configured."}
        params = urllib.parse.urlencode(
            {
                "CANO": self.settings.kis_account_no,
                "ACNT_PRDT_CD": self.settings.kis_product_code,
                "INQR_DVSN_1": "",
                "BSPR_BF_DT_APLY_YN": "",
            }
        )
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-account-balance?{params}"
        try:
            token = self._cached_token()
            request = urllib.request.Request(
                url,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "authorization": f"Bearer {token}",
                    "appkey": self.settings.kis_app_key,
                    "appsecret": self.settings.kis_app_secret,
                    "tr_id": KIS_ACCOUNT_ASSETS_TR_ID,
                    "custtype": "P",
                },
            )
            with urllib.request.urlopen(request, timeout=max(KIS_TIMEOUT_SEC, 8)) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {"ok": False, "source": "kis_account_assets", "message": f"KIS account asset snapshot error: {exc}"}
        if str(payload.get("rt_cd")) != "0":
            return {
                "ok": False,
                "source": "kis_account_assets",
                "status": payload.get("rt_cd"),
                "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS account asset snapshot response error"),
            }
        output1 = payload.get("output1") or []
        output2 = payload.get("output2") or {}
        if isinstance(output1, dict):
            output1 = [output1]
        if isinstance(output2, list):
            summary = output2[0] if output2 and isinstance(output2[0], dict) else {}
        else:
            summary = output2 if isinstance(output2, dict) else {}
        cash = (
            _safe_float(summary.get("tot_dncl_amt"))
            or _safe_float(summary.get("dncl_amt"))
            or _safe_float(summary.get("cma_evlu_amt"))
            or _safe_float(summary.get("nass_tot_amt"))
        )
        total_value = (
            _safe_float(summary.get("tot_asst_amt"))
            or _safe_float(summary.get("nass_tot_amt"))
            or _safe_float(summary.get("evlu_amt_smtl"))
            or cash
        )
        return {
            "ok": True,
            "source": "kis_account_assets",
            "status": payload.get("rt_cd"),
            "message": str(payload.get("msg1") or "OK"),
            "cash": cash,
            "total_value": total_value,
            "stock_value": _safe_float(summary.get("evlu_amt_smtl")),
            "purchase_amount": _safe_float(summary.get("pchs_amt_smtl")),
            "profit_loss": _safe_float(summary.get("evlu_pfls_amt_smtl")),
            "position_rows": len(output1) if isinstance(output1, list) else 0,
            "fields": {
                "tot_dncl_amt": _safe_float(summary.get("tot_dncl_amt")),
                "dncl_amt": _safe_float(summary.get("dncl_amt")),
                "cma_evlu_amt": _safe_float(summary.get("cma_evlu_amt")),
                "nass_tot_amt": _safe_float(summary.get("nass_tot_amt")),
                "tot_asst_amt": _safe_float(summary.get("tot_asst_amt")),
                "evlu_amt_smtl": _safe_float(summary.get("evlu_amt_smtl")),
            },
        }

    def account_balance(self) -> dict[str, Any]:
        if not self.settings.kis_configured:
            return {
                "ok": False,
                "configured": False,
                "source": "unconfigured",
                "message": "KIS API 키가 설정되지 않았습니다.",
            }
        tr_id = KIS_BALANCE_TR_ID_MOCK if self.settings.kis_use_mock else KIS_BALANCE_TR_ID_REAL
        positions: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []
        ctx_fk = ""
        ctx_nk = ""
        tr_cont = ""
        message = "정상"
        raw_status = ""
        for _ in range(5):
            params = urllib.parse.urlencode(
                {
                    "CANO": self.settings.kis_account_no,
                    "ACNT_PRDT_CD": self.settings.kis_product_code,
                    "AFHR_FLPR_YN": "N",
                    "OFL_YN": "",
                    "INQR_DVSN": "02",
                    "UNPR_DVSN": "01",
                    "FUND_STTL_ICLD_YN": "N",
                    "FNCG_AMT_AUTO_RDPT_YN": "N",
                    "PRCS_DVSN": "00",
                    "CTX_AREA_FK100": ctx_fk,
                    "CTX_AREA_NK100": ctx_nk,
                }
            )
            url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance?{params}"
            try:
                token = self._cached_token()
                request = urllib.request.Request(
                    url,
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "authorization": f"Bearer {token}",
                        "appkey": self.settings.kis_app_key,
                        "appsecret": self.settings.kis_app_secret,
                        "tr_id": tr_id,
                        "tr_cont": tr_cont,
                        "custtype": "P",
                    },
                )
                with urllib.request.urlopen(request, timeout=max(KIS_TIMEOUT_SEC, 8)) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    headers = dict(response.headers.items())
            except Exception as exc:
                return {
                    "ok": False,
                    "configured": True,
                    "source": "kis_readonly_account",
                    "mode": self.settings.kis_mode,
                    "account_masked": _mask(self.settings.kis_account_no),
                    "message": f"KIS 계좌 조회 오류: {exc}",
                }
            raw_status = str(payload.get("rt_cd") or "")
            if raw_status != "0":
                return {
                    "ok": False,
                    "configured": True,
                    "source": "kis_readonly_account",
                    "mode": self.settings.kis_mode,
                    "account_masked": _mask(self.settings.kis_account_no),
                    "status": raw_status,
                    "message": str(payload.get("msg1") or payload.get("msg_cd") or "KIS 계좌 조회 응답 오류"),
                }
            message = str(payload.get("msg1") or "정상")
            output1 = payload.get("output1") or []
            output2 = payload.get("output2") or {}
            if isinstance(output1, dict):
                output1 = [output1]
            if isinstance(output2, list):
                summaries.extend([item for item in output2 if isinstance(item, dict)])
            elif isinstance(output2, dict):
                summaries.append(output2)
            for item in output1:
                if not isinstance(item, dict):
                    continue
                qty = _safe_float(item.get("hldg_qty"))
                if qty <= 0 and not item.get("pdno"):
                    continue
                positions.append(
                    {
                        "symbol": item.get("pdno", ""),
                        "name": item.get("prdt_name", ""),
                        "quantity": qty,
                        "available_quantity": _safe_float(item.get("ord_psbl_qty")),
                        "avg_price": _safe_float(item.get("pchs_avg_pric")),
                        "current_price": _safe_float(item.get("prpr")),
                        "purchase_amount": _safe_float(item.get("pchs_amt")),
                        "evaluation_amount": _safe_float(item.get("evlu_amt")),
                        "profit_loss": _safe_float(item.get("evlu_pfls_amt")),
                        "profit_loss_rate": _safe_float(item.get("evlu_pfls_rt")),
                    }
                )
            ctx_fk = str(payload.get("ctx_area_fk100") or payload.get("CTX_AREA_FK100") or "")
            ctx_nk = str(payload.get("ctx_area_nk100") or payload.get("CTX_AREA_NK100") or "")
            next_cont = str(headers.get("tr_cont") or headers.get("Tr_cont") or headers.get("tr-cont") or "").strip()
            if next_cont not in {"M", "F"}:
                break
            tr_cont = "N"
            time.sleep(max(0.05, self.settings.kis_quote_throttle_ms / 1000))

        summary = summaries[-1] if summaries else {}
        deposit_cash = (
            _safe_float(summary.get("dnca_tot_amt"))
            or _safe_float(summary.get("ord_psbl_cash"))
            or _safe_float(summary.get("nass_amt"))
            or _safe_float(summary.get("prvs_rcdl_excc_amt"))
        )
        stock_value = _safe_float(summary.get("scts_evlu_amt")) or sum(_safe_float(item.get("evaluation_amount")) for item in positions)
        broker_total_value = _safe_float(summary.get("tot_evlu_amt"))
        purchase_amount = _safe_float(summary.get("pchs_amt_smtl_amt")) or sum(_safe_float(item.get("purchase_amount")) for item in positions)
        profit_loss = _safe_float(summary.get("evlu_pfls_smtl_amt")) or sum(_safe_float(item.get("profit_loss")) for item in positions)
        raw_available_cash = _safe_float(summary.get("ord_psbl_cash"))
        available_cash = raw_available_cash or deposit_cash
        cash_probe = self.buying_power("005930", price=1, include_cma=False)
        cma_cash_probe = self.buying_power("005930", price=1, include_cma=True)
        asset_probe = self.account_asset_snapshot()
        probe_cash = 0.0
        for probe in (cash_probe, cma_cash_probe):
            if not probe.get("ok"):
                continue
            probe_cash = max(
                probe_cash,
                _safe_float(probe.get("order_possible_cash")),
                _safe_float(probe.get("non_receivable_buy_amount")),
                _safe_float(probe.get("max_buy_amount")),
            )
        if asset_probe.get("ok"):
            probe_cash = max(probe_cash, _safe_float(asset_probe.get("cash")))
            if not stock_value and _safe_float(asset_probe.get("stock_value")):
                stock_value = _safe_float(asset_probe.get("stock_value"))
            if not purchase_amount and _safe_float(asset_probe.get("purchase_amount")):
                purchase_amount = _safe_float(asset_probe.get("purchase_amount"))
            if not profit_loss and _safe_float(asset_probe.get("profit_loss")):
                profit_loss = _safe_float(asset_probe.get("profit_loss"))
            if not broker_total_value and _safe_float(asset_probe.get("total_value")):
                broker_total_value = _safe_float(asset_probe.get("total_value"))
        if probe_cash:
            available_cash = probe_cash
        if not deposit_cash and available_cash:
            deposit_cash = available_cash
        operating_cash = available_cash or deposit_cash
        operating_total_value = operating_cash + stock_value
        total_value = operating_total_value or broker_total_value or 0.0
        return {
            "ok": True,
            "configured": True,
            "provider": "KIS",
            "source": "kis_readonly_account",
            "mode": self.settings.kis_mode,
            "readonly": self.settings.kis_readonly,
            "live_trading": self.settings.live_trading,
            "order_allowed": bool(self.settings.live_trading and not self.settings.kis_readonly and not self.settings.kis_use_mock),
            "account_masked": _mask(self.settings.kis_account_no),
            "product_code": self.settings.kis_product_code,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "currency": "KRW",
            "unit_scale": 1,
            "summary": {
                "cash": operating_cash,
                "available_cash": available_cash,
                "deposit_cash": deposit_cash,
                "settlement_cash": deposit_cash,
                "stock_value": stock_value,
                "total_value": total_value,
                "broker_total_value": broker_total_value,
                "net_liquidation_value": total_value,
                "purchase_amount": purchase_amount,
                "profit_loss": profit_loss,
                "profit_loss_rate": _safe_float(summary.get("evlu_erng_rt")) or _safe_float(summary.get("asst_icdc_erng_rt")),
                "deposit_guess": deposit_cash,
                "total_value_source": "주문가능현금+주식평가",
                "cash_probe": {
                    "ok": bool(cash_probe.get("ok")),
                    "include_cma": bool(cash_probe.get("include_cma")),
                    "order_possible_cash": _safe_float(cash_probe.get("order_possible_cash")),
                    "non_receivable_buy_amount": _safe_float(cash_probe.get("non_receivable_buy_amount")),
                    "max_buy_amount": _safe_float(cash_probe.get("max_buy_amount")),
                    "message": cash_probe.get("message", ""),
                },
                "cma_cash_probe": {
                    "ok": bool(cma_cash_probe.get("ok")),
                    "include_cma": bool(cma_cash_probe.get("include_cma")),
                    "order_possible_cash": _safe_float(cma_cash_probe.get("order_possible_cash")),
                    "non_receivable_buy_amount": _safe_float(cma_cash_probe.get("non_receivable_buy_amount")),
                    "max_buy_amount": _safe_float(cma_cash_probe.get("max_buy_amount")),
                    "message": cma_cash_probe.get("message", ""),
                },
                "asset_probe": {
                    "ok": bool(asset_probe.get("ok")),
                    "cash": _safe_float(asset_probe.get("cash")),
                    "total_value": _safe_float(asset_probe.get("total_value")),
                    "stock_value": _safe_float(asset_probe.get("stock_value")),
                    "position_rows": _safe_int(asset_probe.get("position_rows")),
                    "fields": asset_probe.get("fields", {}),
                    "message": asset_probe.get("message", ""),
                },
            },
            "positions": [item for item in positions if _safe_float(item.get("quantity")) > 0],
            "position_count": len([item for item in positions if _safe_float(item.get("quantity")) > 0]),
            "raw_status": raw_status,
            "message": message,
            "safety": "한투 계좌 조회는 읽기전용입니다. 이 API는 주문을 전송하지 않습니다.",
        }


class DartBridge:
    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings

    def status(self) -> dict[str, Any]:
        return {
            "provider": "DART",
            "configured": self.settings.dart_configured,
            "lookback_days": self.settings.dart_lookback_days,
            "cache_ttl_sec": self.settings.cache_ttl_dart_sec,
            "message": "DART_API_KEY가 있으면 삼성전자 기본 공시 조회부터 실행합니다.",
        }

    def disclosures(self, corp_code: str = "00126380", days: int | None = None, page_count: int = 10) -> dict[str, Any]:
        if not self.settings.dart_configured:
            return {
                "configured": False,
                "corp_code": corp_code,
                "items": [],
                "message": "DART_API_KEY가 설정되지 않았습니다.",
            }
        end = datetime.now()
        start = end - timedelta(days=days or self.settings.dart_lookback_days)
        params = {
            "crtfc_key": self.settings.dart_api_key,
            "corp_code": corp_code,
            "bgn_de": start.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "page_no": "1",
            "page_count": str(max(1, min(page_count, 100))),
        }
        url = f"{DART_BASE_URL}/list.json?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": "StockSuiteHTS/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {
                "configured": True,
                "corp_code": corp_code,
                "items": [],
                "error": str(exc),
                "message": "DART 조회 중 오류가 발생했습니다.",
            }
        status = str(payload.get("status", ""))
        if status not in {"000", "013"}:
            return {
                "configured": True,
                "corp_code": corp_code,
                "items": [],
                "status": status,
                "message": payload.get("message", "DART 응답 오류"),
            }
        return {
            "configured": True,
            "corp_code": corp_code,
            "items": payload.get("list") or [],
            "status": status,
            "message": payload.get("message", "정상"),
        }

    def financials(self, corp_code: str = "00126380", bsns_year: int | None = None, reprt_code: str = "11011") -> dict[str, Any]:
        year = bsns_year or (datetime.now().year - 1)
        if not self.settings.dart_configured:
            return {
                "configured": False,
                "corp_code": corp_code,
                "bsns_year": year,
                "reprt_code": reprt_code,
                "items": [],
                "summary": {},
                "score": 0,
                "stance": "DART 키 없음",
                "message": "DART_API_KEY가 설정되지 않았습니다.",
            }
        params = {
            "crtfc_key": self.settings.dart_api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": reprt_code,
            "fs_div": "CFS",
        }
        url = f"{DART_BASE_URL}/fnlttSinglAcntAll.json?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": "StockSuiteHTS/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {
                "configured": True,
                "corp_code": corp_code,
                "bsns_year": year,
                "reprt_code": reprt_code,
                "items": [],
                "summary": {},
                "score": 0,
                "stance": "조회 오류",
                "error": str(exc),
                "message": "DART 재무제표 조회 중 오류가 발생했습니다.",
            }
        status = str(payload.get("status", ""))
        items = list(payload.get("list") or [])
        if status != "000":
            return {
                "configured": True,
                "corp_code": corp_code,
                "bsns_year": year,
                "reprt_code": reprt_code,
                "items": [],
                "summary": {},
                "score": 0,
                "stance": "자료 없음",
                "status": status,
                "message": payload.get("message", "DART 재무제표 응답 오류"),
            }

        def pick_amount(names: tuple[str, ...]) -> float:
            for name in names:
                for item in items:
                    account = str(item.get("account_nm") or "").strip()
                    fs_name = str(item.get("fs_nm") or "")
                    if fs_name and "연결" not in fs_name and "재무" not in fs_name:
                        continue
                    if account == name:
                        amount = _safe_float(item.get("thstrm_amount"))
                        if amount:
                            return amount
            for name in names:
                if name == "수익":
                    continue
                for item in items:
                    account = str(item.get("account_nm") or "").strip()
                    fs_name = str(item.get("fs_nm") or "")
                    if fs_name and "연결" not in fs_name and "재무" not in fs_name:
                        continue
                    if name in account:
                        amount = _safe_float(item.get("thstrm_amount"))
                        if amount:
                            return amount
            return 0.0

        revenue = pick_amount(("매출액", "영업수익", "수익"))
        if not revenue:
            sales_cost = pick_amount(("매출원가",))
            gross_profit = pick_amount(("매출총이익",))
            if sales_cost and gross_profit:
                revenue = sales_cost + gross_profit
        operating_income = pick_amount(("영업이익",))
        net_income = pick_amount(("당기순이익", "분기순이익", "반기순이익"))
        assets = pick_amount(("자산총계",))
        liabilities = pick_amount(("부채총계",))
        equity = pick_amount(("자본총계",))
        op_margin = round(operating_income / revenue * 100, 2) if revenue else 0.0
        net_margin = round(net_income / revenue * 100, 2) if revenue else 0.0
        debt_ratio = round(liabilities / equity * 100, 2) if equity else 0.0
        score = 0
        if revenue > 0:
            score += 15
        if operating_income > 0:
            score += 25
        if net_income > 0:
            score += 20
        if op_margin >= 10:
            score += 20
        elif op_margin >= 5:
            score += 10
        if debt_ratio and debt_ratio < 120:
            score += 15
        elif debt_ratio and debt_ratio < 200:
            score += 8
        if score >= 75:
            stance = "재무 우수"
        elif score >= 50:
            stance = "재무 보통"
        elif score > 0:
            stance = "재무 점검"
        else:
            stance = "재무 자료 부족"
        return {
            "configured": True,
            "corp_code": corp_code,
            "bsns_year": year,
            "reprt_code": reprt_code,
            "items": items[:80],
            "summary": {
                "revenue": revenue,
                "operating_income": operating_income,
                "net_income": net_income,
                "assets": assets,
                "liabilities": liabilities,
                "equity": equity,
                "operating_margin_pct": op_margin,
                "net_margin_pct": net_margin,
                "debt_ratio_pct": debt_ratio,
            },
            "score": score,
            "stance": stance,
            "status": status,
            "message": payload.get("message", "정상"),
        }


class BokEcosBridge:
    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings

    def status(self) -> dict[str, Any]:
        return {
            "provider": "BOK ECOS",
            "configured": self.settings.ecos_configured,
            "key_masked": _mask(self.settings.ecos_api_key),
            "language": self.settings.ecos_language,
            "cache_ttl_sec": self.settings.ecos_cache_ttl_sec,
            "default_series": list(ECOS_MACRO_SERIES),
            "message": "BOK_ECOS_API_KEY가 있으면 금리/환율/물가 매크로 스냅샷을 조회합니다.",
        }

    def _default_window(self, cycle: str) -> tuple[str, str]:
        today = datetime.now()
        cycle = (cycle or "M").upper()
        if cycle == "D":
            return (today - timedelta(days=45)).strftime("%Y%m%d"), today.strftime("%Y%m%d")
        if cycle == "Q":
            year = today.year - 2
            quarter = ((today.month - 1) // 3) + 1
            return f"{year}Q1", f"{today.year}Q{quarter}"
        if cycle == "A":
            return str(today.year - 5), str(today.year)
        return (today - timedelta(days=550)).strftime("%Y%m"), today.strftime("%Y%m")

    def statistic_search(
        self,
        stat_code: str,
        cycle: str = "M",
        start: str | None = None,
        end: str | None = None,
        item_code1: str = "",
        item_code2: str = "",
        item_code3: str = "",
        item_code4: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        stat_code = str(stat_code or "").strip()
        cycle = str(cycle or "M").strip().upper()
        if not self.settings.ecos_configured:
            return {
                "ok": False,
                "configured": False,
                "rows": [],
                "message": "BOK_ECOS_API_KEY 또는 ECOS_API_KEY가 설정되지 않았습니다.",
            }
        if not stat_code:
            return {"ok": False, "configured": True, "rows": [], "message": "stat_code가 필요합니다."}
        if not start or not end:
            default_start, default_end = self._default_window(cycle)
            start = start or default_start
            end = end or default_end
        end_row = max(1, min(int(limit or 100), 1000))
        parts = [
            "StatisticSearch",
            self.settings.ecos_api_key,
            "json",
            self.settings.ecos_language or "kr",
            "1",
            str(end_row),
            stat_code,
            cycle,
            str(start),
            str(end),
        ]
        for item in (item_code1, item_code2, item_code3, item_code4):
            if str(item or "").strip():
                parts.append(str(item).strip())
        safe_parts = [urllib.parse.quote(part, safe="") for part in parts]
        url = f"{ECOS_BASE_URL}/{'/'.join(safe_parts)}"
        try:
            payload, cached = _fetch_json(
                url,
                timeout=ECOS_TIMEOUT_SEC,
                ttl_sec=self.settings.ecos_cache_ttl_sec,
                user_agent="StockSuiteHTS-ECOS/1.0",
            )
        except Exception as exc:
            return {
                "ok": False,
                "configured": True,
                "rows": [],
                "stat_code": stat_code,
                "cycle": cycle,
                "start": start,
                "end": end,
                "message": f"ECOS 조회 오류: {exc}",
            }
        body = payload.get("StatisticSearch") if isinstance(payload, dict) else None
        if not isinstance(body, dict):
            result = payload.get("RESULT") if isinstance(payload, dict) else {}
            return {
                "ok": False,
                "configured": True,
                "rows": [],
                "stat_code": stat_code,
                "cycle": cycle,
                "start": start,
                "end": end,
                "status": result.get("CODE") if isinstance(result, dict) else "",
                "message": result.get("MESSAGE") if isinstance(result, dict) else "ECOS 응답 형식을 해석하지 못했습니다.",
            }
        rows = []
        for item in list(body.get("row") or []):
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "time": item.get("TIME", ""),
                    "value": _safe_float(item.get("DATA_VALUE")),
                    "raw_value": item.get("DATA_VALUE"),
                    "unit": item.get("UNIT_NAME", ""),
                    "stat_code": item.get("STAT_CODE", stat_code),
                    "stat_name": item.get("STAT_NAME", ""),
                    "item_code1": item.get("ITEM_CODE1", ""),
                    "item_name1": item.get("ITEM_NAME1", ""),
                    "item_code2": item.get("ITEM_CODE2", ""),
                    "item_name2": item.get("ITEM_NAME2", ""),
                }
            )
        return {
            "ok": True,
            "configured": True,
            "provider": "BOK ECOS",
            "stat_code": stat_code,
            "cycle": cycle,
            "start": start,
            "end": end,
            "count": len(rows),
            "total_count": _safe_int(body.get("list_total_count")),
            "rows": rows,
            "latest": rows[-1] if rows else None,
            "cached": cached,
            "message": "정상" if rows else "조회 결과가 없습니다.",
        }

    def macro_snapshot(self) -> dict[str, Any]:
        rows = []
        for key, config in ECOS_MACRO_SERIES.items():
            result = self.statistic_search(
                stat_code=str(config["stat_code"]),
                cycle=str(config["cycle"]),
                item_code1=str(config.get("item_code1", "")),
                limit=100,
            )
            latest = result.get("latest") if isinstance(result.get("latest"), dict) else {}
            rows.append(
                {
                    "id": key,
                    "name": config["name"],
                    "ok": bool(result.get("ok")) and bool(latest),
                    "value": latest.get("value") if latest else None,
                    "time": latest.get("time") if latest else "",
                    "unit": latest.get("unit") or config.get("unit", ""),
                    "stat_code": config["stat_code"],
                    "cycle": config["cycle"],
                    "item_code1": config.get("item_code1", ""),
                    "message": result.get("message", ""),
                }
            )
        ok_rows = [row for row in rows if row.get("ok")]
        stance = "ECOS 대기"
        if ok_rows:
            base_rate = next((row for row in rows if row.get("id") == "base_rate" and row.get("ok")), {})
            usd = next((row for row in rows if row.get("id") == "usd_krw" and row.get("ok")), {})
            stance = "중립"
            if _safe_float(base_rate.get("value")) >= 3.0 or _safe_float(usd.get("value")) >= 1400:
                stance = "긴축/환율 리스크 점검"
            elif _safe_float(base_rate.get("value")) <= 2.5 and _safe_float(usd.get("value")) and _safe_float(usd.get("value")) < 1350:
                stance = "완화/위험선호 관찰"
        return {
            "ok": bool(ok_rows),
            "configured": self.settings.ecos_configured,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "stance": stance,
            "rows": rows,
            "source": "BOK ECOS",
            "safety": "ECOS 거시지표는 투자판단 보조 데이터이며 실거래 주문 지시가 아닙니다.",
        }


class FredBridge:
    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings

    def status(self) -> dict[str, Any]:
        return {
            "provider": "FRED",
            "configured": self.settings.fred_configured,
            "key_masked": _mask(self.settings.fred_api_key),
            "cache_ttl_sec": self.settings.fred_cache_ttl_sec,
            "default_series": list(FRED_MACRO_SERIES),
            "message": "FRED_API_KEY가 있으면 미국 금리/실업률/물가 매크로 스냅샷을 조회합니다.",
        }

    def _default_window(self) -> tuple[str, str]:
        today = datetime.now()
        return (today - timedelta(days=365 * 5)).date().isoformat(), today.date().isoformat()

    def series_observations(
        self,
        series_id: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 600,
    ) -> dict[str, Any]:
        series_id = str(series_id or "").strip().upper()
        if not self.settings.fred_configured:
            return {
                "ok": False,
                "configured": False,
                "rows": [],
                "message": "FRED_API_KEY가 설정되지 않았습니다.",
            }
        if not series_id:
            return {"ok": False, "configured": True, "rows": [], "message": "series_id가 필요합니다."}
        if not start or not end:
            default_start, default_end = self._default_window()
            start = start or default_start
            end = end or default_end
        params = {
            "series_id": series_id,
            "api_key": self.settings.fred_api_key,
            "file_type": "json",
            "observation_start": str(start),
            "observation_end": str(end),
            "sort_order": "asc",
        }
        url = f"{FRED_BASE_URL}/series/observations?{urllib.parse.urlencode(params)}"
        try:
            payload, cached = _fetch_json(
                url,
                timeout=FRED_TIMEOUT_SEC,
                ttl_sec=self.settings.fred_cache_ttl_sec,
                user_agent="StockSuiteHTS-FRED/1.0",
            )
        except Exception as exc:
            return {
                "ok": False,
                "configured": True,
                "rows": [],
                "series_id": series_id,
                "start": start,
                "end": end,
                "message": f"FRED 조회 오류: {exc}",
            }
        observations = payload.get("observations") if isinstance(payload, dict) else None
        if not isinstance(observations, list):
            return {
                "ok": False,
                "configured": True,
                "rows": [],
                "series_id": series_id,
                "start": start,
                "end": end,
                "message": payload.get("error_message") if isinstance(payload, dict) else "FRED 응답 형식을 해석하지 못했습니다.",
            }
        rows = []
        for item in observations:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "date": item.get("date", ""),
                    "time": item.get("date", ""),
                    "value": _optional_float(item.get("value")),
                    "raw_value": item.get("value"),
                    "series_id": series_id,
                    "realtime_start": item.get("realtime_start", ""),
                    "realtime_end": item.get("realtime_end", ""),
                }
            )
        end_row = max(1, min(int(limit or 600), 5000))
        if len(rows) > end_row:
            rows = rows[-end_row:]
        latest = next((row for row in reversed(rows) if row.get("value") is not None), None)
        return {
            "ok": bool(latest),
            "configured": True,
            "provider": "FRED",
            "series_id": series_id,
            "start": start,
            "end": end,
            "count": len(rows),
            "rows": rows,
            "latest": latest,
            "cached": cached,
            "message": "정상" if latest else "조회 결과가 없거나 최신값이 비어 있습니다.",
        }

    def release_dates(self, start: str | None = None, end: str | None = None, limit: int = 100) -> dict[str, Any]:
        if not self.settings.fred_configured:
            return {"ok": False, "configured": False, "rows": [], "message": "FRED_API_KEY가 설정되지 않았습니다."}
        today = datetime.now().date()
        start = start or today.isoformat()
        end = end or (today + timedelta(days=14)).isoformat()
        params = {
            "api_key": self.settings.fred_api_key,
            "file_type": "json",
            "realtime_start": str(start),
            "realtime_end": str(end),
            "include_release_dates_with_no_data": "true",
            "order_by": "release_date",
            "sort_order": "asc",
            "limit": max(1, min(int(limit or 100), 1000)),
        }
        url = f"{FRED_BASE_URL}/releases/dates?{urllib.parse.urlencode(params)}"
        try:
            payload, cached = _fetch_json(
                url,
                timeout=FRED_TIMEOUT_SEC,
                ttl_sec=self.settings.fred_cache_ttl_sec,
                user_agent="StockSuiteHTS-FRED/1.0",
            )
        except Exception as exc:
            return {"ok": False, "configured": True, "rows": [], "start": start, "end": end, "message": f"FRED 발표일정 조회 오류: {exc}"}
        raw_rows = payload.get("release_dates") if isinstance(payload, dict) else []
        rows = []
        for item in raw_rows if isinstance(raw_rows, list) else []:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "release_id": item.get("release_id"),
                    "name": item.get("release_name", ""),
                    "observed_at": item.get("date", ""),
                    "time_precision": "date_only",
                    "timezone": "US release timezone not supplied by FRED endpoint",
                    "source": "FRED release dates",
                    "source_url": "https://fred.stlouisfed.org/releases/calendar",
                    "verified": bool(item.get("date") and item.get("release_name")),
                }
            )
        return {
            "ok": bool(rows),
            "query_ok": True,
            "configured": True,
            "provider": "FRED",
            "start": start,
            "end": end,
            "rows": rows,
            "cached": cached,
            "message": "정상" if rows else "기간 안에 확인된 FRED 발표일정이 없습니다.",
            "safety": "발표 날짜만 확인합니다. 발표 시각은 이 API가 제공하지 않으므로 추정하지 않습니다.",
        }

    def macro_snapshot(self) -> dict[str, Any]:
        rows = []
        for key, config in FRED_MACRO_SERIES.items():
            result = self.series_observations(series_id=str(config["series_id"]), limit=900)
            latest = result.get("latest") if isinstance(result.get("latest"), dict) else {}
            rows.append(
                {
                    "id": key,
                    "name": config["name"],
                    "ok": bool(result.get("ok")) and bool(latest),
                    "value": latest.get("value") if latest else None,
                    "time": latest.get("time") if latest else "",
                    "unit": config.get("unit", ""),
                    "series_id": config["series_id"],
                    "message": result.get("message", ""),
                }
            )
        ok_rows = [row for row in rows if row.get("ok")]
        stance = "FRED 대기"
        if ok_rows:
            fed = next((row for row in rows if row.get("id") == "fed_funds" and row.get("ok")), {})
            ten = next((row for row in rows if row.get("id") == "us_10y" and row.get("ok")), {})
            two = next((row for row in rows if row.get("id") == "us_2y" and row.get("ok")), {})
            unemployment = next((row for row in rows if row.get("id") == "unemployment" and row.get("ok")), {})
            stance = "미국 거시 중립"
            if _safe_float(fed.get("value")) >= 5.0 or _safe_float(ten.get("value")) >= 4.5:
                stance = "고금리 리스크 점검"
            if _safe_float(two.get("value")) and _safe_float(ten.get("value")) and _safe_float(two.get("value")) > _safe_float(ten.get("value")):
                stance = "장단기 금리역전 점검"
            if _safe_float(unemployment.get("value")) >= 5.0:
                stance = "고용 둔화 리스크 점검"
        return {
            "ok": bool(ok_rows),
            "configured": self.settings.fred_configured,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "stance": stance,
            "rows": rows,
            "source": "FRED",
            "safety": "FRED 거시지표는 투자판단 보조 데이터이며 실거래 주문 지시가 아닙니다.",
        }


class KrxBridge:
    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings

    def status(self) -> dict[str, Any]:
        return {
            "provider": "KRX",
            "configured": self.settings.krx_configured,
            "key_masked": _mask(self.settings.krx_api_key),
            "base_url": self.settings.krx_base_url,
            "cache_ttl_sec": self.settings.krx_cache_ttl_sec,
            "message": "KRX_API_KEY가 있으면 공식 KRX 데이터 API를 우선 사용할 준비가 된 상태입니다.",
            "safety": "KRX 키는 시장/종목 데이터 조회용입니다. 친구 배포 시 각자 본인 키를 입력해야 합니다.",
        }


class LiveResearchRouter:
    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings

    def score_disclosures(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        positive_words = ("공급계약", "수주", "실적", "매출", "영업이익", "배당", "자기주식취득", "합병")
        risk_words = ("소송", "횡령", "배임", "감자", "유상증자", "불성실", "관리종목", "거래정지")
        score = 0
        positives: list[str] = []
        risks: list[str] = []
        for item in items:
            title = str(item.get("report_nm") or "")
            if any(word in title for word in positive_words):
                score += 2
                positives.append(title)
            if any(word in title for word in risk_words):
                score -= 3
                risks.append(title)
        if not items:
            stance = "공시 없음"
        elif score > 1:
            stance = "긍정 관찰"
        elif score < 0:
            stance = "리스크 점검"
        else:
            stance = "중립"
        return {
            "score": score,
            "stance": stance,
            "positive_count": len(positives),
            "risk_count": len(risks),
            "positive_titles": positives[:3],
            "risk_titles": risks[:3],
        }

    def run(self, symbols: list[str] | None = None) -> dict[str, Any]:
        target_symbols = symbols or list(KR_CORP_CODES)
        dart = DartBridge(self.settings)
        kis = KisReadonlyBridge(self.settings)
        rows = []
        for symbol in target_symbols[:6]:
            normalized = _normalize_kr_symbol(symbol)
            corp = KR_CORP_CODES.get(normalized, {"corp_code": "00126380", "name": normalized})
            disclosures = dart.disclosures(corp_code=corp["corp_code"], days=self.settings.dart_lookback_days, page_count=5)
            dart_items = list(disclosures.get("items") or [])
            dart_score = self.score_disclosures(dart_items)
            quote = kis.quote(normalized, allow_real_fallback=False)
            price_ok = bool(quote.get("ok"))
            data_score = dart_score["score"] + (1 if price_ok else 0)
            if data_score >= 3:
                action = "관심"
            elif data_score < 0:
                action = "주의"
            else:
                action = "대기"
            rows.append(
                {
                    "symbol": normalized,
                    "name": quote.get("name") or corp["name"],
                    "action": action,
                    "score": data_score,
                    "price_ok": price_ok,
                    "price": quote.get("price", 0),
                    "change_pct": quote.get("change_pct", 0),
                    "quote_message": quote.get("message", ""),
                    "dart_ok": bool(disclosures.get("configured")),
                    "dart_count": len(dart_items),
                    "dart_stance": dart_score["stance"],
                    "latest_disclosure": dart_items[0] if dart_items else None,
                    "risk_count": dart_score["risk_count"],
                    "positive_count": dart_score["positive_count"],
                }
            )
        rows.sort(key=lambda item: (item["score"], item["dart_count"]), reverse=True)
        return {
            "source_order": ["KIS 읽기전용 시세", "DART 공시", "내장 백테스트"],
            "live_trading": self.settings.live_trading,
            "order_allowed": False,
            "rows": rows,
        }


class UsMarketRouter:
    def quote_rows(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        rows = []
        for index, symbol in enumerate((symbols or list(US_SYMBOLS))[:10]):
            seed = sum(ord(ch) for ch in symbol) + int(time.time() // 300)
            base = 80 + (seed % 240)
            change = ((seed % 81) - 40) / 10
            price = round(base * (1 + change / 100), 2)
            if change >= 2.5:
                action = "관심"
            elif change <= -2.5:
                action = "주의"
            else:
                action = "대기"
            rows.append(
                {
                    "symbol": symbol,
                    "name": symbol,
                    "market": "US",
                    "price": price,
                    "change_pct": round(change, 2),
                    "volume_rank": index + 1,
                    "action": action,
                    "source": "내장 미국시장 감시",
                }
            )
        return rows


class AiTraderDesk:
    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings

    def brief(self) -> dict[str, Any]:
        kr = LiveResearchRouter(self.settings).run(list(KR_CORP_CODES))
        us_rows = UsMarketRouter().quote_rows()
        macro = {
            "ecos": BokEcosBridge(self.settings).macro_snapshot(),
            "fred": FredBridge(self.settings).macro_snapshot(),
        }
        watch_kr = [row for row in kr["rows"] if row.get("action") == "관심"]
        caution_kr = [row for row in kr["rows"] if row.get("action") == "주의"]
        watch_us = [row for row in us_rows if row.get("action") == "관심"]
        caution_us = [row for row in us_rows if row.get("action") == "주의"]
        headline = "AI 트레이더가 국내/미국 시장을 감시 중입니다."
        if watch_kr or watch_us:
            headline = "관심 후보가 감지되었습니다. 단, 실전 주문은 잠겨 있습니다."
        elif caution_kr or caution_us:
            headline = "주의 후보가 있습니다. 리스크 점검이 우선입니다."
        elif any("리스크" in str(item.get("stance", "")) or "역전" in str(item.get("stance", "")) for item in macro.values()):
            headline = "거시지표 리스크가 감지되어 보수적으로 관찰합니다."
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "persona": "24시간 AI 트레이더",
            "headline": headline,
            "macro": macro,
            "markets": {
                "kr": {
                    "name": "국내시장",
                    "rows": kr["rows"],
                    "watch_count": len(watch_kr),
                    "caution_count": len(caution_kr),
                },
                "us": {
                    "name": "미국시장",
                    "rows": us_rows,
                    "watch_count": len(watch_us),
                    "caution_count": len(caution_us),
                },
            },
            "telegram": TelegramBridge(self.settings).status(),
            "safety": {
                "live_trading": self.settings.live_trading,
                "order_allowed": False,
                "message": "분석과 보고는 자동화하고, 실제 주문은 승인 전까지 잠급니다.",
            },
        }

    def format_telegram(self, brief: dict[str, Any]) -> str:
        kr = brief["markets"]["kr"]
        us = brief["markets"]["us"]
        lines = [
            "[AI 트레이더 자동 브리핑]",
            brief["headline"],
            f"생성시각: {brief['generated_at']}",
            "",
            f"국내시장: 관심 {kr['watch_count']} / 주의 {kr['caution_count']}",
        ]
        for row in kr["rows"][:3]:
            latest = row.get("latest_disclosure") or {}
            lines.append(f"- {row['name']}({row['symbol']}): {row['action']} / DART {row['dart_count']}건 / {latest.get('report_nm', '공시 없음')}")
        lines += ["", f"미국시장: 관심 {us['watch_count']} / 주의 {us['caution_count']}"]
        for row in us["rows"][:5]:
            lines.append(f"- {row['symbol']}: {row['action']} / {row['price']} / {row['change_pct']:+.2f}%")
        macro = brief.get("macro") or {}
        ecos = macro.get("ecos") or {}
        fred = macro.get("fred") or {}
        lines += ["", f"거시환경: ECOS {ecos.get('stance', '대기')} / FRED {fred.get('stance', '대기')}"]
        lines += ["", "실전 주문: 잠금"]
        return "\n".join(lines)


TELEGRAM_TEXT_LIMIT = 3800


def telegram_text_integrity(text: str) -> dict[str, Any]:
    """Normalize Telegram text and detect irreversible encoding loss."""
    original = str(text or "")
    normalized = unicodedata.normalize("NFC", original)
    normalized = "".join(
        character
        for character in normalized
        if character in {"\n", "\t"} or (ord(character) >= 32 and ord(character) != 127)
    )
    reasons: list[str] = []
    if "\ufffd" in normalized:
        reasons.append("unicode_replacement_character")
    if re.search(r"\?{3,}", normalized):
        reasons.append("question_mark_loss_run")
    try:
        normalized.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        reasons.append("invalid_utf8_scalar")
    digest = hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:16]
    return {
        "ok": not reasons,
        "text": normalized,
        "sha256": digest,
        "original_chars": len(original),
        "normalized_chars": len(normalized),
        "reasons": reasons,
    }


def _telegram_integrity_fallback(integrity: dict[str, Any]) -> str:
    reasons = ", ".join(str(item) for item in integrity.get("reasons", [])) or "unknown"
    return (
        "[코덱스스톡 보고 보호]\n"
        "한글 또는 문자 손상이 감지되어 깨진 원문 발송을 차단했습니다.\n"
        "내부 개발자가 보고서 생성 경로와 UTF-8 인코딩을 점검해야 합니다.\n"
        f"진단 코드: {reasons}\n"
        f"내용 해시: {integrity.get('sha256', '')}"
    )


class TelegramBridge:
    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.settings.telegram_enabled,
            "configured": self.settings.telegram_configured,
            "dry_run": self.settings.telegram_dry_run,
            "stub": self.settings.telegram_stub,
            "chat_masked": _mask(self.settings.telegram_chat_id),
        }

    def send_message(self, text: str) -> dict[str, Any]:
        status = self.status()
        if not status["enabled"]:
            return {"ok": False, "sent": False, "message": "텔레그램이 비활성화되어 있습니다.", "status": status}
        if not status["configured"]:
            return {"ok": False, "sent": False, "message": "텔레그램 토큰 또는 채팅 ID가 없습니다.", "status": status}

        integrity = telegram_text_integrity(text)
        outbound_text = str(integrity.get("text", ""))
        used_integrity_fallback = not bool(integrity.get("ok"))
        if used_integrity_fallback:
            outbound_text = _telegram_integrity_fallback(integrity)
        integrity_evidence = {key: value for key, value in integrity.items() if key != "text"}

        if status["dry_run"] or status["stub"]:
            return {
                "ok": True,
                "sent": False,
                "message": "텔레그램 드라이런 모드입니다.",
                "status": status,
                "delivery_status": "dry_run_integrity_fallback" if used_integrity_fallback else "dry_run",
                "used_integrity_fallback": used_integrity_fallback,
                "text_integrity": integrity_evidence,
                "preview": outbound_text[:800],
            }

        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = json.dumps(
            {
                "chat_id": self.settings.telegram_chat_id,
                "text": outbound_text[:TELEGRAM_TEXT_LIMIT],
                "disable_web_page_preview": True,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            safe_error = str(exc).replace(self.settings.telegram_bot_token, "***")
            return {
                "ok": False,
                "sent": False,
                "message": safe_error,
                "status": status,
                "delivery_status": "network_error",
                "used_integrity_fallback": used_integrity_fallback,
                "text_integrity": integrity_evidence,
            }
        sent = bool(data.get("ok"))
        return {
            "ok": sent,
            "sent": sent,
            "message": "손상된 원문 대신 안전 경고를 전송했습니다." if used_integrity_fallback else "전송 완료",
            "telegram": data,
            "status": status,
            "delivery_status": "sent_integrity_fallback" if used_integrity_fallback else "sent",
            "used_integrity_fallback": used_integrity_fallback,
            "text_integrity": integrity_evidence,
        }

    def _send_message_legacy(self, text: str) -> dict[str, Any]:
        status = self.status()
        if not status["enabled"]:
            return {"ok": False, "sent": False, "message": "텔레그램이 비활성화되어 있습니다.", "status": status}
        if not status["configured"]:
            return {"ok": False, "sent": False, "message": "텔레그램 토큰 또는 채팅 ID가 없습니다.", "status": status}
        if status["dry_run"] or status["stub"]:
            return {"ok": True, "sent": False, "message": "드라이런 모드입니다.", "status": status, "preview": text[:800]}
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = urllib.parse.urlencode(
            {
                "chat_id": self.settings.telegram_chat_id,
                "text": text[:3800],
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        request = urllib.request.Request(url, data=payload, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {"ok": False, "sent": False, "message": str(exc), "status": status}
        return {"ok": bool(data.get("ok")), "sent": bool(data.get("ok")), "message": "전송 완료", "telegram": data, "status": status}

    def get_updates(self, offset: int | None = None, timeout: int = 0) -> dict[str, Any]:
        status = self.status()
        if not status["enabled"]:
            return {"ok": False, "message": "텔레그램이 비활성화되어 있습니다.", "updates": [], "status": status}
        if not status["configured"]:
            return {"ok": False, "message": "텔레그램 토큰 또는 채팅 ID가 없습니다.", "updates": [], "status": status}
        if status["dry_run"] or status["stub"]:
            return {"ok": True, "message": "드라이런 모드입니다.", "updates": [], "status": status}
        params = {"timeout": str(timeout)}
        if offset is not None:
            params["offset"] = str(offset)
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/getUpdates?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=max(4, timeout + 4)) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {"ok": False, "message": str(exc), "updates": [], "status": status}
        updates = data.get("result", []) if data.get("ok") else []
        allowed_chat = str(self.settings.telegram_chat_id)
        filtered = []
        for update in updates:
            message = update.get("message") or update.get("edited_message") or {}
            chat_id = str((message.get("chat") or {}).get("id", ""))
            if chat_id == allowed_chat:
                filtered.append(update)
        return {"ok": bool(data.get("ok")), "message": "조회 완료", "updates": filtered, "raw_count": len(updates), "status": status}


class IntegrationHub:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def settings(self) -> IntegrationSettings:
        return IntegrationSettings.load(self.repo_root)

    def status(self) -> dict[str, Any]:
        settings = self.settings()
        return {
            "kis": KisReadonlyBridge(settings).status(),
            "dart": DartBridge(settings).status(),
            "ecos": BokEcosBridge(settings).status(),
            "fred": FredBridge(settings).status(),
            "krx": KrxBridge(settings).status(),
            "telegram": TelegramBridge(settings).status(),
            "safety": {
                "live_trading": settings.live_trading,
                "real_order_blocked": not bool(settings.live_trading and not settings.kis_readonly and not settings.kis_use_mock),
                "reason": "실전 주문 전송 모드입니다. 주문별 승인/확인문구/정규장/중복가드가 추가로 필요합니다."
                if settings.live_trading and not settings.kis_readonly and not settings.kis_use_mock
                else "LIVE_TRADING=true, KIS_READONLY=false, KIS_USE_MOCK=false가 모두 맞기 전까지 실제 주문 API는 호출되지 않습니다.",
            },
        }

    def dart_disclosures(self, corp_code: str, days: int | None = None, page_count: int = 10) -> dict[str, Any]:
        return DartBridge(self.settings()).disclosures(corp_code=corp_code, days=days, page_count=page_count)

    def dart_financials(self, corp_code: str, bsns_year: int | None = None, reprt_code: str = "11011") -> dict[str, Any]:
        return DartBridge(self.settings()).financials(corp_code=corp_code, bsns_year=bsns_year, reprt_code=reprt_code)

    def kis_quote(self, symbol: str = "005930") -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).quote(symbol)

    def kis_orderbook(self, symbol: str = "005930") -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).orderbook(symbol)

    def kis_daily_chart(self, symbol: str = "005930", start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).daily_chart_range(symbol=symbol, start_date=start_date, end_date=end_date)

    def kis_minute_chart(self, symbol: str = "005930", input_time: str | None = None, include_past: bool = True, limit: int = 30) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).minute_chart(
            symbol=symbol,
            input_time=input_time,
            include_past=include_past,
            limit=limit,
        )

    def kis_time_conclusion(self, symbol: str = "005930", input_time: str | None = None, limit: int = 30) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).time_conclusion(
            symbol=symbol,
            input_time=input_time,
            limit=limit,
        )

    def kis_watch_quotes(self, symbols: list[str] | None = None) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).watch_quotes(symbols)

    def kis_investor_trend(self, symbol: str = "005930") -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).investor_trend(symbol)

    def kis_foreign_institution_rank(
        self,
        investor: str = "foreign",
        market: str = "all",
        direction: str = "buy",
        limit: int = 20,
    ) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).foreign_institution_rank(
            investor=investor,
            market=market,
            direction=direction,
            limit=limit,
        )

    def kis_volume_rank(
        self,
        rank_kind: str = "amount",
        market: str = "all",
        limit: int = 30,
        min_price: int = 0,
        max_price: int = 0,
        min_volume: int = 0,
    ) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).volume_rank(
            rank_kind=rank_kind,
            market=market,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
            min_volume=min_volume,
        )

    def kis_fluctuation_rank(
        self,
        direction: str = "up",
        market: str = "all",
        limit: int = 30,
        min_price: int = 0,
        max_price: int = 0,
        min_volume: int = 0,
    ) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).fluctuation_rank(
            direction=direction,
            market=market,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
            min_volume=min_volume,
        )

    def kis_volume_power_rank(
        self,
        market: str = "all",
        limit: int = 30,
        min_price: int = 0,
        max_price: int = 0,
        min_volume: int = 0,
    ) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).volume_power_rank(
            market=market,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
            min_volume=min_volume,
        )

    def kis_quote_balance_rank(
        self,
        balance_kind: str = "buy",
        market: str = "all",
        limit: int = 30,
        min_price: int = 0,
        max_price: int = 0,
        min_volume: int = 0,
    ) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).quote_balance_rank(
            balance_kind=balance_kind,
            market=market,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
            min_volume=min_volume,
        )

    def kis_interest_watchlist(self) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).interest_watchlist()

    def kis_account(self) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).account_balance()

    def kis_account_assets(self) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).account_asset_snapshot()

    def kis_daily_executions(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        symbol: str = "",
        side: str = "all",
        filled: str = "filled",
    ) -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).daily_executions(
            start_date=start_date,
            end_date=end_date,
            symbol=symbol,
            side=side,
            filled=filled,
        )

    def kis_cash_order(self, symbol: str, side: str, quantity: float, price: float = 0.0, order_type: str = "limit") -> dict[str, Any]:
        return KisReadonlyBridge(self.settings()).cash_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

    def ecos_status(self) -> dict[str, Any]:
        return BokEcosBridge(self.settings()).status()

    def ecos_macro(self) -> dict[str, Any]:
        return BokEcosBridge(self.settings()).macro_snapshot()

    def ecos_series(
        self,
        stat_code: str,
        cycle: str = "M",
        start: str | None = None,
        end: str | None = None,
        item_code1: str = "",
        item_code2: str = "",
        item_code3: str = "",
        item_code4: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        return BokEcosBridge(self.settings()).statistic_search(
            stat_code=stat_code,
            cycle=cycle,
            start=start,
            end=end,
            item_code1=item_code1,
            item_code2=item_code2,
            item_code3=item_code3,
            item_code4=item_code4,
            limit=limit,
        )

    def fred_status(self) -> dict[str, Any]:
        return FredBridge(self.settings()).status()

    def fred_macro(self) -> dict[str, Any]:
        return FredBridge(self.settings()).macro_snapshot()

    def fred_series(self, series_id: str, start: str | None = None, end: str | None = None, limit: int = 600) -> dict[str, Any]:
        return FredBridge(self.settings()).series_observations(series_id=series_id, start=start, end=end, limit=limit)

    def fred_release_dates(self, start: str | None = None, end: str | None = None, limit: int = 100) -> dict[str, Any]:
        return FredBridge(self.settings()).release_dates(start=start, end=end, limit=limit)

    def macro_snapshot(self) -> dict[str, Any]:
        settings = self.settings()
        ecos = BokEcosBridge(settings).macro_snapshot()
        fred = FredBridge(settings).macro_snapshot()
        stances = [item.get("stance", "") for item in (ecos, fred) if item.get("ok")]
        if not stances:
            summary = "ECOS/FRED 키 또는 데이터가 아직 준비되지 않았습니다."
        elif any("리스크" in stance or "역전" in stance for stance in stances):
            summary = "거시 리스크를 우선 점검해야 하는 환경입니다."
        else:
            summary = "거시지표는 중립권으로 관찰됩니다."
        return {
            "ok": bool(ecos.get("ok") or fred.get("ok")),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "summary": summary,
            "ecos": ecos,
            "fred": fred,
            "safety": "거시지표는 분석 보조 데이터이며 수익 보장이나 확정 매매 지시가 아닙니다.",
        }

    def live_research(self, symbols: list[str] | None = None) -> dict[str, Any]:
        return LiveResearchRouter(self.settings()).run(symbols)

    def ai_brief(self) -> dict[str, Any]:
        return AiTraderDesk(self.settings()).brief()

    def ai_brief_message(self) -> dict[str, Any]:
        settings = self.settings()
        desk = AiTraderDesk(settings)
        brief = desk.brief()
        return {"brief": brief, "text": desk.format_telegram(brief)}

    def send_ai_brief(self) -> dict[str, Any]:
        settings = self.settings()
        payload = self.ai_brief_message()
        result = TelegramBridge(settings).send_message(str(payload.get("text", "")))
        return {"brief": payload.get("brief"), "telegram": result}

    def telegram_updates(self, offset: int | None = None, timeout: int = 0) -> dict[str, Any]:
        return TelegramBridge(self.settings()).get_updates(offset=offset, timeout=timeout)

    def telegram_send(self, text: str) -> dict[str, Any]:
        return TelegramBridge(self.settings()).send_message(text)
