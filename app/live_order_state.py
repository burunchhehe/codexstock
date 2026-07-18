from __future__ import annotations


RECONCILIATION_WATCH_SECONDS = 3 * 60
RECONCILIATION_OVERDUE_SECONDS = 10 * 60


def _age_minutes(age_seconds: int | None) -> float | None:
    return round((age_seconds or 0) / 60, 1) if age_seconds is not None else None


def build_reconciliation_sla(
    workflow: dict[str, object],
    stage_state: dict[str, object],
    *,
    today_date: str,
    submit_age_seconds: int | None,
) -> dict[str, object]:
    """Return the post-submit reconciliation SLA state for a live-order workflow."""
    submit_at = str(workflow.get("latest_submit_at") or workflow.get("updated_at") or workflow.get("created_at") or "")
    submit_date = submit_at[:10] if submit_at else ""
    reconciliation_state = str(stage_state.get("reconciliation") or "")
    broker_state = str(stage_state.get("broker_submit") or "")
    if broker_state != "done":
        return {
            "state": "not_submitted",
            "severity": "idle",
            "age_seconds": submit_age_seconds,
            "age_minutes": _age_minutes(submit_age_seconds),
            "should_pause_new_live_orders": False,
            "message": "브로커 전송 전 단계라 체결/잔고 대조 SLA를 적용하지 않습니다.",
        }
    if reconciliation_state == "done":
        return {
            "state": "reconciled",
            "severity": "ok",
            "age_seconds": submit_age_seconds,
            "age_minutes": _age_minutes(submit_age_seconds),
            "should_pause_new_live_orders": False,
            "message": "해당 주문에 직접 연결된 체결/잔고 대조가 완료됐습니다.",
        }
    if reconciliation_state == "blocked":
        return {
            "state": "mismatch_or_blocked",
            "severity": "critical",
            "age_seconds": submit_age_seconds,
            "age_minutes": _age_minutes(submit_age_seconds),
            "should_pause_new_live_orders": True,
            "message": "체결/잔고 대조가 차단 상태입니다. 신규 실주문보다 대조 원인 확인이 우선입니다.",
        }
    if submit_date and submit_date != today_date:
        return {
            "state": "historical_backfill_needed",
            "severity": "history",
            "age_seconds": submit_age_seconds,
            "age_minutes": _age_minutes(submit_age_seconds),
            "should_pause_new_live_orders": False,
            "message": f"{submit_date} 과거 주문의 직접 대조 연결이 비어 있습니다. 기록 백필/정리 대상입니다.",
        }
    if submit_age_seconds is None:
        return {
            "state": "unknown_age",
            "severity": "warning",
            "age_seconds": None,
            "age_minutes": None,
            "should_pause_new_live_orders": False,
            "message": "주문 전송 시각을 해석하지 못해 대조 지연 시간을 계산하지 못했습니다.",
        }
    age_minutes = _age_minutes(submit_age_seconds)
    if submit_age_seconds >= RECONCILIATION_OVERDUE_SECONDS:
        return {
            "state": "overdue",
            "severity": "critical",
            "age_seconds": submit_age_seconds,
            "age_minutes": age_minutes,
            "should_pause_new_live_orders": True,
            "message": f"실전 전송 후 {age_minutes}분째 직접 대조가 붙지 않았습니다. 읽기전용 체결/잔고 대조를 먼저 실행해야 합니다.",
        }
    if submit_age_seconds >= RECONCILIATION_WATCH_SECONDS:
        return {
            "state": "watch",
            "severity": "warning",
            "age_seconds": submit_age_seconds,
            "age_minutes": age_minutes,
            "should_pause_new_live_orders": False,
            "message": f"실전 전송 후 {age_minutes}분째 대조 대기 중입니다. 곧바로 대조 결과가 붙는지 감시합니다.",
        }
    return {
        "state": "fresh_wait",
        "severity": "ok",
        "age_seconds": submit_age_seconds,
        "age_minutes": age_minutes,
        "should_pause_new_live_orders": False,
        "message": f"실전 전송 후 {age_minutes}분 경과했습니다. 자동 대조 결과를 기다리는 정상 대기 구간입니다.",
    }


def determine_current_order_stage(
    stage_state: dict[str, object],
    reconciliation_sla: dict[str, object],
) -> dict[str, str]:
    """Return the user-facing live-order stage and the next safe action."""
    if stage_state.get("reconciliation") == "done":
        return {
            "current_stage": "reconciled",
            "current_label": "정산 대조 완료",
            "next_action": "매매일지와 성과 복기에 연결합니다.",
        }
    if stage_state.get("reconciliation") == "blocked":
        return {
            "current_stage": "reconciliation_blocked",
            "current_label": "체결/잔고 대조 차단",
            "next_action": "한투 체결/잔고와 로컬 주문 로그를 확인하기 전 신규 실주문을 멈춥니다.",
        }
    if stage_state.get("broker_submit") == "done":
        if reconciliation_sla.get("state") == "historical_backfill_needed":
            return {
                "current_stage": "reconciliation_backfill_needed",
                "current_label": "과거 대조 백필 필요",
                "next_action": str(reconciliation_sla.get("message") or "과거 주문의 체결/잔고 대조 기록을 백필합니다."),
            }
        if reconciliation_sla.get("state") == "unknown_age":
            return {
                "current_stage": "reconciliation_age_unknown",
                "current_label": "대조 기준시각 확인 필요",
                "next_action": str(reconciliation_sla.get("message") or "주문 전송 시각을 먼저 복원합니다."),
            }
        if reconciliation_sla.get("state") == "watch":
            return {
                "current_stage": "reconciliation_watch",
                "current_label": "체결/잔고 대조 감시",
                "next_action": str(reconciliation_sla.get("message") or "자동 대조 결과가 붙는지 감시합니다."),
            }
        if reconciliation_sla.get("state") == "overdue":
            return {
                "current_stage": "reconciliation_overdue",
                "current_label": "체결/잔고 대조 지연",
                "next_action": str(reconciliation_sla.get("message") or "체결/잔고 대조를 먼저 실행합니다."),
            }
        return {
            "current_stage": "submitted",
            "current_label": "브로커 전송 완료",
            "next_action": "체결/잔고 대조를 실행해 주문 결과를 확정합니다.",
        }
    if stage_state.get("broker_submit") == "blocked":
        return {
            "current_stage": "submit_blocked",
            "current_label": "최종 전송 차단",
            "next_action": "차단된 최종 게이트 항목을 해결한 뒤 새 후보부터 다시 진행합니다.",
        }
    if stage_state.get("dry_submit") == "done":
        return {
            "current_stage": "ready_to_submit",
            "current_label": "최종 전송 대기",
            "next_action": "정규장/확인문구/체결대조 게이트를 확인한 뒤 최종 전송 여부를 사용자가 결정합니다.",
        }
    if stage_state.get("dry_submit") == "blocked":
        return {
            "current_stage": "dry_blocked",
            "current_label": "Dry-submit 차단",
            "next_action": "승인, 중복주문, 리스크 한도 차단 원인을 해결합니다.",
        }
    if stage_state.get("approval") == "done":
        return {
            "current_stage": "dry_needed",
            "current_label": "Dry-submit 필요",
            "next_action": "브로커 전송 전 dry-submit 검증을 실행합니다.",
        }
    if stage_state.get("approval") == "wait":
        return {
            "current_stage": "approval_pending",
            "current_label": "승인 대기",
            "next_action": "후보 근거를 확인하고 승인/거절을 결정합니다.",
        }
    if stage_state.get("approval") == "blocked":
        return {
            "current_stage": "approval_blocked",
            "current_label": "승인 차단/만료",
            "next_action": "새 실전 후보를 생성해 새 승인 토큰을 발급합니다.",
        }
    if stage_state.get("candidate") in {"done", "wait"}:
        return {
            "current_stage": "candidate",
            "current_label": "후보 생성됨",
            "next_action": "승인 토큰 상태를 확인합니다.",
        }
    return {
        "current_stage": "unknown",
        "current_label": "상태 복원 필요",
        "next_action": "후보/승인/dry-submit/전송 로그 연결 상태를 확인합니다.",
    }
