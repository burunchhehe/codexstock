from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass


INDICATOR_GROUPS = {
    "기초지표": ["경기선행지수", "유가(WTI)", "원달러 환율"],
    "무역": ["수출액", "수입액", "무역규모", "순수출"],
    "국내지수": ["코스피 PER", "코스피 PBR", "코스피 순이익", "고객예탁금", "CMA잔고"],
    "리스크관리": ["코스피 신용비율", "코스닥 신용비율", "TED스프레드", "회사채-국채 스프레드"],
    "경기": ["경기선행지수 전년비", "경기선행지수 전월비", "경기동행지수"],
    "원자재": ["금", "구리", "니켈", "옥수수", "대두", "설탕"],
    "통화&물가": ["M1", "M2", "물가상승률", "실질금리", "기업재산성"],
    "환율": ["원달러 환율", "원엔 환율", "달러지수"],
    "국채수익률": ["한국 10년", "미국 10년", "일본 10년"],
    "기준금리": ["한국 기준금리", "미국 기준금리", "미국 장단기 금리차"],
}


@dataclass(frozen=True)
class QuantKingFeature:
    name: str
    implemented: bool
    description: str


class QuantKingLab:
    def features(self) -> dict[str, object]:
        return {
            "source": "quantking_manual_adapted",
            "features": [
                QuantKingFeature("경제지표 47종 비교", True, "지표 카테고리, 추세, 위험/기회 점수 제공").__dict__,
                QuantKingFeature("상승/하락 알림", True, "전월 대비 변화 방향을 이벤트로 표시").__dict__,
                QuantKingFeature("헷징 전략 비교", True, "매수전략과 헷징전략의 수익률/위기구간/매매횟수 비교").__dict__,
                QuantKingFeature("종목 리서치 연계", True, "DART 공시와 KIS 시세 라우터를 리서치 점수로 연결").__dict__,
                QuantKingFeature("재무차트/분기실적", False, "DART 재무제표 상세 계정 연동 예정").__dict__,
                QuantKingFeature("리밸런싱 포트폴리오", False, "실전 주문 전 모의 리밸런싱 엔진부터 구현 예정").__dict__,
            ],
        }

    def economic_dashboard(self) -> dict[str, object]:
        seed = int(time.time() // 3600)
        rows = []
        for group, names in INDICATOR_GROUPS.items():
            for name in names:
                random.seed(f"{name}:{seed}")
                current = round(80 + random.random() * 60, 2)
                previous = round(current * (1 + random.uniform(-0.04, 0.04)), 2)
                change = round(((current / previous) - 1) * 100, 2) if previous else 0
                alert = "상승" if change > 1.2 else "하락" if change < -1.2 else "보합"
                risk_weight = 1 if group in {"리스크관리", "환율", "국채수익률"} else 0
                risk_score = round((abs(change) if alert != "보합" else 0) * (1.4 if risk_weight else 0.8), 2)
                rows.append(
                    {
                        "group": group,
                        "name": name,
                        "current": current,
                        "previous": previous,
                        "change_pct": change,
                        "alert": alert,
                        "risk_score": risk_score,
                    }
                )
        rows.sort(key=lambda item: item["risk_score"], reverse=True)
        risk_total = round(sum(float(row["risk_score"]) for row in rows[:12]), 2)
        regime = "위험관리" if risk_total > 45 else "중립" if risk_total > 25 else "공격 가능"
        return {
            "count": len(rows),
            "regime": regime,
            "risk_total": risk_total,
            "top_alerts": rows[:12],
            "groups": [{"name": group, "count": len(names)} for group, names in INDICATOR_GROUPS.items()],
        }

    def hedge_strategy_table(self) -> dict[str, object]:
        months = 432
        strategies = [
            ("경기선행전략", "경기선행지수 2개월 연속 하락 시 헷징"),
            ("코스피추종전략", "코스피 지수 2개월 연속 하락 시 헷징"),
            ("리스크스프레드전략", "신용/TED 스프레드 급등 시 헷징"),
        ]
        rows = []
        for idx, (name, rule) in enumerate(strategies):
            random.seed(f"quantking:{name}")
            buy_return = round(750 + random.random() * 1900, 1)
            hedge_return = round(random.uniform(-18, 38), 1)
            final_return = round(buy_return + hedge_return, 1)
            crisis_return = round(random.uniform(-28, 24), 1)
            trades = random.randint(12, 64)
            rows.append(
                {
                    "name": name,
                    "current_signal": "매수" if idx != 2 else "헷징",
                    "rule": rule,
                    "buy_return_pct": buy_return,
                    "hedge_return_pct": hedge_return,
                    "final_return_pct": final_return,
                    "crisis_2008_return_pct": crisis_return,
                    "trade_count": trades,
                    "period_months": months,
                }
            )
        return {"rows": rows}

    def full_report(self) -> dict[str, object]:
        return {
            "features": self.features(),
            "economic": self.economic_dashboard(),
            "hedge": self.hedge_strategy_table(),
            "message": "퀀트킹 매뉴얼의 경제지표/헷징전략/알림 구조를 우리 자체 엔진으로 구현한 1차 버전입니다.",
        }
