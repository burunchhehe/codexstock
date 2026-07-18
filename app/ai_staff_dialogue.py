from __future__ import annotations

import re


def compact_meeting_text(value: object, max_chars: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(20, max_chars - 3)].rstrip() + "..."


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def staff_dialogue_role(speaker: str, stance: str, message: object = "") -> str:
    text = f"{speaker} {stance} {message}".lower()
    if _contains_any(
        text,
        (
            "리스크",
            "위험",
            "손절",
            "게이트",
            "차단",
            "보류",
            "risk",
            "gate",
            "block",
        ),
    ):
        return "risk_challenge"
    if _contains_any(
        text,
        (
            "운용",
            "매매",
            "주문",
            "체결",
            "승인",
            "operator",
            "execution",
            "order",
        ),
    ):
        return "execution_challenge"
    if _contains_any(
        text,
        (
            "수급",
            "분봉",
            "호가",
            "체결강도",
            "거래대금",
            "시장",
            "뉴스",
            "재무",
            "공시",
            "근거",
            "evidence",
            "market",
            "fundamental",
            "strategy",
        ),
    ):
        return "evidence"
    if _contains_any(text, ("연구", "후보", "가설", "판단", "research", "claim", "candidate")):
        return "claim"
    return "comment"


def _normalize_dialogue_role(speaker: str, stance: str, message: object, current_role: str) -> str:
    text = f"{speaker} {stance} {message}".lower()
    if _contains_any(text, ("반대", "위험", "리스크", "손실", "손절", "차단", "과열", "편중", "고위험", "보류")):
        return "risk_challenge"
    if _contains_any(text, ("주문", "체결", "분봉", "호가", "승인", "실행", "매수 조건", "매도 조건")):
        return "execution_challenge"
    if _contains_any(text, ("근거", "수급", "외국인", "거래대금", "재무", "뉴스", "공시", "백테스트", "데이터")):
        return "evidence"
    if _contains_any(text, ("추천", "제안", "후보", "주장", "선정", "매수 의견")):
        return "claim"
    return current_role


SECTOR_RESEARCHER_DESK: list[dict[str, object]] = [
    {"id": "semiconductor", "name": "반도체 연구원", "coverage": ["반도체", "HBM", "AI 반도체", "장비", "소부장"]},
    {"id": "defense", "name": "방산 연구원", "coverage": ["방산", "항공우주", "국방"]},
    {"id": "shipbuilding", "name": "조선 연구원", "coverage": ["조선", "해양", "LNG"]},
    {"id": "power_grid", "name": "전력 연구원", "coverage": ["전력", "전력망", "변압기", "원전"]},
    {"id": "finance", "name": "금융 연구원", "coverage": ["은행", "증권", "보험", "지주"]},
    {"id": "bio", "name": "바이오 연구원", "coverage": ["바이오", "제약", "헬스케어"]},
    {"id": "ai_software", "name": "AI·소프트웨어 연구원", "coverage": ["AI", "소프트웨어", "클라우드", "데이터센터"]},
]


_SECTOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "semiconductor": ("반도체", "hbm", "sk하이닉스", "삼성전자", "hpsp", "테크윙", "GST", "퀄리타스", "소부장"),
    "defense": ("방산", "한화에어로", "항공우주", "국방", "전쟁", "방위"),
    "shipbuilding": ("조선", "선박", "lng", "hd현대중공업", "삼성중공업", "한화오션"),
    "power_grid": ("전력", "변압기", "전선", "원전", "전력망", "hd현대일렉트릭"),
    "finance": ("은행", "금융", "증권", "보험", "kb금융", "신한지주", "하나금융"),
    "bio": ("바이오", "제약", "임상", "헬스케어", "셀트리온", "삼성바이오"),
    "ai_software": ("ai", "소프트웨어", "클라우드", "데이터센터", "로봇", "플랫폼"),
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _summaries_for_role(structured: list[dict[str, object]], roles: set[str], limit: int = 4) -> list[str]:
    rows: list[str] = []
    for row in structured:
        if row.get("role") not in roles:
            continue
        summary = str(row.get("summary") or "").strip()
        if summary:
            rows.append(summary)
        if len(rows) >= limit:
            break
    return rows


def _infer_sector_from_text(meeting: dict[str, object], top: dict[str, object], structured: list[dict[str, object]]) -> dict[str, object]:
    joined = " ".join(
        [
            str(meeting.get("agenda") or ""),
            str(top.get("name") or ""),
            str(top.get("symbol") or ""),
            " ".join(str(row.get("summary") or "") for row in structured),
        ]
    ).lower()
    for sector_id, keywords in _SECTOR_KEYWORDS.items():
        if any(keyword.lower() in joined for keyword in keywords):
            desk = next((row for row in SECTOR_RESEARCHER_DESK if row.get("id") == sector_id), {})
            return {
                "id": sector_id,
                "name": desk.get("name", sector_id),
                "matched": True,
                "coverage": desk.get("coverage", []),
            }
    return {"id": "unknown", "name": "업종 미분류", "matched": False, "coverage": []}


def _meeting_has_sector_first(meeting: dict[str, object], structured: list[dict[str, object]]) -> bool:
    text = " ".join(
        [str(meeting.get("agenda") or "")]
        + [str(row.get("summary") or "") for row in structured]
        + [str(item) for item in meeting.get("next_actions", []) if str(item).strip()]
    ).lower()
    return _contains_any(text, ("업종", "섹터", "비중", "편중", "포트폴리오", "sector", "allocation", "weight"))


def _build_debate_flow(
    meeting: dict[str, object],
    structured: list[dict[str, object]],
    decision: dict[str, object],
    top: dict[str, object],
    next_actions: list[str],
) -> dict[str, object]:
    claims = _summaries_for_role(structured, {"claim"}, 3)
    evidence = _summaries_for_role(structured, {"evidence"}, 4)
    objections = _summaries_for_role(structured, {"risk_challenge", "execution_challenge"}, 4)
    rebuttals = [
        str(row.get("summary"))
        for row in structured
        if row.get("role") == "evidence" and row.get("responds_to") and str(row.get("summary") or "").strip()
    ][1:4]
    top_name = str(top.get("name") or top.get("symbol") or "후보 미정")
    if not claims:
        claims = [str(decision.get("label") or f"{top_name} 검토 필요")]
    if not evidence:
        evidence = ["수급·재무·뉴스·백테스트 근거가 아직 충분히 분리 기록되지 않았습니다."]
    if not objections:
        objections = ["반대 의견 부족: 다음 회의에서 리스크 관리자와 반대 연구원의 명시 반론이 필요합니다."]
    if not rebuttals:
        rebuttals = ["재반론 부족: 다음 회의에서 반론에 대한 데이터 기반 재검증을 기록해야 합니다."]
    pros = sum(1 for row in structured if row.get("role") in {"claim", "evidence"})
    cons = sum(1 for row in structured if row.get("role") in {"risk_challenge", "execution_challenge"})
    neutral = max(0, len(structured) - pros - cons)
    return {
        "claim": claims[:3],
        "evidence": evidence[:4],
        "objections": objections[:4],
        "rebuttals": rebuttals[:3],
        "chair_conclusion": {
            "candidate": top_name,
            "decision": decision.get("label") or "-",
            "next_actions": next_actions[:5],
            "real_execution": meeting.get("real_execution", "BLOCKED"),
        },
        "vote_balance": {"pros": pros, "cons": cons, "neutral": neutral},
        "dissent_count": cons,
        "is_real_debate": bool(claims and evidence and cons > 0),
    }


def _build_investment_committee_frame(
    meeting: dict[str, object],
    structured: list[dict[str, object]],
    decision: dict[str, object],
    top: dict[str, object],
    next_actions: list[str],
    debate_flow: dict[str, object],
) -> dict[str, object]:
    sector = _infer_sector_from_text(meeting, top, structured)
    sector_first = _meeting_has_sector_first(meeting, structured)
    confidence = _safe_float(decision.get("confidence"), 0.5)
    dissent_count = int(debate_flow.get("dissent_count") or 0)
    execution_state = str(meeting.get("real_execution") or "BLOCKED").upper()
    base_weight = 15.0 if confidence >= 0.75 else 10.0 if confidence >= 0.55 else 5.0
    base_weight = max(0.0, base_weight - min(6.0, dissent_count * 2.0))
    if execution_state not in {"EXECUTED", "FILLED", "SUBMITTED"}:
        base_weight = min(base_weight, 5.0)
    assigned_researcher = next((row for row in SECTOR_RESEARCHER_DESK if row.get("id") == sector.get("id")), {})
    final_name = str(top.get("name") or top.get("symbol") or "후보 미정")
    return {
        "sector_first_review": {
            "status": "pass" if sector_first else "needs_sector_allocation_first",
            "inferred_sector": sector,
            "message": "업종 비중을 먼저 확인한 회의입니다." if sector_first else "종목 검토 전에 업종 점수·업종 최대비중을 먼저 확정해야 합니다.",
        },
        "sector_researchers": {
            "required_desks": SECTOR_RESEARCHER_DESK,
            "assigned": assigned_researcher or {"id": "unknown", "name": "업종 미분류 담당", "coverage": []},
        },
        "votes": {
            "pros": debate_flow.get("vote_balance", {}).get("pros", 0) if isinstance(debate_flow.get("vote_balance"), dict) else 0,
            "cons": debate_flow.get("vote_balance", {}).get("cons", 0) if isinstance(debate_flow.get("vote_balance"), dict) else 0,
            "neutral": debate_flow.get("vote_balance", {}).get("neutral", 0) if isinstance(debate_flow.get("vote_balance"), dict) else 0,
            "dissent_required": dissent_count <= 0,
        },
        "chair_decision": {
            "chair": "CodexStock 투자위원회 의장",
            "final_symbol": top.get("symbol") or "-",
            "final_name": final_name,
            "suggested_weight_pct": round(base_weight, 2),
            "buy_condition": "분봉·호가·체결강도와 업종 비중 게이트가 동시에 통과할 때만 검토",
            "stop_condition": "초기 손절선 또는 회의가 지정한 리스크 한도 이탈 시 축소/철회",
            "withdraw_condition": "업종 편중, 데이터 정합성 경고, 승인 만료, 분봉 누락, 주문 게이트 실패 시 철회",
            "approval_state": execution_state,
        },
        "memory_follow_through": {
            "long_term_memory": {"status": "enabled", "target": "staff_meetings memory + note"},
            "candidate_score_update": {"status": "queued", "target": "next candidate scoring memory adjustment"},
            "next_tournament": {"status": "queued_if_candidate", "target": "same-sector replay/tournament comparison"},
            "portfolio_update": {"status": "queued_sector_review", "target": "sector exposure and cash weight review"},
        },
    }


def _build_meeting_quality_v2(
    dialogue_quality: dict[str, object],
    debate_flow: dict[str, object],
    committee: dict[str, object],
    next_actions: list[str],
) -> dict[str, object]:
    sector_status = ((committee.get("sector_first_review") or {}) if isinstance(committee.get("sector_first_review"), dict) else {}).get("status")
    chair = committee.get("chair_decision") if isinstance(committee.get("chair_decision"), dict) else {}
    memory = committee.get("memory_follow_through") if isinstance(committee.get("memory_follow_through"), dict) else {}
    vote_balance = debate_flow.get("vote_balance") if isinstance(debate_flow.get("vote_balance"), dict) else {}
    gates = {
        "has_claim": bool(debate_flow.get("claim")),
        "has_evidence": bool(debate_flow.get("evidence")),
        "has_dissent": int(vote_balance.get("cons") or 0) > 0,
        "has_chair_decision": bool(chair.get("final_name")),
        "has_sector_first": sector_status == "pass",
        "has_memory_follow_through": bool(memory),
        "has_next_actions": bool(next_actions),
    }
    score = int(_safe_float(dialogue_quality.get("score"), 70))
    penalties = {
        "no_dissent": 14 if not gates["has_dissent"] else 0,
        "no_sector_first": 14 if not gates["has_sector_first"] else 0,
        "no_chair": 10 if not gates["has_chair_decision"] else 0,
        "no_memory_link": 8 if not gates["has_memory_follow_through"] else 0,
        "no_next_actions": 8 if not gates["has_next_actions"] else 0,
    }
    score = max(0, min(100, score - sum(penalties.values())))
    return {
        "score": score,
        "grade": "investment_committee" if score >= 82 else "debate_ready" if score >= 68 else "thin_meeting",
        "quality_gates": gates,
        "penalties": penalties,
        "dimensions": {
            "debate_quality": 100 if debate_flow.get("is_real_debate") else 60,
            "sector_first_quality": 100 if gates["has_sector_first"] else 45,
            "dissent_quality": 100 if gates["has_dissent"] else 35,
            "chair_quality": 100 if gates["has_chair_decision"] else 50,
            "memory_quality": 90 if gates["has_memory_follow_through"] else 40,
            "portfolio_quality": 90 if gates["has_sector_first"] and gates["has_chair_decision"] else 50,
        },
        "message": (
            "주장-근거-반론-의장결론-장기기억 연결이 투자위원회 형태로 기록됐습니다."
            if score >= 82
            else "회의는 구조화됐지만 반대 의견, 업종 선결정, 의장 결론 중 일부를 더 강화해야 합니다."
        ),
    }


def _build_decision_frame(
    structured: list[dict[str, object]],
    decision: dict[str, object],
    top: dict[str, object],
    next_actions: list[str],
    real_execution: object,
) -> dict[str, object]:
    observations = [
        str(row.get("summary"))
        for row in structured
        if row.get("role") == "evidence" and str(row.get("summary") or "").strip()
    ][:4]
    claims = [
        str(row.get("summary"))
        for row in structured
        if row.get("role") == "claim" and str(row.get("summary") or "").strip()
    ][:3]
    risk_checks = [
        str(row.get("summary"))
        for row in structured
        if row.get("role") in {"risk_challenge", "execution_challenge"} and str(row.get("summary") or "").strip()
    ][:4]
    if not observations and top:
        observations.append(
            f"{top.get('name') or top.get('symbol') or '후보 없음'} 점수 {top.get('score', '-')}, 게이트 {top.get('gate', '-')}"
        )
    if not claims:
        claims.append(str(decision.get("label") or "명확한 투자 가설이 부족합니다."))
    if not risk_checks:
        risk_checks.append("리스크/주문 반론이 충분히 기록되지 않았습니다.")
    verification_needed = []
    if not observations:
        verification_needed.append("시장/수급/재무 근거 보강")
    if len(risk_checks) < 2:
        verification_needed.append("손절, 주문 가능 수량, 체결 후 대조 조건 확인")
    if not next_actions:
        verification_needed.append("다음 행동을 실행 가능한 문장으로 남기기")
    top_name = str(top.get("name") or top.get("symbol") or "후보")
    execution_state = str(real_execution or "BLOCKED").upper()
    baseline_checks = [
        f"{top_name} 최신 분봉, 체결강도, 거래대금이 후보 점수를 계속 지지하는지 확인",
        f"{top_name} 최신 뉴스, 공시, 재무 리스크에 새 악재가 없는지 확인",
        "주문 전 현금, 자동운용 비중, 중복주문, 승인대기, 1일 손실한도를 확인",
        "진입 전 손절가, 1차 익절가, 시간청산 기준을 숫자로 남기기",
    ]
    if execution_state not in {"EXECUTED", "FILLED", "SUBMITTED"}:
        baseline_checks.append("실전 주문 전 후보 판단과 실제 주문 가능 상태를 한 번 더 분리 검증")
    for check in baseline_checks:
        if check not in verification_needed:
            verification_needed.append(check)
    return {
        "observation": observations,
        "thesis": claims,
        "risk_checks": risk_checks,
        "action_plan": next_actions[:5],
        "verification_needed": verification_needed,
        "verification_count": len(verification_needed),
        "execution_state": str(real_execution or "BLOCKED"),
        "machine_summary": {
            "symbol": top.get("symbol") or "-",
            "name": top.get("name") or top.get("symbol") or "-",
            "score": top.get("score"),
            "decision": decision.get("label") or "-",
            "confidence": decision.get("confidence"),
            "execution_bias": decision.get("execution_bias") or "-",
        },
    }


def build_staff_meeting_structure(meeting: dict[str, object]) -> dict[str, object]:
    messages = meeting.get("messages") if isinstance(meeting.get("messages"), list) else []
    decision = meeting.get("decision") if isinstance(meeting.get("decision"), dict) else {}
    top = meeting.get("top_candidate") if isinstance(meeting.get("top_candidate"), dict) else {}
    next_actions = [str(item) for item in meeting.get("next_actions", []) if str(item).strip()]
    structured: list[dict[str, object]] = []
    speaker_counts: dict[str, int] = {}
    role_counts = {
        "claim": 0,
        "evidence": 0,
        "risk_challenge": 0,
        "execution_challenge": 0,
        "comment": 0,
    }
    previous_speaker = ""
    for index, row in enumerate(messages, start=1):
        if not isinstance(row, dict):
            continue
        speaker = str(row.get("speaker") or row.get("name") or f"참가자 {index}")
        stance = str(row.get("stance") or row.get("role") or "-")
        message = row.get("message")
        role = _normalize_dialogue_role(speaker, stance, message, staff_dialogue_role(speaker, stance, message))
        role_counts[role] = role_counts.get(role, 0) + 1
        speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
        structured.append(
            {
                "turn": index,
                "speaker": speaker,
                "role": role,
                "stance": stance,
                "summary": compact_meeting_text(message, 220),
                "responds_to": previous_speaker,
                "model": row.get("model", ""),
            }
        )
        previous_speaker = speaker
    turn_count = len(structured)
    max_speaker_turns = max(speaker_counts.values()) if speaker_counts else 0
    monologue_ratio = round(max_speaker_turns / max(1, turn_count), 3)
    challenge_turns = role_counts.get("risk_challenge", 0) + role_counts.get("execution_challenge", 0)
    evidence_turns = role_counts.get("evidence", 0)
    missing_roles = [
        label
        for label, count in (
            ("claim", role_counts.get("claim", 0)),
            ("evidence", evidence_turns),
            ("challenge", challenge_turns),
        )
        if count <= 0
    ]
    dialogue_mode = (
        "structured_dialogue"
        if turn_count >= 3 and not missing_roles
        else "thin_dialogue"
        if turn_count >= 2
        else "monologue_risk"
    )
    quality_score = 100
    if turn_count < 3:
        quality_score -= 25
    quality_score -= min(45, len(missing_roles) * 15)
    if monologue_ratio >= 0.75:
        quality_score -= 20
    if not next_actions:
        quality_score -= 15
    quality_score = max(0, min(100, quality_score))
    decision_brief = {
        "label": decision.get("label") or "-",
        "confidence": decision.get("confidence"),
        "execution_bias": decision.get("execution_bias") or "-",
        "top_symbol": top.get("symbol") or "-",
        "top_name": top.get("name") or top.get("symbol") or "-",
        "top_score": top.get("score"),
        "real_execution": meeting.get("real_execution", "BLOCKED"),
        "next_actions": next_actions[:5],
        "one_line": (
            f"{top.get('name') or top.get('symbol') or '후보 없음'} / "
            f"{decision.get('label') or '-'} / 실전 {meeting.get('real_execution', 'BLOCKED')}"
        ),
    }
    decision_frame = _build_decision_frame(
        structured,
        decision,
        top,
        next_actions,
        meeting.get("real_execution", "BLOCKED"),
    )
    verification_count = len(decision_frame.get("verification_needed", []))
    dialogue_quality_v2_base = {
        "score": quality_score,
        "mode": dialogue_mode,
        "turn_count": turn_count,
        "speaker_count": len(speaker_counts),
        "role_counts": role_counts,
        "challenge_turns": challenge_turns,
        "evidence_turns": evidence_turns,
        "verification_count": verification_count,
        "monologue_ratio": monologue_ratio,
        "missing_roles": missing_roles,
        "message": (
            "주장, 근거, 리스크/실행 반론, 다음 행동이 분리되어 기록됐습니다."
            if dialogue_mode == "structured_dialogue"
            else "회의가 독백에 가까워질 수 있습니다. 다음 회의에는 근거, 반론, 검증 조건을 명시해야 합니다."
        ),
        "recommended_next_prompt": "각 직원은 후보 1개, 반대 근거 1개, 체결 후 검증 조건 1개를 짧게 남기세요.",
    }
    debate_flow = _build_debate_flow(meeting, structured, decision, top, next_actions)
    investment_committee_frame = _build_investment_committee_frame(
        meeting,
        structured,
        decision,
        top,
        next_actions,
        debate_flow,
    )
    meeting_quality_v2 = _build_meeting_quality_v2(
        dialogue_quality_v2_base,
        debate_flow,
        investment_committee_frame,
        next_actions,
    )
    return {
        "structured_dialogue": structured[:12],
        "decision_brief": decision_brief,
        "decision_frame": decision_frame,
        "dialogue_quality": {
            "score": quality_score,
            "mode": dialogue_mode,
            "turn_count": turn_count,
            "speaker_count": len(speaker_counts),
            "role_counts": role_counts,
            "challenge_turns": challenge_turns,
            "evidence_turns": evidence_turns,
            "verification_count": verification_count,
            "monologue_ratio": monologue_ratio,
            "missing_roles": missing_roles,
            "message": (
                "주장, 근거, 리스크/실행 반론, 다음 행동이 분리되어 기록됐습니다."
                if dialogue_mode == "structured_dialogue"
                else "회의가 독백에 가까워질 수 있습니다. 다음 회의에는 근거, 반론, 검증 조건을 명시해야 합니다."
            ),
            "recommended_next_prompt": "각 직원은 후보 1개, 반대 근거 1개, 체결 후 검증 조건 1개를 짧게 남기세요.",
        },
        "dialogue_quality_v2_base": dialogue_quality_v2_base,
        "dialogue_quality": dialogue_quality_v2_base,
        "debate_flow": debate_flow,
        "investment_committee_frame": investment_committee_frame,
        "meeting_quality_v2": meeting_quality_v2,
    }


def attach_staff_meeting_structure(meeting: dict[str, object]) -> dict[str, object]:
    structure = build_staff_meeting_structure(meeting)
    meeting["structured_dialogue"] = structure["structured_dialogue"]
    meeting["decision_brief"] = structure["decision_brief"]
    meeting["decision_frame"] = structure["decision_frame"]
    meeting["dialogue_quality"] = structure["dialogue_quality"]
    meeting["dialogue_quality"] = structure.get("dialogue_quality_v2_base", structure["dialogue_quality"])
    meeting["debate_flow"] = structure.get("debate_flow", {})
    meeting["investment_committee_frame"] = structure.get("investment_committee_frame", {})
    meeting["meeting_quality_v2"] = structure.get("meeting_quality_v2", {})
    return meeting
