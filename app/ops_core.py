from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from runtime_paths import USER_DATA_ENV_KEY, bootstrap_user_data_dir, configured_user_data_root
except ImportError:  # pragma: no cover - package import fallback
    from .runtime_paths import USER_DATA_ENV_KEY, bootstrap_user_data_dir, configured_user_data_root


@dataclass
class BacktestRiskGateConfig:
    min_trade_count: int = 8
    min_win_rate_pct: float = 42.0
    min_expectancy_pct: float = -0.2
    min_profit_factor: float = 1.05
    max_drawdown_pct: float = 35.0
    max_consecutive_losses: int = 6


def _infer_position_market(symbol: str) -> str:
    normalized = str(symbol or "").upper().strip()
    if re.fullmatch(r"\d{6}", normalized):
        return "KR"
    if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", normalized):
        return "US"
    return "UNKNOWN"


def _position_currency(market: str) -> str:
    if market == "KR":
        return "KRW"
    if market == "US":
        return "USD"
    return "UNKNOWN"


def _paper_currency_bucket(
    currency: str,
    cash_by_currency: dict[str, float],
    market_value_by_currency: dict[str, float],
    realized_by_currency: dict[str, float],
    unrealized_by_currency: dict[str, float],
    *,
    base_currency: str,
) -> dict[str, Any]:
    cash = float(cash_by_currency.get(currency, 0.0) or 0.0)
    market_value = float(market_value_by_currency.get(currency, 0.0) or 0.0)
    realized = float(realized_by_currency.get(currency, 0.0) or 0.0)
    unrealized = float(unrealized_by_currency.get(currency, 0.0) or 0.0)
    return {
        "currency": currency,
        "cash": round(cash, 2),
        "market_value": round(market_value, 2),
        "equity": round(cash + market_value, 2),
        "realized_pnl": round(realized, 2),
        "unrealized_pnl": round(unrealized, 2),
        "included_in_base_total": currency == base_currency,
    }


def _paper_position_valuation_guard(symbol: str, avg_cost: float, mark: float) -> dict[str, Any]:
    """Guard paper PnL from market/currency/price-scale mixups before aggregation."""
    market = _infer_position_market(symbol)
    currency = _position_currency(market)
    warnings: list[str] = []
    blocked = False
    price_ratio = 1.0
    if avg_cost > 0 and mark > 0:
        price_ratio = max(avg_cost, mark) / max(0.000001, min(avg_cost, mark))
    if mark <= 0:
        warnings.append("mark_price_missing")
        blocked = True
    if avg_cost <= 0:
        warnings.append("avg_cost_missing")
        blocked = True
    if market == "KR" and mark > 0 and mark < 500:
        warnings.append("kr_mark_below_500_review")
    if market == "KR" and avg_cost > 0 and avg_cost < 500:
        warnings.append("kr_avg_cost_below_500_review")
        warnings.append("kr_position_quarantined_until_price_repaired")
        blocked = True
    if market == "KR" and mark > 0 and mark < 500 and avg_cost >= 1000:
        warnings.append("kr_price_too_small_for_avg_cost")
        blocked = True
    if avg_cost > 0 and mark > 0 and price_ratio >= 20.0:
        warnings.append("avg_cost_mark_ratio_abnormal")
        blocked = True
    if market == "US":
        warnings.append("us_position_requires_fx_separated_valuation")
    if market == "UNKNOWN":
        warnings.append("unknown_market_symbol")
    applied_mark = avg_cost if blocked and avg_cost > 0 else mark
    risk_level = "blocked" if blocked else "watch" if warnings else "ok"
    return {
        "market": market,
        "currency": currency,
        "raw_mark": round(mark, 6),
        "applied_mark": round(applied_mark, 6),
        "price_ratio": round(price_ratio, 4),
        "risk_level": risk_level,
        "warnings": warnings,
        "valuation_note": (
            "Paper valuation used avg_cost instead of raw mark because price scale/currency looked inconsistent."
            if blocked
            else "US paper positions need separated FX-aware reporting." if market == "US"
            else "valuation_ok"
        ),
    }


def _order_ticket_price_anomaly(symbol: str, price: float) -> str:
    market = _infer_position_market(symbol)
    if price <= 0:
        return "ticket_price_missing"
    if market == "KR" and price < 500:
        return "kr_order_price_below_500_blocked"
    return ""


def _paper_ticket_price_anomaly(symbol: str, price: float) -> str:
    anomaly = _order_ticket_price_anomaly(symbol, price)
    if anomaly == "kr_order_price_below_500_blocked":
        return "kr_filled_ticket_price_below_500_quarantined"
    if anomaly == "ticket_price_missing":
        return anomaly
    return ""


def _order_quantity_notional_anomaly(symbol: str, quantity: float, price: float, max_order_amount: float = 0.0) -> str:
    market = _infer_position_market(symbol)
    if quantity <= 0 or price <= 0:
        return ""
    notional = quantity * price
    if market == "US":
        if quantity >= 500 and notional >= 100_000:
            return "us_quantity_looks_like_cash_amount"
        if quantity >= 100 and notional >= 25_000:
            return "us_large_quantity_requires_fx_aware_sizing"
    if market == "KR":
        if quantity >= 100_000 and notional >= 100_000_000:
            return "kr_quantity_notional_too_large_review"
        if max_order_amount > 0 and quantity >= max_order_amount and price >= 100:
            return "quantity_may_be_cash_amount"
    return ""


class HepiOpsCore:
    """헤피식 운영 안전장치를 우리 앱 데이터 구조로 재구현한 코어."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.default_data_dir = repo_root / "data" / "ops"
        self.user_data_env_key = USER_DATA_ENV_KEY
        self.user_data_root = configured_user_data_root()
        self.data_dir_source = "env" if self.user_data_root else "repo"
        self.data_dir = (self.user_data_root / "ops") if self.user_data_root else self.default_data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.user_data_root:
            bootstrap_user_data_dir(self.default_data_dir, self.data_dir)
        self.ticket_file = self.data_dir / "order_tickets.jsonl"
        self.approval_file = self.data_dir / "approvals.json"
        self.duplicate_file = self.data_dir / "live_duplicate_ledger.jsonl"
        self.audit_file = self.data_dir / "audit_log.jsonl"
        self.telegram_outbox_file = self.data_dir / "telegram_outbox.jsonl"
        self.telegram_dispatch_file = self.data_dir / "telegram_dispatch.jsonl"
        self.telegram_policy_file = self.data_dir / "telegram_policy.json"
        self._telegram_queue_lock = threading.Lock()
        self.kis_state_file = self.data_dir / "kis_state.json"
        self.risk_state_file = self.data_dir / "risk_state.json"
        self.autotrade_policy_file = self.data_dir / "autotrade_policy.json"
        self.shadow_signal_outbox = self.data_dir / "execution_sidecar" / "inbox"
        self.shadow_signal_secret_file = self.data_dir / "execution_sidecar" / "signal_secret"
        self.paper_start_cash = 100_000_000.0
        self.max_order_amount = 2_000_000.0
        self.max_daily_orders = 20
        self.gate_config = BacktestRiskGateConfig()

    def now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            clean = line.strip().lstrip("\ufeff")
            if not clean:
                continue
            try:
                item = json.loads(clean)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def _default_autotrade_policy(self) -> dict[str, Any]:
        return {
            "paper_autopilot_enabled": True,
            "live_candidate_enabled": True,
            "live_execution_enabled": False,
            "live_pilot_enabled": False,
            "live_execution_control_mode": "manual_approval",
            "require_approval": True,
            "emergency_halt": False,
            "buy_blocked": False,
            "day_halted": False,
            "max_order_amount": self.max_order_amount,
            "live_pilot_sizing_mode": "single_share",
            "live_pilot_max_cash_pct": 10.0,
            "live_pilot_dynamic_sizing_enabled": True,
            "live_pilot_dynamic_min_cash_pct": 0.0,
            "live_pilot_dynamic_max_cash_pct": 50.0,
            "live_pilot_max_quantity": 1,
            "live_pilot_max_notional": 300_000.0,
            "live_pilot_approval_ttl_minutes": 180,
            "live_pilot_allowed_symbols": [],
            "live_pilot_confirm_phrase": "1주 파일럿 승인",
            "delegated_live_autonomy_enabled": False,
            "delegated_live_authorization_confirmed": False,
            "delegated_live_authorized_date": "",
            "delegated_live_authorized_at": "",
            "delegated_live_authorization_source": "",
            "delegated_live_authorization_scope": "",
            "delegated_live_authorization_mode": "daily",
            "delegated_live_auto_submit_max_cash_pct": 30.0,
            "delegated_live_user_approval_above_cash_pct": 50.0,
            "delegated_live_min_buy_symbols_per_day": 1,
            "delegated_live_max_position_cash_pct": 30.0,
            "delegated_live_max_buy_orders_per_day": 1,
            "delegated_live_max_sell_orders_per_day": 1,
            "delegated_live_reentry_cooldown_minutes": 90,
            "delegated_live_stop_loss_pct": 2.0,
            "delegated_live_take_profit_pct": 3.0,
            "delegated_live_profit_partial_exit_pct": 50.0,
            "delegated_live_profit_trailing_drawdown_pct": 1.0,
            "max_daily_orders": self.max_daily_orders,
            "max_position_pct": 10.0,
            "max_daily_loss_pct": 2.0,
            "min_paper_rehearsals_before_live": 20,
            "min_readiness_score_for_live": 90,
            "allowed_markets": ["KR", "US"],
            "updated_at": "",
            "memo": "기본값: paper 자동운영 ON, 실전 주문 실행 OFF",
        }

    def autotrade_policy(self) -> dict[str, Any]:
        policy = self._default_autotrade_policy()
        saved = self._read_json(self.autotrade_policy_file, {})
        saved_has_control_mode = isinstance(saved, dict) and "live_execution_control_mode" in saved
        if isinstance(saved, dict):
            policy.update(saved)
        mode = str(policy.get("live_execution_control_mode") or "").strip().lower()
        if not saved_has_control_mode or mode not in {"manual_approval", "delegated_auto"}:
            mode = "delegated_auto" if (
                bool(policy.get("delegated_live_autonomy_enabled"))
                and not bool(policy.get("require_approval", True))
            ) else "manual_approval"
        policy["live_execution_control_mode"] = mode
        policy["require_approval"] = mode == "manual_approval"
        policy["delegated_live_autonomy_enabled"] = mode == "delegated_auto"
        risk_state = self._read_json(self.risk_state_file, {})
        if isinstance(risk_state, dict):
            for key in ("emergency_halt", "buy_blocked", "day_halted"):
                if key in risk_state:
                    policy[key] = bool(risk_state.get(key))
            if risk_state.get("memo"):
                policy["memo"] = risk_state.get("memo")
        return policy

    def save_autotrade_policy(self, patch: dict[str, Any]) -> dict[str, Any]:
        policy = self.autotrade_policy()
        bool_keys = {
            "paper_autopilot_enabled",
            "live_candidate_enabled",
            "live_execution_enabled",
            "live_pilot_enabled",
            "delegated_live_autonomy_enabled",
            "delegated_live_authorization_confirmed",
            "live_pilot_dynamic_sizing_enabled",
            "require_approval",
            "emergency_halt",
            "buy_blocked",
            "day_halted",
        }
        float_ranges = {
            "max_order_amount": (10_000.0, 100_000_000.0),
            "live_pilot_max_notional": (1_000.0, 5_000_000.0),
            "live_pilot_max_cash_pct": (0.1, 100.0),
            "live_pilot_dynamic_min_cash_pct": (0.0, 100.0),
            "live_pilot_dynamic_max_cash_pct": (0.1, 100.0),
            "delegated_live_stop_loss_pct": (0.1, 30.0),
            "delegated_live_take_profit_pct": (0.1, 100.0),
            "delegated_live_profit_partial_exit_pct": (1.0, 100.0),
            "delegated_live_profit_trailing_drawdown_pct": (0.1, 20.0),
            "delegated_live_auto_submit_max_cash_pct": (0.1, 100.0),
            "delegated_live_user_approval_above_cash_pct": (0.1, 100.0),
            "delegated_live_max_position_cash_pct": (0.1, 100.0),
            "max_position_pct": (0.1, 100.0),
            "max_daily_loss_pct": (0.1, 50.0),
        }
        int_ranges = {
            "max_daily_orders": (1, 300),
            "live_pilot_max_quantity": (1, 10_000),
            "live_pilot_approval_ttl_minutes": (5, 390),
            "delegated_live_max_buy_orders_per_day": (0, 20),
            "delegated_live_min_buy_symbols_per_day": (1, 20),
            "delegated_live_max_sell_orders_per_day": (0, 20),
            "delegated_live_reentry_cooldown_minutes": (0, 1440),
            "min_paper_rehearsals_before_live": (0, 1000),
            "min_readiness_score_for_live": (0, 100),
        }
        for key, value in patch.items():
            if key in bool_keys:
                policy[key] = bool(value)
            elif key in float_ranges:
                lower, upper = float_ranges[key]
                policy[key] = max(lower, min(float(value), upper))
            elif key in int_ranges:
                lower, upper = int_ranges[key]
                policy[key] = max(lower, min(int(value), upper))
            elif key == "allowed_markets" and isinstance(value, list):
                policy[key] = [str(item).upper() for item in value if str(item).upper() in {"KR", "US", "COIN"}]
            elif key == "live_pilot_allowed_symbols" and isinstance(value, list):
                policy[key] = [str(item).upper().strip()[:16] for item in value if str(item).strip()]
            elif key == "live_pilot_confirm_phrase":
                policy[key] = str(value).strip()[:80] or "1주 파일럿 승인"
            elif key in {
                "delegated_live_authorized_date",
                "delegated_live_authorized_at",
                "delegated_live_authorization_source",
                "delegated_live_authorization_scope",
            }:
                policy[key] = str(value).strip()[:200]
            elif key == "delegated_live_authorization_mode":
                mode = str(value).strip().lower()
                if mode not in {"daily", "standing"}:
                    raise ValueError("invalid_delegated_authorization_mode")
                policy[key] = mode
            elif key == "live_pilot_sizing_mode":
                mode = str(value).strip().lower()
                policy[key] = mode if mode in {"single_share", "cash_pct"} else "single_share"
            elif key == "live_execution_control_mode":
                mode = str(value).strip().lower()
                if mode not in {"manual_approval", "delegated_auto"}:
                    raise ValueError("invalid_live_execution_control_mode")
                policy[key] = mode
            elif key == "memo":
                policy[key] = str(value)[:500]
        if "live_execution_control_mode" in patch:
            delegated = policy["live_execution_control_mode"] == "delegated_auto"
            policy["delegated_live_autonomy_enabled"] = delegated
            policy["require_approval"] = not delegated
            policy["delegated_live_authorization_mode"] = "standing" if delegated else "daily"
        elif "delegated_live_autonomy_enabled" in patch or "require_approval" in patch:
            delegated = bool(policy.get("delegated_live_autonomy_enabled")) and not bool(
                policy.get("require_approval", True)
            )
            policy["live_execution_control_mode"] = "delegated_auto" if delegated else "manual_approval"
            policy["delegated_live_autonomy_enabled"] = delegated
            policy["require_approval"] = not delegated
        if not bool(policy.get("delegated_live_autonomy_enabled")):
            policy["delegated_live_authorization_confirmed"] = False
            policy["delegated_live_authorized_date"] = ""
            policy["delegated_live_authorized_at"] = ""
            policy["delegated_live_authorization_source"] = ""
            policy["delegated_live_authorization_scope"] = ""
        policy["updated_at"] = self.now()
        self._write_json(self.autotrade_policy_file, policy)
        self._write_json(
            self.risk_state_file,
            {
                "emergency_halt": bool(policy.get("emergency_halt")),
                "buy_blocked": bool(policy.get("buy_blocked")),
                "day_halted": bool(policy.get("day_halted")),
                "memo": str(policy.get("memo", "")),
                "updated_at": policy["updated_at"],
            },
        )
        self.audit("AUTOTRADE_POLICY_UPDATED", "자동매매 운영 정책을 업데이트했습니다.", {"policy": policy})
        return policy

    def set_emergency_halt(self, enabled: bool, memo: str = "") -> dict[str, Any]:
        patch = {
            "emergency_halt": bool(enabled),
            "day_halted": bool(enabled),
            "buy_blocked": bool(enabled),
            "memo": memo or ("긴급정지 ON" if enabled else "긴급정지 해제"),
        }
        policy = self.save_autotrade_policy(patch)
        self.audit("EMERGENCY_HALT_ON" if enabled else "EMERGENCY_HALT_OFF", str(patch["memo"]), {"policy": policy})
        return policy

    def audit(self, action: str, message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        record = {
            "id": f"AUD-{int(time.time() * 1000)}",
            "created_at": self.now(),
            "action": action,
            "message": message,
            "payload": payload or {},
        }
        self._append_jsonl(self.audit_file, record)
        return record

    def audit_log(self, limit: int = 80) -> list[dict[str, Any]]:
        return list(reversed(self._read_jsonl(self.audit_file)[-limit:]))

    def tickets(self, limit: int | None = None) -> list[dict[str, Any]]:
        rows = self._read_jsonl(self.ticket_file)
        return rows[-limit:] if limit else rows

    def order_symbols(self) -> list[str]:
        symbols = {str(row.get("symbol", "")).upper() for row in self.tickets() if row.get("symbol")}
        return sorted(symbol for symbol in symbols if symbol)

    def approvals(self) -> list[dict[str, Any]]:
        rows = self._read_json(self.approval_file, [])
        return rows if isinstance(rows, list) else []

    def _save_approvals(self, rows: list[dict[str, Any]]) -> None:
        self._write_json(self.approval_file, rows)

    def _risk_state(self) -> dict[str, Any]:
        state = self._read_json(self.risk_state_file, {})
        if not isinstance(state, dict):
            state = {}
        saved_policy = self._read_json(self.autotrade_policy_file, {})
        if isinstance(saved_policy, dict):
            for key in ("emergency_halt", "buy_blocked", "day_halted"):
                if key in saved_policy:
                    state[key] = bool(saved_policy.get(key))
            if saved_policy.get("memo") and not state.get("memo"):
                state["memo"] = saved_policy.get("memo")
        state.setdefault("emergency_halt", False)
        state.setdefault("buy_blocked", False)
        state.setdefault("day_halted", False)
        state.setdefault("memo", "기본값: 매수 가능, 당일 정지 아님")
        return state

    def duplicate_fingerprints(self) -> set[str]:
        return {str(row.get("fingerprint", "")) for row in self._read_jsonl(self.duplicate_file) if row.get("fingerprint")}

    def _fingerprint(self, ticket: dict[str, Any]) -> str:
        raw = "|".join(
            [
                str(ticket.get("symbol", "")).upper(),
                str(ticket.get("side", "")).upper(),
                str(ticket.get("quantity", "")),
                str(ticket.get("price", "")),
                self._today(),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    def _daily_order_count(self) -> int:
        today = self._today()
        active_statuses = {"PAPER_FILLED", "APPROVAL_REQUIRED", "LIVE_READY_NOT_SUBMITTED", "LIVE_SUBMITTED"}
        return sum(
            1
            for row in self.tickets()
            if str(row.get("created_at", "")).startswith(today)
            and str(row.get("status", "")) in active_statuses
        )

    def has_today_ticket(self, symbol: str, side: str = "BUY", mode: str = "paper", source: str | None = None) -> bool:
        today = self._today()
        normalized = symbol.upper().strip()
        normalized_side = side.upper().strip()
        for row in self.tickets():
            if not str(row.get("created_at", "")).startswith(today):
                continue
            if str(row.get("symbol", "")).upper() != normalized:
                continue
            if str(row.get("side", "")).upper() != normalized_side:
                continue
            if str(row.get("mode", "")) != mode:
                continue
            if source is not None and str(row.get("source", "")) != source:
                continue
            if row.get("status") in {"PAPER_FILLED", "APPROVAL_REQUIRED", "LIVE_READY_NOT_SUBMITTED"}:
                return True
        return False

    def _paper_position_quantity(self, symbol: str) -> float:
        summary = self.paper_summary()
        for item in summary["positions"]:
            if item["symbol"] == symbol.upper():
                return float(item["quantity"])
        return 0.0

    def risk_checks(self, ticket: dict[str, Any]) -> list[dict[str, Any]]:
        side = str(ticket.get("side", "")).upper()
        mode = str(ticket.get("mode", "paper"))
        symbol = str(ticket.get("symbol", "")).upper()
        quantity = float(ticket.get("quantity", 0) or 0)
        price = float(ticket.get("price", 0) or 0)
        notional = quantity * price
        price_anomaly = _order_ticket_price_anomaly(symbol, price)
        risk_state = self._risk_state()
        policy = self.autotrade_policy()
        max_order_amount = float(policy.get("max_order_amount", self.max_order_amount) or self.max_order_amount)
        quantity_anomaly = _order_quantity_notional_anomaly(symbol, quantity, price, max_order_amount)
        max_daily_orders = int(policy.get("max_daily_orders", self.max_daily_orders) or self.max_daily_orders)
        max_position_pct = float(policy.get("max_position_pct", 10.0) or 10.0)
        max_daily_loss_pct = float(policy.get("max_daily_loss_pct", 2.0) or 2.0)
        paper = self.paper_summary()
        current_position_value = 0.0
        for position in paper.get("positions", []):
            if isinstance(position, dict) and str(position.get("symbol", "")).upper() == symbol:
                current_position_value = float(position.get("value", 0) or 0)
                break
        next_position_pct = ((current_position_value + notional) / self.paper_start_cash) * 100.0 if self.paper_start_cash else 0.0
        paper_pnl_pct = float(paper.get("total_pnl_pct", 0) or 0)
        fingerprint = self._fingerprint(ticket)
        duplicate_seen = fingerprint in self.duplicate_fingerprints()
        checks = [
            {"name": "valid_symbol", "ok": bool(symbol), "detail": "종목코드가 있어야 합니다."},
            {"name": "valid_side", "ok": side in {"BUY", "SELL"}, "detail": "BUY 또는 SELL만 허용합니다."},
            {"name": "valid_quantity", "ok": quantity > 0, "detail": "수량은 0보다 커야 합니다."},
            {"name": "valid_price", "ok": price > 0, "detail": "가격은 0보다 커야 합니다."},
            {
                "name": "max_order_amount",
                "ok": notional <= max_order_amount,
                "detail": f"주문금액 {notional:,.0f} / 한도 {max_order_amount:,.0f}",
            },
            {
                "name": "daily_order_limit",
                "ok": self._daily_order_count() < max_daily_orders,
                "detail": f"오늘 주문티켓 {self._daily_order_count()} / 한도 {max_daily_orders}",
            },
            {
                "name": "max_position_pct",
                "ok": side != "BUY" or next_position_pct <= max_position_pct,
                "detail": f"예상 종목비중 {next_position_pct:.2f}% / 한도 {max_position_pct:.2f}%",
            },
            {
                "name": "daily_loss_limit",
                "ok": paper_pnl_pct > -abs(max_daily_loss_pct),
                "detail": f"paper 총손익 {paper_pnl_pct:.2f}% / 손실정지 {-abs(max_daily_loss_pct):.2f}%",
            },
            {
                "name": "emergency_halt_off",
                "ok": not bool(risk_state.get("emergency_halt")),
                "detail": "긴급정지가 켜져 있으면 모든 주문 후보를 막습니다.",
            },
            {
                "name": "buy_not_blocked",
                "ok": not (side == "BUY" and bool(risk_state.get("buy_blocked"))),
                "detail": "운영 상태가 매수 차단이면 BUY를 막습니다.",
            },
            {
                "name": "day_not_halted",
                "ok": not bool(risk_state.get("day_halted")),
                "detail": "당일 중지 상태면 모든 주문 후보를 막습니다.",
            },
        ]
        checks.append(
            {
                "name": "order_price_integrity",
                "ok": not price_anomaly,
                "detail": price_anomaly or "price_scale_ok",
            }
        )
        checks.append(
            {
                "name": "order_quantity_integrity",
                "ok": not quantity_anomaly,
                "detail": quantity_anomaly or "quantity_notional_ok",
            }
        )
        if mode == "paper" and side == "SELL":
            held = self._paper_position_quantity(symbol)
            checks.append(
                {
                    "name": "paper_sell_has_position",
                    "ok": held >= quantity,
                    "detail": f"보유 {held:,.4f} / 매도요청 {quantity:,.4f}",
                }
            )
        if mode == "paper":
            checks.append(
                {
                    "name": "paper_autopilot_enabled",
                    "ok": bool(policy.get("paper_autopilot_enabled", True)),
                    "detail": "paper 자동운영이 꺼져 있으면 paper 후보도 막습니다.",
                }
            )
        if mode.startswith("live"):
            checks.append(
                {
                    "name": "live_candidate_enabled",
                    "ok": bool(policy.get("live_candidate_enabled", True)),
                    "detail": "실전 후보 생성 스위치가 켜져 있어야 합니다.",
                }
            )
            checks.append(
                {
                    "name": "approval_required",
                    "ok": bool(
                        isinstance(ticket.get("metadata"), dict)
                        and ticket["metadata"].get("shadow_validation_only") is True
                    ) or str(policy.get("live_execution_control_mode") or "manual_approval")
                    in {"manual_approval", "delegated_auto"},
                    "detail": (
                        "반자동은 승인 게이트, 완전자동은 서명된 외부 실행기 신호 게이트를 거칩니다."
                    ),
                }
            )
            checks.append(
                {
                    "name": "duplicate_order_not_seen",
                    "ok": not duplicate_seen,
                    "detail": f"fingerprint {fingerprint}",
                }
            )
        return checks

    def create_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        mode: str = "paper",
        source: str = "web",
        request_approval: bool = False,
        memo: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_mode = "live_candidate" if mode in {"live", "live_candidate"} else "paper"
        shadow_validation_only = bool(
            normalized_mode == "live_candidate"
            and isinstance(metadata, dict)
            and metadata.get("shadow_validation_only") is True
        )
        ticket: dict[str, Any] = {
            "id": f"TIC-{int(time.time() * 1000)}",
            "created_at": self.now(),
            "symbol": symbol.upper().strip(),
            "side": side.upper().strip(),
            "quantity": round(float(quantity), 6),
            "price": round(float(price), 4),
            "notional": round(float(quantity) * float(price), 2),
            "mode": normalized_mode,
            "source": source,
            "memo": memo,
            "real_execution": "BLOCKED",
        }
        if isinstance(metadata, dict) and metadata:
            ticket["metadata"] = metadata
        ticket["fingerprint"] = self._fingerprint(ticket)
        checks = self.risk_checks(ticket)
        passed = all(bool(item["ok"]) for item in checks)
        ticket["risk_checks"] = checks
        ticket["risk_status"] = "PASSED" if passed else "BLOCKED"
        if normalized_mode == "paper":
            ticket["status"] = "PAPER_FILLED" if passed else "PAPER_BLOCKED"
            ticket["guard"] = "paper_only_no_broker_order"
        else:
            if shadow_validation_only:
                ticket["guard"] = "shadow_validation_only_no_approval_no_broker_order"
                ticket["status"] = "SHADOW_VALIDATION_READY" if passed else "LIVE_CANDIDATE_BLOCKED"
            elif passed and not bool(self.autotrade_policy().get("require_approval", True)):
                ticket["guard"] = "delegated_signed_signal_external_executor"
                ticket["status"] = "DELEGATED_SIGNAL_READY"
            else:
                ticket["guard"] = "live_order_not_implemented_and_requires_approval"
                ticket["status"] = "APPROVAL_REQUIRED" if passed else "LIVE_CANDIDATE_BLOCKED"
            if (
                passed
                and not shadow_validation_only
                and (request_approval or bool(self.autotrade_policy().get("require_approval", True)))
            ):
                approval = self.create_approval(ticket)
                ticket["approval_token"] = approval["token"]
                ticket["approval_status"] = approval["status"]
        if (
            bool(self.telegram_policy().get("trade_reason_reports_enabled", True))
            and ticket.get("status") in {"PAPER_FILLED", "APPROVAL_REQUIRED", "DELEGATED_SIGNAL_READY"}
        ):
            side_label = "매수" if ticket["side"] == "BUY" else "매도"
            mode_label = "모의투자" if normalized_mode == "paper" else "실전 후보"
            reason = memo or f"{source} 출처의 자동/수동 티켓"
            text = "\n".join(
                [
                    "[매매 사유 기록]",
                    f"{ticket['symbol']} {side_label} {ticket['quantity']:g}주 @ {ticket['price']:,.2f}",
                    f"구분: {mode_label} / 상태: {ticket['status']}",
                    f"이유: {reason}",
                    f"위험게이트: {ticket['risk_status']} / 실전주문: {ticket['real_execution']}",
                ]
            )
            report = self.queue_telegram(
                text=text,
                message_type="trade_reason",
                source="order-ticket",
                metadata={"ticket_id": ticket["id"], "symbol": ticket["symbol"], "side": ticket["side"], "mode": normalized_mode},
            )
            ticket["telegram_trade_reason"] = {
                "queued": bool(report.get("queued")),
                "id": report.get("id"),
                "status": report.get("status"),
                "reason": (report.get("policy") or {}).get("reason") if isinstance(report.get("policy"), dict) else "",
            }
        if normalized_mode == "live_candidate" and passed:
            try:
                from stock_suite.signal_bridge import ShadowSignalPublisher

                ticket["shadow_signal"] = ShadowSignalPublisher(
                    self.shadow_signal_outbox,
                    self.shadow_signal_secret_file,
                ).publish(ticket)
            except Exception as exc:
                ticket["shadow_signal"] = {
                    "published": False,
                    "reason": "shadow_signal_publish_failed",
                    "error": f"{type(exc).__name__}: {exc}"[:500],
                }
        self._append_jsonl(self.ticket_file, ticket)
        self.audit(
            "ORDER_TICKET",
            f"{ticket['symbol']} {ticket['side']} {ticket['mode']} 티켓 {ticket['status']}",
            {"ticket": ticket},
        )
        return ticket

    def create_approval(self, ticket: dict[str, Any], ttl_minutes: int | None = None) -> dict[str, Any]:
        if ttl_minutes is None:
            policy = self.autotrade_policy()
            ttl_minutes = int(policy.get("live_pilot_approval_ttl_minutes", 180) or 180)
        ttl_minutes = max(5, min(int(ttl_minutes or 180), 390))
        token_seed = f"{ticket.get('id')}:{time.time()}"
        token = "APP-" + hashlib.sha256(token_seed.encode("utf-8")).hexdigest()[:16].upper()
        approval = {
            "token": token,
            "created_at": self.now(),
            "expires_at": (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds"),
            "status": "pending",
            "action": "real_stock_order",
            "ticket": ticket,
            "resolution": "",
        }
        rows = self.approvals()
        rows.append(approval)
        self._save_approvals(rows)
        self.audit("APPROVAL_CREATED", f"{ticket.get('symbol')} 실전 주문 후보 승인 요청", {"token": token})
        return approval

    def resolve_approval(self, token: str, approved: bool, memo: str = "") -> dict[str, Any]:
        rows = self.approvals()
        for row in rows:
            if row.get("token") != token:
                continue
            if row.get("status") != "pending":
                raise ValueError("이미 처리된 승인 토큰입니다.")
            expires_at = str(row.get("expires_at", "")).strip()
            if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
                raise ValueError("만료된 승인 토큰입니다. 새 실전 후보를 생성해주세요.")
            row["status"] = "approved" if approved else "rejected"
            row["resolved_at"] = self.now()
            row["resolution"] = memo
            self._save_approvals(rows)
            self.audit("APPROVAL_RESOLVED", f"승인 {row['status']}: {token}", {"approval": row})
            return row
        raise ValueError("승인 토큰을 찾을 수 없습니다.")

    def live_dry_submit(self, token: str) -> dict[str, Any]:
        approval = next((row for row in self.approvals() if row.get("token") == token), None)
        if not approval:
            raise ValueError("승인 토큰을 찾을 수 없습니다.")
        expires_at = str(approval.get("expires_at", "")).strip()
        if expires_at and datetime.fromisoformat(expires_at) < datetime.now():
            raise ValueError("만료된 승인 토큰입니다. 새 실전 후보를 생성해주세요.")
        ticket = dict(approval.get("ticket") or {})
        ticket["approval_token"] = token
        checks = self.risk_checks(ticket)
        checks.append(
            {
                "name": "approval_token_approved",
                "ok": approval.get("status") == "approved",
                "detail": f"approval status {approval.get('status')}",
            }
        )
        passed = all(bool(item["ok"]) for item in checks)
        fingerprint = self._fingerprint(ticket)
        duplicate_seen = fingerprint in self.duplicate_fingerprints()
        if duplicate_seen:
            passed = False
        result = {
            "created_at": self.now(),
            "status": "LIVE_READY_NOT_SUBMITTED" if passed else ("LIVE_DRY_SUBMIT_DUPLICATE_BLOCKED" if duplicate_seen else "LIVE_DRY_SUBMIT_BLOCKED"),
            "real_execution": "BLOCKED",
            "message": "실전 주문은 아직 보내지 않습니다. 준비상태와 중복가드만 검증했습니다.",
            "approval": approval,
            "ticket": ticket,
            "risk_checks": checks,
            "duplicate_fingerprint": fingerprint,
        }
        if passed:
            self._append_jsonl(self.duplicate_file, {"created_at": self.now(), "fingerprint": fingerprint, "ticket": ticket})
        self._append_jsonl(self.data_dir / "live_dry_submits.jsonl", result)
        self.audit("LIVE_DRY_SUBMIT", result["status"], {"token": token, "fingerprint": fingerprint})
        return result

    def paper_summary(self, marks: dict[str, float] | None = None) -> dict[str, Any]:
        marks = marks or {}
        base_currency = "KRW"
        cash_by_currency: dict[str, float] = {base_currency: self.paper_start_cash}
        realized_by_currency: dict[str, float] = {}
        positions: dict[str, dict[str, float]] = {}
        ledger_quarantined_tickets: list[dict[str, Any]] = []
        filled = [row for row in self.tickets() if row.get("mode") == "paper" and row.get("status") == "PAPER_FILLED"]
        for row in filled:
            symbol = str(row.get("symbol", "")).upper()
            side = str(row.get("side", "")).upper()
            qty = float(row.get("quantity", 0) or 0)
            price = float(row.get("price", 0) or 0)
            currency = _position_currency(_infer_position_market(symbol))
            cash_by_currency.setdefault(currency, 0.0)
            realized_by_currency.setdefault(currency, 0.0)
            ticket_anomalies = [
                item
                for item in (
                    _paper_ticket_price_anomaly(symbol, price),
                    _order_quantity_notional_anomaly(symbol, qty, price, self.max_order_amount),
                )
                if item
            ]
            if ticket_anomalies:
                ledger_quarantined_tickets.append(
                    {
                        "id": row.get("id"),
                        "created_at": row.get("created_at"),
                        "symbol": symbol,
                        "side": side,
                        "quantity": qty,
                        "price": price,
                        "source": row.get("source"),
                        "reason": ",".join(ticket_anomalies),
                        "reasons": ticket_anomalies,
                    }
                )
                continue
            fee = max(1.0, qty * price * 0.0005)
            pos = positions.setdefault(symbol, {"quantity": 0.0, "cost": 0.0})
            if side == "BUY":
                pos["quantity"] += qty
                pos["cost"] += qty * price
                cash_by_currency[currency] -= qty * price + fee
            elif side == "SELL" and pos["quantity"] > 0:
                sell_qty = min(qty, pos["quantity"])
                avg_cost = pos["cost"] / pos["quantity"] if pos["quantity"] else 0.0
                realized_by_currency[currency] += (price - avg_cost) * sell_qty - fee
                pos["quantity"] -= sell_qty
                pos["cost"] = max(0.0, pos["cost"] - avg_cost * sell_qty)
                cash_by_currency[currency] += price * sell_qty - fee
        position_rows = []
        market_value = 0.0
        unrealized = 0.0
        market_value_by_currency: dict[str, float] = {}
        unrealized_by_currency: dict[str, float] = {}
        quarantined_value_by_currency: dict[str, float] = {}
        quarantined_symbols_by_currency: dict[str, list[str]] = {}
        valuation_warnings: list[dict[str, Any]] = []
        valuation_neutralized_symbols: list[str] = []
        excluded_from_base_total: list[str] = []
        for symbol, pos in sorted(positions.items()):
            qty = pos["quantity"]
            if qty <= 0:
                continue
            avg_cost = pos["cost"] / qty if qty else 0.0
            raw_mark = float(marks.get(symbol, avg_cost) or avg_cost)
            guard = _paper_position_valuation_guard(symbol, avg_cost, raw_mark)
            currency = str(guard.get("currency") or "UNKNOWN")
            mark = float(guard.get("applied_mark", raw_mark) or raw_mark)
            if guard.get("risk_level") in {"blocked", "watch"}:
                valuation_warnings.append(
                    {
                        "symbol": symbol,
                        "risk_level": guard.get("risk_level"),
                        "warnings": guard.get("warnings", []),
                        "avg_cost": round(avg_cost, 4),
                        "raw_mark": guard.get("raw_mark"),
                        "applied_mark": guard.get("applied_mark"),
                    }
                )
            if guard.get("risk_level") == "blocked":
                valuation_neutralized_symbols.append(symbol)
            value = qty * mark
            pnl = (mark - avg_cost) * qty
            if guard.get("risk_level") == "blocked":
                quarantined_value_by_currency[currency] = quarantined_value_by_currency.get(currency, 0.0) + value
                quarantined_symbols_by_currency.setdefault(currency, []).append(symbol)
            else:
                market_value_by_currency[currency] = market_value_by_currency.get(currency, 0.0) + value
                unrealized_by_currency[currency] = unrealized_by_currency.get(currency, 0.0) + pnl
            included_in_base_total = currency == base_currency and guard.get("risk_level") != "blocked"
            if included_in_base_total:
                market_value += value
                unrealized += pnl
            else:
                excluded_from_base_total.append(symbol)
            position_rows.append(
                {
                    "symbol": symbol,
                    "market": guard.get("market"),
                    "currency": currency,
                    "quantity": round(qty, 6),
                    "avg_cost": round(avg_cost, 4),
                    "mark": round(mark, 4),
                    "raw_mark": round(raw_mark, 4),
                    "value": round(value, 2),
                    "unrealized_pnl": round(pnl, 2),
                    "unrealized_pct": round((mark / avg_cost - 1) * 100, 2) if avg_cost else 0.0,
                    "included_in_base_total": included_in_base_total,
                    "valuation_quality": guard.get("risk_level"),
                    "valuation_guard": guard,
                }
            )
        cash = cash_by_currency.get(base_currency, 0.0)
        realized = realized_by_currency.get(base_currency, 0.0)
        equity = cash + market_value
        currency_codes = sorted(
            set(cash_by_currency)
            | set(market_value_by_currency)
            | set(realized_by_currency)
            | set(unrealized_by_currency)
            | set(quarantined_value_by_currency)
        )
        currency_breakdown = {
            currency: _paper_currency_bucket(
                currency,
                cash_by_currency,
                market_value_by_currency,
                realized_by_currency,
                unrealized_by_currency,
                base_currency=base_currency,
            )
            for currency in currency_codes
        }
        for currency, bucket in currency_breakdown.items():
            bucket["quarantined_market_value"] = round(quarantined_value_by_currency.get(currency, 0.0), 2)
            bucket["quarantined_symbols"] = quarantined_symbols_by_currency.get(currency, [])
        valuation_quality = (
            "suspect"
            if valuation_neutralized_symbols
            else "watch" if ledger_quarantined_tickets or valuation_warnings or excluded_from_base_total else "ok"
        )
        return {
            "base_currency": base_currency,
            "start_cash": round(self.paper_start_cash, 2),
            "cash": round(cash, 2),
            "market_value": round(market_value, 2),
            "equity": round(equity, 2),
            "realized_pnl": round(realized, 2),
            "unrealized_pnl": round(unrealized, 2),
            "total_pnl": round(equity - self.paper_start_cash, 2),
            "total_pnl_pct": round((equity / self.paper_start_cash - 1) * 100, 2),
            "positions": position_rows,
            "ticket_count": len(filled),
            "blocked_count": sum(1 for row in self.tickets() if str(row.get("status", "")).endswith("BLOCKED")),
            "recent_tickets": list(reversed(self.tickets(limit=12))),
            "valuation_quality": valuation_quality,
            "currency_breakdown": currency_breakdown,
            "excluded_from_base_total": excluded_from_base_total,
            "ledger_quarantined_ticket_count": len(ledger_quarantined_tickets),
            "ledger_quarantined_tickets": ledger_quarantined_tickets[-20:],
            "valuation_guard": {
                "quality": valuation_quality,
                "warning_count": len(valuation_warnings),
                "ledger_quarantined_ticket_count": len(ledger_quarantined_tickets),
                "ledger_quarantined_tickets": ledger_quarantined_tickets[-20:],
                "neutralized_symbols": valuation_neutralized_symbols,
                "excluded_from_base_total": excluded_from_base_total,
                "currency_breakdown": currency_breakdown,
                "aggregation_mode": "base_currency_only_without_fx_conversion",
                "base_currency": base_currency,
                "warnings": valuation_warnings[:12],
                "safety": "Paper PnL totals include only KRW-confirmed positions. Non-KRW positions are kept in currency_breakdown until FX-aware conversion is available.",
            },
        }

    def _default_telegram_policy(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "dedupe_enabled": True,
            "dedupe_window_minutes": 20,
            "rate_limit_enabled": True,
            "min_interval_minutes_by_type": {
                "scheduled_pre_market": 120,
                "scheduled_market_midday": 120,
                "scheduled_market_close": 120,
                "scheduled_post_review": 120,
                "scheduled_evening_21": 120,
                "trade_reason": 5,
                "simple_trade_paper": 0,
                "simple_trade_live_plan": 0,
                "simple_trade_live_execution": 0,
                "external_signal_alert": 10,
                "internal_developer_urgent": 0,
                "command_reply": 0,
                "manual": 0,
            },
            "pending_soft_limit_by_type": {
                "scheduled_pre_market": 2,
                "scheduled_market_midday": 2,
                "scheduled_market_close": 2,
                "scheduled_post_review": 2,
                "scheduled_evening_21": 2,
                "trade_reason": 8,
                "simple_trade_paper": 20,
                "simple_trade_live_plan": 20,
                "simple_trade_live_execution": 20,
                "external_signal_alert": 3,
                "internal_developer_urgent": 5,
                "command_reply": 20,
                "manual": 5,
            },
            "manual_dispatch_limit": 1,
            "auto_dispatch": True,
            "strict_report_mode": True,
            "allowed_message_types": [
                "scheduled_pre_market",
                "scheduled_market_midday",
                "scheduled_market_close",
                "scheduled_post_review",
                "scheduled_evening_21",
                "trade_reason",
                "simple_trade_paper",
                "simple_trade_live_plan",
                "simple_trade_live_execution",
                "external_signal_alert",
                "internal_developer_urgent",
                "command_reply",
                "manual",
            ],
            "suppressed_message_types": [
                "daemon_brief",
                "health_report",
                "promotion_rehearsal_trend",
                "promotion_rehearsal_review",
                "promotion_rehearsal_digest",
                "ai_brief",
                "mission_brief",
                "alert_digest",
                "competitive_audit",
            ],
            "daemon_auto_report_enabled": False,
            "health_auto_report_enabled": False,
            "promotion_trend_auto_report_enabled": False,
            "scheduled_reports_enabled": True,
            "trade_reason_reports_enabled": True,
            "external_signal_alerts_enabled": True,
            "scheduled_report_windows": {
                "pre_market": {"enabled": True, "time": "07:40", "label": "장전 준비 보고", "grace_minutes": 45, "weekdays_only": True},
                "market_midday": {"enabled": True, "time": "12:30", "label": "장중 중간 점검", "grace_minutes": 45, "weekdays_only": True},
                "market_close": {"enabled": True, "time": "15:40", "label": "장마감 보고", "grace_minutes": 60, "weekdays_only": True},
                "post_review": {"enabled": True, "time": "17:30", "label": "장 복기 후 보고", "grace_minutes": 75, "weekdays_only": True},
                "evening_21": {"enabled": True, "time": "21:00", "label": "저녁 9시 연구 요약", "grace_minutes": 90, "weekdays_only": True},
            },
            "reporting_mode": "silent_learning",
            "safety": "텔레그램은 명령 응답, 장전/장중/마감/복기/21시 시간표 보고, 주문 사유 보고에 사용합니다. 연구 데몬/건강점검/리허설 변화 자동보고는 기본 OFF이며, 실제 주문은 별도 승인 전까지 BLOCKED입니다.",
        }

    def _telegram_message_allowed(self, policy: dict[str, Any], message_type: str, source: str = "") -> tuple[bool, str]:
        message_type = str(message_type or "report")
        source = str(source or "")
        if message_type.startswith("scheduled_") and not bool(policy.get("scheduled_reports_enabled", True)):
            return False, "scheduled_reports_disabled"
        if message_type in {"trade_reason", "simple_trade_paper", "simple_trade_live_plan", "simple_trade_live_execution"} and not bool(policy.get("trade_reason_reports_enabled", True)):
            return False, "trade_reason_reports_disabled"
        if message_type == "external_signal_alert" and not bool(policy.get("external_signal_alerts_enabled", True)):
            return False, "external_signal_alerts_disabled"
        if message_type == "daemon_brief" and not bool(policy.get("daemon_auto_report_enabled", False)):
            return False, "daemon_auto_report_disabled"
        if message_type == "health_report" and not bool(policy.get("health_auto_report_enabled", False)):
            return False, "health_auto_report_disabled"
        if message_type == "promotion_rehearsal_trend" and not bool(policy.get("promotion_trend_auto_report_enabled", False)):
            return False, "promotion_trend_auto_report_disabled"
        suppressed = policy.get("suppressed_message_types", [])
        if isinstance(suppressed, list) and message_type in {str(item) for item in suppressed}:
            return False, "suppressed_message_type"
        if bool(policy.get("strict_report_mode", False)):
            allowed = policy.get("allowed_message_types", [])
            allowed_set = {str(item) for item in allowed} if isinstance(allowed, list) else set()
            if message_type not in allowed_set:
                return False, "not_in_allowed_message_types"
        return True, "allowed"

    def telegram_policy(self) -> dict[str, Any]:
        policy = self._default_telegram_policy()
        saved = self._read_json(self.telegram_policy_file, {})
        if isinstance(saved, dict):
            for key, value in saved.items():
                if isinstance(policy.get(key), dict) and isinstance(value, dict):
                    merged = dict(policy[key])
                    merged.update(value)
                    policy[key] = merged
                else:
                    policy[key] = value
        if bool(policy.get("strict_report_mode", False)):
            allowed = policy.get("allowed_message_types", [])
            allowed_list = [str(item) for item in allowed] if isinstance(allowed, list) else []
            for required_type in (
                "simple_trade_paper",
                "simple_trade_live_plan",
                "simple_trade_live_execution",
                "external_signal_alert",
                "internal_developer_urgent",
            ):
                if required_type not in allowed_list:
                    allowed_list.append(required_type)
            policy["allowed_message_types"] = allowed_list
        return policy

    def save_telegram_policy(self, patch: dict[str, Any]) -> dict[str, Any]:
        policy = self.telegram_policy()
        for key, value in patch.items():
            if isinstance(policy.get(key), dict) and isinstance(value, dict):
                merged = dict(policy[key])
                merged.update(value)
                policy[key] = merged
            else:
                policy[key] = value
        self._write_json(self.telegram_policy_file, policy)
        self.audit("TELEGRAM_POLICY_UPDATED", "텔레그램 보고 정책을 업데이트했습니다.", {"policy": policy})
        return policy

    def _telegram_fingerprint(self, text: str, message_type: str, source: str) -> str:
        normalized_text = " ".join(str(text or "").split()).strip()
        raw = "|".join([str(message_type or "report"), str(source or "ops"), normalized_text])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    def _minutes_since(self, created_at: Any) -> float | None:
        try:
            return (datetime.now() - datetime.fromisoformat(str(created_at))).total_seconds() / 60
        except (TypeError, ValueError):
            return None

    def _telegram_policy_skip_record(
        self,
        *,
        status: str,
        text: str,
        message_type: str,
        source: str,
        fingerprint: str,
        metadata: dict[str, Any],
        reason: str,
        matched_id: str = "",
        window_minutes: float = 0.0,
    ) -> dict[str, Any]:
        record = {
            "id": f"TGSKIP-{int(time.time() * 1000)}",
            "created_at": self.now(),
            "status": status,
            "queued": False,
            "message_type": message_type,
            "source": source,
            "text": text,
            "telegram_fingerprint": fingerprint,
            "metadata": metadata,
            "policy": {
                "reason": reason,
                "matched_id": matched_id,
                "window_minutes": round(float(window_minutes or 0), 2),
            },
        }
        self.audit(
            "TELEGRAM_POLICY_SKIP",
            f"텔레그램 보고 등록 보류: {message_type} / {status}",
            {"id": record["id"], "matched_id": matched_id, "reason": reason, "status": status},
        )
        return record

    def queue_telegram(self, text: str, message_type: str = "report", source: str = "ops", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._telegram_queue_lock:
            return self._queue_telegram_locked(text, message_type, source, metadata)

    def _queue_telegram_locked(self, text: str, message_type: str = "report", source: str = "ops", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        message_type = str(message_type or "report")
        source = str(source or "ops")
        text = str(text or "")
        metadata = metadata or {}
        policy = self.telegram_policy()
        fingerprint = self._telegram_fingerprint(text, message_type, source)
        recent_rows = self._read_jsonl(self.telegram_outbox_file)[-600:]
        if policy.get("enabled", True):
            allowed, reason = self._telegram_message_allowed(policy, message_type, source)
            if not allowed:
                return self._telegram_policy_skip_record(
                    status="muted_by_policy",
                    text=text,
                    message_type=message_type,
                    source=source,
                    fingerprint=fingerprint,
                    metadata=metadata,
                    reason=reason,
                )
            single_delivery_id = str(
                metadata.get("single_delivery_id") or metadata.get("incident_id") or ""
            ).strip()
            if metadata.get("single_delivery") is True and single_delivery_id:
                for row in reversed(recent_rows):
                    row_metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                    row_delivery_id = str(
                        row_metadata.get("single_delivery_id")
                        or row_metadata.get("incident_id")
                        or ""
                    ).strip()
                    if (
                        str(row.get("message_type") or "") == message_type
                        and row_metadata.get("single_delivery") is True
                        and row_delivery_id == single_delivery_id
                    ):
                        return self._telegram_policy_skip_record(
                            status="deduped",
                            text=text,
                            message_type=message_type,
                            source=source,
                            fingerprint=fingerprint,
                            metadata=metadata,
                            reason="single_delivery incident was already queued",
                            matched_id=str(row.get("id", "")),
                        )
            if policy.get("dedupe_enabled", True):
                dedupe_window = float(policy.get("dedupe_window_minutes", 20) or 0)
                for row in reversed(recent_rows):
                    row_fingerprint = row.get("telegram_fingerprint") or self._telegram_fingerprint(
                        str(row.get("text", "")),
                        str(row.get("message_type", "")),
                        str(row.get("source", "")),
                    )
                    minutes = self._minutes_since(row.get("created_at"))
                    if row_fingerprint == fingerprint and minutes is not None and minutes <= dedupe_window:
                        return self._telegram_policy_skip_record(
                            status="deduped",
                            text=text,
                            message_type=message_type,
                            source=source,
                            fingerprint=fingerprint,
                            metadata=metadata,
                            reason=f"{dedupe_window:g}분 안에 같은 보고가 이미 등록되었습니다.",
                            matched_id=str(row.get("id", "")),
                            window_minutes=dedupe_window,
                        )
            if policy.get("rate_limit_enabled", True):
                intervals = policy.get("min_interval_minutes_by_type", {})
                min_interval = float(intervals.get(message_type, intervals.get("manual", 0)) if isinstance(intervals, dict) else 0)
                if min_interval > 0:
                    for row in reversed(recent_rows):
                        if str(row.get("message_type", "")) != message_type or str(row.get("source", "")) != source:
                            continue
                        minutes = self._minutes_since(row.get("created_at"))
                        if minutes is not None and minutes < min_interval:
                            return self._telegram_policy_skip_record(
                                status="rate_limited",
                                text=text,
                                message_type=message_type,
                                source=source,
                                fingerprint=fingerprint,
                                metadata=metadata,
                                reason=f"{message_type} 보고는 {min_interval:g}분 간격으로만 등록합니다.",
                                matched_id=str(row.get("id", "")),
                                window_minutes=min_interval,
                            )
        record = {
            "id": f"TG-{time.time_ns()}",
            "created_at": self.now(),
            "status": "queued",
            "message_type": message_type,
            "source": source,
            "text": text,
            "telegram_fingerprint": fingerprint,
            "metadata": metadata,
            "policy": {
                "dedupe_enabled": bool(policy.get("dedupe_enabled", True)),
                "rate_limit_enabled": bool(policy.get("rate_limit_enabled", True)),
            },
        }
        self._append_jsonl(self.telegram_outbox_file, record)
        self.audit("TELEGRAM_QUEUED", f"텔레그램 outbox 등록: {message_type}", {"id": record["id"]})
        return record

    def telegram_outbox(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(reversed(self._read_jsonl(self.telegram_outbox_file)[-limit:]))

    def telegram_dispatches(self, limit: int | None = None) -> list[dict[str, Any]]:
        rows = self._read_jsonl(self.telegram_dispatch_file)
        return rows[-limit:] if limit else rows

    def telegram_dispatched_ids(self) -> set[str]:
        return {
            str(row.get("outbox_id", ""))
            for row in self.telegram_dispatches()
            if row.get("outbox_id")
            and row.get("status") in {"claimed_once", "sent", "dry_run", "skipped", "failed_terminal"}
        }

    def claim_single_delivery_telegram(self, outbox_record: dict[str, Any], source: str = "dispatcher") -> dict[str, Any] | None:
        metadata = outbox_record.get("metadata") if isinstance(outbox_record.get("metadata"), dict) else {}
        if metadata.get("single_delivery") is not True:
            return None
        outbox_id = str(outbox_record.get("id", ""))
        if not outbox_id or outbox_id in self.telegram_dispatched_ids():
            return None
        record = {
            "id": f"TGDCLAIM-{time.time_ns()}",
            "created_at": self.now(),
            "outbox_id": outbox_id,
            "message_type": outbox_record.get("message_type"),
            "source": source,
            "status": "claimed_once",
            "single_delivery": True,
            "single_delivery_id": str(metadata.get("single_delivery_id") or metadata.get("incident_id") or ""),
            "ok": True,
            "sent": False,
            "message": "단일 발송 사건의 첫 전송 시도를 선점했습니다.",
        }
        self._append_jsonl(self.telegram_dispatch_file, record)
        return record

    def pending_telegram_outbox(self, limit: int = 20) -> list[dict[str, Any]]:
        dispatched = self.telegram_dispatched_ids()
        policy = self.telegram_policy()
        rows = []
        for row in self._read_jsonl(self.telegram_outbox_file):
            if row.get("status") != "queued" or str(row.get("id", "")) in dispatched:
                continue
            allowed, _reason = self._telegram_message_allowed(
                policy,
                str(row.get("message_type", "manual")),
                str(row.get("source", "")),
            )
            if allowed:
                rows.append(row)
        return list(reversed(rows[-limit:]))

    def telegram_policy_stats(self, limit: int = 200) -> dict[str, Any]:
        audits = [row for row in self.audit_log(limit=limit) if row.get("action") == "TELEGRAM_POLICY_SKIP"]
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for row in audits:
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            status = str(payload.get("status", "skipped"))
            by_status[status] = by_status.get(status, 0) + 1
            message = str(row.get("message", ""))
            if "/" in message:
                message_type = message.split("/", 1)[0].split(":")[-1].strip()
                by_type[message_type] = by_type.get(message_type, 0) + 1
        return {
            "recent_skips": len(audits),
            "by_status": by_status,
            "by_type": by_type,
            "recent": audits[:8],
        }

    def record_telegram_dispatch(self, outbox_record: dict[str, Any], result: dict[str, Any], source: str = "dispatcher") -> dict[str, Any]:
        metadata = outbox_record.get("metadata") if isinstance(outbox_record.get("metadata"), dict) else {}
        single_delivery = metadata.get("single_delivery") is True
        status = (
            "sent"
            if result.get("sent")
            else "dry_run"
            if result.get("ok")
            else "failed_terminal"
            if single_delivery
            else "failed"
        )
        telegram_result = result.get("telegram") if isinstance(result.get("telegram"), dict) else {}
        telegram_message = telegram_result.get("result") if isinstance(telegram_result.get("result"), dict) else {}
        safe_result = {
            "ok": bool(result.get("ok")),
            "sent": bool(result.get("sent")),
            "message": result.get("message", ""),
            "status": result.get("status", {}),
            "telegram_message_id": telegram_message.get("message_id"),
            "delivery_status": result.get("delivery_status", ""),
            "used_integrity_fallback": bool(result.get("used_integrity_fallback")),
            "text_integrity": result.get("text_integrity", {}),
        }
        if "preview" in result:
            safe_result["preview"] = str(result.get("preview", ""))[:800]
        record = {
            "id": f"TGD-{time.time_ns()}",
            "created_at": self.now(),
            "outbox_id": outbox_record.get("id"),
            "message_type": outbox_record.get("message_type"),
            "source": source,
            "status": status,
            "ok": bool(result.get("ok")),
            "sent": bool(result.get("sent")),
            "message": result.get("message", ""),
            "single_delivery": single_delivery,
            "single_delivery_id": str(metadata.get("single_delivery_id") or metadata.get("incident_id") or ""),
            "result": safe_result,
        }
        self._append_jsonl(self.telegram_dispatch_file, record)
        self.audit("TELEGRAM_DISPATCH", f"{outbox_record.get('id')} {status}", {"dispatch": record})
        return record

    def live_dry_submits(self, limit: int | None = None) -> list[dict[str, Any]]:
        rows = self._read_jsonl(self.data_dir / "live_dry_submits.jsonl")
        return rows[-limit:] if limit else rows

    def save_kis_state(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        payload = {"updated_at": self.now(), "snapshot": snapshot}
        self._write_json(self.kis_state_file, payload)
        return payload

    def kis_state(self) -> dict[str, Any]:
        state = self._read_json(self.kis_state_file, {})
        return state if isinstance(state, dict) else {}

    def evaluate_backtest_risk_gate(self, result: dict[str, Any], config: BacktestRiskGateConfig | None = None) -> dict[str, Any]:
        cfg = config or self.gate_config
        quality = result.get("trade_quality") if isinstance(result.get("trade_quality"), dict) else {}
        trade_count = int(result.get("trade_count") or 0)
        win_rate = float(quality.get("win_rate_pct") or 0)
        expectancy = float(quality.get("expectancy_pct") or 0)
        profit_factor = float(quality.get("profit_factor") or 0)
        drawdown = abs(float(result.get("max_drawdown_pct") or 0))
        loss_streak = int(quality.get("longest_loss_streak") or quality.get("max_consecutive_losses") or 0)
        reconciliation = result.get("backtest_return_reconciliation") if isinstance(result.get("backtest_return_reconciliation"), dict) else {}
        if not reconciliation:
            reconciliation = result.get("trade_journal_reconciliation_summary") if isinstance(result.get("trade_journal_reconciliation_summary"), dict) else {}
        reconciliation_checked = int(reconciliation.get("checked_count") or 0)
        reconciliation_blockers = int(reconciliation.get("blocker_count") or 0)
        reconciliation_official_blockers = int(reconciliation.get("official_return_blocker_count") or 0)
        reconciliation_ok = reconciliation_checked > 0 and reconciliation_blockers == 0 and reconciliation_official_blockers == 0
        checks = [
            {"name": "min_trade_count", "ok": trade_count >= cfg.min_trade_count, "value": trade_count, "required": cfg.min_trade_count},
            {"name": "min_win_rate_pct", "ok": win_rate >= cfg.min_win_rate_pct, "value": win_rate, "required": cfg.min_win_rate_pct},
            {"name": "min_expectancy_pct", "ok": expectancy >= cfg.min_expectancy_pct, "value": expectancy, "required": cfg.min_expectancy_pct},
            {"name": "min_profit_factor", "ok": profit_factor >= cfg.min_profit_factor, "value": profit_factor, "required": cfg.min_profit_factor},
            {"name": "max_drawdown_pct", "ok": drawdown <= cfg.max_drawdown_pct, "value": drawdown, "required": cfg.max_drawdown_pct},
            {"name": "max_consecutive_losses", "ok": loss_streak <= cfg.max_consecutive_losses, "value": loss_streak, "required": cfg.max_consecutive_losses},
            {
                "name": "return_reconciliation",
                "ok": reconciliation_ok,
                "value": {
                    "checked_count": reconciliation_checked,
                    "blocker_count": reconciliation_blockers,
                    "official_return_blocker_count": reconciliation_official_blockers,
                    "status": reconciliation.get("status"),
                },
                "required": "checked_count>0, blocker_count=0, official_return_blocker_count=0",
            },
        ]
        failed = [item for item in checks if not item["ok"]]
        status = "PASSED" if not failed else "BLOCKED"
        return_reconciliation_failed = any(item.get("name") == "return_reconciliation" for item in failed)
        if failed and not return_reconciliation_failed and len(failed) <= 2 and trade_count >= max(3, cfg.min_trade_count // 2):
            status = "REVIEW"
        return {
            "status": status,
            "passed": status == "PASSED",
            "checks": checks,
            "failed": failed,
            "summary": {
                "trade_count": trade_count,
                "win_rate_pct": round(win_rate, 2),
                "expectancy_pct": round(expectancy, 4),
                "profit_factor": round(profit_factor, 3),
                "max_drawdown_pct": round(drawdown, 2),
                "max_consecutive_losses": loss_streak,
                "return_reconciliation_checked_count": reconciliation_checked,
                "return_reconciliation_blocker_count": reconciliation_blockers,
                "return_reconciliation_official_blocker_count": reconciliation_official_blockers,
            },
            "config": asdict(cfg),
            "message": "실전 후보 가능" if status == "PASSED" else "실전 후보 차단" if status == "BLOCKED" else "추가 검토 필요",
        }

    def status(self, marks: dict[str, float] | None = None) -> dict[str, Any]:
        approvals = self.approvals()
        pending = [row for row in approvals if row.get("status") == "pending"]
        approved = [row for row in approvals if row.get("status") == "approved"]
        telegram_policy = self.telegram_policy()
        autotrade_policy = self.autotrade_policy()
        return {
            "generated_at": self.now(),
            "safety": "실전 주문 잠금 / 후보와 dry-run만 허용",
            "autotrade_policy": autotrade_policy,
            "paper": self.paper_summary(marks=marks),
            "approvals": {
                "total": len(approvals),
                "pending": len(pending),
                "approved": len(approved),
                "recent": list(reversed(approvals[-12:])),
            },
            "duplicate_guard": {
                "ledger_path": str(self.duplicate_file),
                "fingerprints": len(self.duplicate_fingerprints()),
                "ready": self.duplicate_file.exists(),
            },
            "telegram_outbox": {
                "queued": len([row for row in self.telegram_outbox() if row.get("status") == "queued"]),
                "pending_dispatch": len(self.pending_telegram_outbox(limit=1000)),
                "recent": self.telegram_outbox(limit=8),
                "dispatch_recent": list(reversed(self.telegram_dispatches(limit=8))),
            },
            "telegram_policy": {
                "enabled": bool(telegram_policy.get("enabled", True)),
                "dedupe_enabled": bool(telegram_policy.get("dedupe_enabled", True)),
                "dedupe_window_minutes": telegram_policy.get("dedupe_window_minutes", 20),
                "rate_limit_enabled": bool(telegram_policy.get("rate_limit_enabled", True)),
                "min_interval_minutes_by_type": telegram_policy.get("min_interval_minutes_by_type", {}),
                "pending_soft_limit_by_type": telegram_policy.get("pending_soft_limit_by_type", {}),
                "manual_dispatch_limit": telegram_policy.get("manual_dispatch_limit", 3),
                "auto_dispatch": bool(telegram_policy.get("auto_dispatch", False)),
                "daemon_auto_report_enabled": bool(telegram_policy.get("daemon_auto_report_enabled", False)),
                "health_auto_report_enabled": bool(telegram_policy.get("health_auto_report_enabled", False)),
                "promotion_trend_auto_report_enabled": bool(telegram_policy.get("promotion_trend_auto_report_enabled", False)),
                "scheduled_reports_enabled": bool(telegram_policy.get("scheduled_reports_enabled", True)),
                "trade_reason_reports_enabled": bool(telegram_policy.get("trade_reason_reports_enabled", True)),
                "scheduled_report_windows": telegram_policy.get("scheduled_report_windows", {}),
                "reporting_mode": telegram_policy.get("reporting_mode", "silent_learning"),
                "stats": self.telegram_policy_stats(limit=200),
            },
            "kis_state": self.kis_state(),
            "audit": self.audit_log(limit=10),
            "risk_state": self._risk_state(),
            "paths": {
                "data_dir": str(self.data_dir),
                "data_dir_source": self.data_dir_source,
                "default_data_dir": str(self.default_data_dir),
                "user_data_env_key": self.user_data_env_key,
                "user_data_root": str(self.user_data_root) if self.user_data_root else "",
                "tickets": str(self.ticket_file),
                "approvals": str(self.approval_file),
                "audit": str(self.audit_file),
                "telegram_outbox": str(self.telegram_outbox_file),
                "telegram_dispatch": str(self.telegram_dispatch_file),
                "telegram_policy": str(self.telegram_policy_file),
                "autotrade_policy": str(self.autotrade_policy_file),
            },
        }
