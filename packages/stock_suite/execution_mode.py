"""Canonical fail-closed execution-mode policy shared by the app and sidecar."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


MANUAL_APPROVAL = "manual_approval"
DELEGATED_AUTO = "delegated_auto"
SUPPORTED_CONTROL_MODES = {MANUAL_APPROVAL, DELEGATED_AUTO}


def _trading_date() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()


def build_delegated_authorization(
    policy: dict[str, object],
    *,
    trading_date: str | None = None,
) -> dict[str, object]:
    target_date = str(trading_date or _trading_date()).strip()
    authorized_date = str(policy.get("delegated_live_authorized_date") or "").strip()
    confirmed = bool(policy.get("delegated_live_authorization_confirmed", False))
    delegated_enabled = bool(policy.get("delegated_live_autonomy_enabled", False))
    authorization_mode = str(
        policy.get("delegated_live_authorization_mode") or "daily"
    ).strip().lower()
    standing = bool(
        authorization_mode == "standing"
        and str(policy.get("live_execution_control_mode") or "").strip().lower()
        == DELEGATED_AUTO
    )
    valid_today = bool(
        delegated_enabled
        and (standing or (confirmed and authorized_date == target_date))
    )
    if valid_today:
        status = "STANDING_DELEGATION_ACTIVE" if standing else "AUTHORIZED_TODAY"
        message = (
            "설정에서 완전자동 운용을 선택했습니다. 해제할 때까지 설정 한도와 독립 실행기 안전 게이트를 적용합니다."
            if standing
            else f"{target_date} 실전 위임 최종 지시가 확인되었습니다. 설정 한도와 모든 주문 게이트를 계속 적용합니다."
        )
    elif not delegated_enabled:
        status = "DELEGATED_OFF"
        message = "실전 위임 자동운용이 꺼져 있습니다. 연구·후보 탐색·Paper 운용은 별도 정책으로 계속할 수 있습니다."
    elif authorized_date:
        status = "DAILY_AUTHORIZATION_EXPIRED"
        message = f"마지막 실전 위임일은 {authorized_date}입니다. {target_date} 실전 주문에는 새 최종 지시가 필요합니다."
    else:
        status = "DAILY_AUTHORIZATION_REQUIRED"
        message = f"{target_date} 실전 위임 최종 지시가 없습니다. 후보 탐색은 계속하지만 실제 주문은 차단합니다."
    return {
        "valid_today": valid_today,
        "status": status,
        "trading_date": target_date,
        "authorized_date": authorized_date,
        "authorized_at": str(policy.get("delegated_live_authorized_at") or ""),
        "source": str(policy.get("delegated_live_authorization_source") or ""),
        "scope": str(policy.get("delegated_live_authorization_scope") or ""),
        "authorization_mode": authorization_mode,
        "message": message,
    }


def build_execution_policy_contract(
    policy: dict[str, object],
    *,
    trading_date: str | None = None,
) -> dict[str, object]:
    requested_mode = str(
        policy.get("live_execution_control_mode") or MANUAL_APPROVAL
    ).strip().lower()
    require_approval = bool(policy.get("require_approval", True))
    delegated_enabled = bool(policy.get("delegated_live_autonomy_enabled", False))
    conflicts: list[str] = []
    if requested_mode not in SUPPORTED_CONTROL_MODES:
        conflicts.append("unsupported_control_mode")
    elif requested_mode == MANUAL_APPROVAL:
        if not require_approval:
            conflicts.append("manual_mode_requires_approval")
        if delegated_enabled:
            conflicts.append("manual_mode_cannot_enable_delegated_autonomy")
    else:
        if require_approval:
            conflicts.append("delegated_mode_cannot_require_per_order_approval")
        if not delegated_enabled:
            conflicts.append("delegated_mode_requires_delegated_autonomy")

    policy_consistent = not conflicts
    delegated = bool(requested_mode == DELEGATED_AUTO and policy_consistent)
    authorization = build_delegated_authorization(
        policy,
        trading_date=trading_date,
    )
    authorization_required = delegated
    authorization_valid = bool(
        not authorization_required or authorization.get("valid_today")
    )
    live_switches_enabled = bool(
        policy.get("live_pilot_enabled") and policy.get("live_execution_enabled")
    )
    safety_halt = bool(policy.get("emergency_halt") or policy.get("day_halted"))
    desired_sidecar_mode = (
        "live"
        if delegated
        and authorization_valid
        and live_switches_enabled
        and not safety_halt
        else "shadow"
    )
    return {
        "control_mode": requested_mode,
        "require_approval": require_approval,
        "delegated_enabled": delegated_enabled,
        "policy_consistent": policy_consistent,
        "policy_conflicts": conflicts,
        "delegated": delegated,
        "requires_user_approval": not delegated,
        "authorization_required": authorization_required,
        "authorization_valid": authorization_valid,
        "authorization": authorization,
        "live_switches_enabled": live_switches_enabled,
        "safety_halt": safety_halt,
        "desired_sidecar_mode": desired_sidecar_mode,
    }
