from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .models import normalize_training_package
from .schema import ALLOWED_MARKETS, ALLOWED_SOURCE_TYPES, ALLOWED_TIMEFRAMES, REQUIRED_FIELDS, REQUIRED_PERFORMANCE_FIELDS

LOOKAHEAD_PATTERNS = (
    "future",
    "lookahead",
    "next close",
    "tomorrow close",
    "same close",
    "close-to-close buy",
    "미래",
    "미래데이터",
    "다음날 종가",
    "내일 종가",
    "종가를 알고",
    "종가 이후",
)

LOOKAHEAD_SAFE_CONTEXT_TERMS = (
    "avoid",
    "forbid",
    "forbidden",
    "prohibit",
    "prohibited",
    "ban",
    "banned",
    "no ",
    "not ",
    "without",
    "금지",
    "방지",
    "차단",
    "사용 금지",
    "검증 전",
    "확인 전",
)


def _issue(code: str, message: str, severity: str = "warning", field: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity, "field": field}


def _valid_date(text: Any) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    try:
        datetime.fromisoformat(value[:10])
        return True
    except ValueError:
        return False


def _combined_text(package: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in (
        "description",
        "entry_rules",
        "exit_rules",
        "stop_rules",
        "avoid_rules",
        "position_sizing_rules",
        "known_limitations",
        "evidence",
    ):
        value = package.get(key)
        if isinstance(value, list):
            chunks.extend(str(item) for item in value)
        else:
            chunks.append(str(value or ""))
    return "\n".join(chunks).lower()


def _has_lookahead_risk(package: dict[str, Any]) -> bool:
    """Detect lookahead wording without flagging explicit prevention rules."""
    for line in _combined_text(package).splitlines():
        if not any(pattern in line for pattern in LOOKAHEAD_PATTERNS):
            continue
        if any(term in line for term in LOOKAHEAD_SAFE_CONTEXT_TERMS):
            continue
        return True
    return False


def validate_training_package(raw: dict[str, Any], *, existing_ids: set[str] | None = None) -> dict[str, Any]:
    package = normalize_training_package(raw)
    existing_ids = existing_ids or set()
    warnings: list[dict[str, str]] = []
    blocks: list[dict[str, str]] = []
    score = 100.0

    for field in REQUIRED_FIELDS:
        value = package.get(field)
        missing = value is None or value == "" or value == [] or value == {}
        if missing:
            blocks.append(_issue("missing_required_field", f"필수 필드가 비어 있습니다: {field}", "block", field))
            score -= 10

    if package.get("package_id") in existing_ids:
        blocks.append(_issue("duplicate_package_id", "이미 수입된 외부 지식 패키지입니다.", "block", "package_id"))
        score -= 20

    if package.get("source_type") not in ALLOWED_SOURCE_TYPES:
        blocks.append(_issue("invalid_source_type", f"허용하지 않는 출처 유형입니다: {package.get('source_type')}", "block", "source_type"))
        score -= 12

    bad_markets = [item for item in package.get("market", []) if str(item).upper() not in ALLOWED_MARKETS]
    if bad_markets:
        blocks.append(_issue("invalid_market", f"시장 구분을 확인해야 합니다: {', '.join(map(str, bad_markets))}", "block", "market"))
        score -= 12

    bad_timeframes = [item for item in package.get("timeframe", []) if str(item) not in ALLOWED_TIMEFRAMES]
    if bad_timeframes:
        warnings.append(_issue("invalid_timeframe", f"지원하지 않는 시간봉이 있습니다: {', '.join(map(str, bad_timeframes))}", "warning", "timeframe"))
        score -= 4

    if not re.match(r"^https?://|^git@|^[a-zA-Z0-9_.:/-]+$", str(package.get("source_url", ""))):
        warnings.append(_issue("weak_source_url", "출처 주소 형식이 약합니다. 원본 확인이 필요합니다.", "warning", "source_url"))
        score -= 5

    license_text = str(package.get("license", "") or "").strip().lower()
    if not license_text or license_text in {"unknown", "verify_required", "n/a", "none"}:
        warnings.append(_issue("license_requires_verification", "라이선스 확인 전에는 연구용 이하로만 보관합니다.", "warning", "license"))
        score -= 8

    perf = package.get("performance", {}) if isinstance(package.get("performance"), dict) else {}
    for field in REQUIRED_PERFORMANCE_FIELDS:
        if field not in perf:
            blocks.append(_issue("missing_performance_field", f"성과 필드가 없습니다: {field}", "block", f"performance.{field}"))
            score -= 6

    if not _valid_date(perf.get("start_date")) or not _valid_date(perf.get("end_date")):
        blocks.append(_issue("invalid_backtest_dates", "백테스트 시작/종료일이 없거나 잘못됐습니다.", "block", "performance"))
        score -= 10
    elif str(perf.get("start_date"))[:10] > str(perf.get("end_date"))[:10]:
        blocks.append(_issue("inverted_backtest_dates", "백테스트 시작일이 종료일보다 늦습니다.", "block", "performance"))
        score -= 10

    trade_count = int(perf.get("trade_count", 0) or 0)
    if trade_count < 30:
        blocks.append(_issue("too_few_trades", "거래 횟수가 30회 미만이라 성과를 믿기 어렵습니다.", "block", "performance.trade_count"))
        score -= 16
    elif trade_count < 100:
        warnings.append(_issue("trade_count_below_promotion_bar", "거래 100회 미만은 장기기억/실전 후보 승격 불가입니다.", "warning", "performance.trade_count"))
        score -= 7

    missing_costs = [
        label
        for key, label in (
            ("fees_included", "수수료"),
            ("tax_included", "세금"),
            ("slippage_included", "슬리피지"),
        )
        if not bool(perf.get(key))
    ]
    if missing_costs:
        warnings.append(_issue("costs_missing", f"{', '.join(missing_costs)} 미반영. Paper/연구용으로만 봐야 합니다.", "warning", "performance"))
        score -= 6 * len(missing_costs)

    total_return = float(perf.get("return_pct", 0.0) or 0.0)
    annual = float(perf.get("annualized_return_pct", 0.0) or 0.0)
    mdd = abs(float(perf.get("mdd_pct", 0.0) or 0.0))
    if abs(total_return) >= 500 or abs(annual) >= 300:
        warnings.append(_issue("unrealistic_return", "수익률이 비정상적으로 큽니다. 가격/분할/상폐/미래참조 검증 전 공식 성과로 쓰지 않습니다.", "warning", "performance"))
        score -= 18
    if mdd >= 50:
        warnings.append(_issue("large_drawdown", "MDD가 50% 이상입니다. 리스크 관리자 학습용으로 우선 분류합니다.", "warning", "performance.mdd_pct"))
        score -= 9

    if _has_lookahead_risk(package):
        warnings.append(_issue("lookahead_suspected", "미래 데이터/종가 선참조 의심 문구가 있습니다.", "warning", "rules"))
        score -= 18

    if len(package.get("regimes", [])) < 2:
        warnings.append(_issue("single_regime", "장세 구분이 2개 미만입니다. 특정 장세 과최적화 위험이 있습니다.", "warning", "regimes"))
        score -= 5

    if not package.get("failure_cases"):
        warnings.append(_issue("missing_failure_cases", "실패 사례가 없습니다. 손실 회피 학습에는 제한이 있습니다.", "warning", "failure_cases"))
        score -= 4

    score = max(0.0, min(100.0, round(score, 2)))
    if blocks:
        recommended_status = "VALIDATION_FAILED"
    elif score >= 85:
        recommended_status = "APPROVED_FOR_RESEARCH"
    elif score >= 70:
        recommended_status = "BACKTEST_READY"
    else:
        recommended_status = "VALIDATING"

    promotion_allowed = (
        score >= 85
        and not blocks
        and trade_count >= 100
        and not missing_costs
        and "lookahead_suspected" not in {item["code"] for item in warnings}
        and len(package.get("regimes", [])) >= 2
        and license_text not in {"", "unknown", "verify_required", "n/a", "none"}
    )
    promotion_reason = "장기기억 후보 조건 통과" if promotion_allowed else "장기기억 승격 전 백테스트/리플레이/라이선스 추가 검증 필요"

    return {
        "ok": not blocks,
        "score": score,
        "warnings": warnings,
        "blocks": blocks,
        "recommended_status": recommended_status,
        "promotion_allowed": promotion_allowed,
        "promotion_reason": promotion_reason,
        "summary": _summary(score, blocks, warnings, recommended_status),
        "normalized_package": package,
    }


def _summary(score: float, blocks: list[dict[str, str]], warnings: list[dict[str, str]], status: str) -> str:
    if blocks:
        return f"차단 {len(blocks)}건으로 격리했습니다. 점수 {score:.1f}, 상태 {status}."
    if warnings:
        return f"경고 {len(warnings)}건이 있어 검증 단계로 보관합니다. 점수 {score:.1f}, 상태 {status}."
    return f"기본 검증 통과. 점수 {score:.1f}, 상태 {status}."
