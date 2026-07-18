from __future__ import annotations

ALLOWED_SOURCE_TYPES = {"github", "paper", "trade_log", "manual", "mcp", "dataset", "markdown", "sqlite", "csv", "json"}
ALLOWED_MARKETS = {"KR", "US", "GLOBAL", "CRYPTO", "PAPER"}
ALLOWED_TIMEFRAMES = {"tick", "1m", "3m", "5m", "10m", "15m", "30m", "60m", "daily", "weekly", "monthly"}
ALLOWED_STATUSES = {
    "IMPORTED",
    "VALIDATING",
    "VALIDATION_FAILED",
    "BACKTEST_READY",
    "BACKTESTING",
    "BACKTEST_FAILED",
    "REPLAY_READY",
    "REPLAYING",
    "PAPER_ONLY",
    "APPROVED_FOR_RESEARCH",
    "APPROVED_FOR_LIVE_CANDIDATE",
    "REJECTED",
    "ARCHIVED",
}

STATUS_FOLDERS = {
    "IMPORTED": "imported",
    "VALIDATING": "validating",
    "VALIDATION_FAILED": "rejected",
    "BACKTEST_READY": "validating",
    "BACKTESTING": "backtesting",
    "BACKTEST_FAILED": "rejected",
    "REPLAY_READY": "backtesting",
    "REPLAYING": "backtesting",
    "PAPER_ONLY": "paper_only",
    "APPROVED_FOR_RESEARCH": "approved_research",
    "APPROVED_FOR_LIVE_CANDIDATE": "approved_candidate",
    "REJECTED": "rejected",
    "ARCHIVED": "archive",
}

PACKAGE_EVIDENCE_STAGES = {
    "IMPORTED": "IMPORTED_UNVALIDATED",
    "VALIDATING": "SCHEMA_VALIDATION_IN_PROGRESS",
    "VALIDATION_FAILED": "SCHEMA_VALIDATION_FAILED",
    "BACKTEST_READY": "SCHEMA_VALIDATED",
    "BACKTESTING": "ENGINE_RUN_IN_PROGRESS",
    "BACKTEST_FAILED": "ENGINE_RUN_FAILED",
    "REPLAY_READY": "READY_FOR_ENGINE_RUN",
    "REPLAYING": "CROSS_ENGINE_RECONCILIATION_IN_PROGRESS",
    "PAPER_ONLY": "CROSS_ENGINE_RECONCILED_RESEARCH_ONLY",
    "APPROVED_FOR_RESEARCH": "READY_FOR_ENGINE_RUN",
    "APPROVED_FOR_LIVE_CANDIDATE": "PROMOTION_ELIGIBLE",
    "REJECTED": "REJECTED",
    "ARCHIVED": "ARCHIVED",
}

STAGE2_COST_POLICY_VERSION = "mandatory-market-specific-paper-costs.v2"


def package_status_semantics(status: object) -> dict[str, object]:
    legacy_status = str(status or "IMPORTED").strip().upper()
    evidence_stage = PACKAGE_EVIDENCE_STAGES.get(legacy_status, "UNKNOWN")
    return {
        "legacy_status": legacy_status,
        "evidence_stage": evidence_stage,
        "profitability_verified": evidence_stage in {
            "CROSS_ENGINE_RECONCILED_RESEARCH_ONLY",
            "PROMOTION_ELIGIBLE",
        },
        "paper_eligible": evidence_stage in {
            "CROSS_ENGINE_RECONCILED_RESEARCH_ONLY",
            "PROMOTION_ELIGIBLE",
        },
        "live_promotion_eligible": evidence_stage == "PROMOTION_ELIGIBLE",
        "explanation": (
            "BACKTEST_READY means schema-validated input ready for an engine run; "
            "it does not mean that profitability has been backtested or verified."
            if legacy_status == "BACKTEST_READY"
            else "Evidence stage is derived from the stored legacy workflow status."
        ),
    }


def market_specific_stage2_cost_model(market: object) -> dict[str, object]:
    market_scope = str(market or "MIXED").strip().upper()
    if market_scope not in {"KR", "US"}:
        market_scope = "MIXED"
    profiles = {
        "KR": {
            "currency": "KRW",
            "commission_bps_per_side": 1.5,
            "sell_tax_bps": 18.0,
            "slippage_bps_per_side": 5.0,
            "minimum_fee": 0.0,
            "regulatory_fee_policy": "not_applicable",
            "fx_conversion_spread_bps_per_side": 0.0,
        },
        "US": {
            "currency": "USD",
            "commission_bps_per_side": 1.5,
            "sell_tax_bps": 0.0,
            "slippage_bps_per_side": 5.0,
            "minimum_fee": 0.0,
            "sec_section31_fee_policy": "date-aware official SEC schedule",
            "finra_taf_policy": "date-aware official FINRA schedule",
            "finra_taf_2026_per_share_usd": 0.000195,
            "finra_taf_2026_max_per_trade_usd": 9.79,
            "fx_conversion_spread_bps_per_side": 10.0,
        },
    }
    selected_profile = profiles.get(market_scope, {})
    return {
        "model_id": STAGE2_COST_POLICY_VERSION,
        "status": "forced_for_stage2_verification",
        "market_scope": market_scope,
        "market_profiles": profiles,
        "selected_profile": selected_profile,
        "mixed_market_requires_per_trade_profile": market_scope == "MIXED",
        "commission_bps_per_side": selected_profile.get("commission_bps_per_side", 1.5),
        "sell_tax_bps": selected_profile.get("sell_tax_bps", 0.0),
        "slippage_bps_per_side": selected_profile.get("slippage_bps_per_side", 5.0),
        "minimum_fee_krw": 0.0,
        "fx_conversion_spread_bps_per_side": selected_profile.get(
            "fx_conversion_spread_bps_per_side", 10.0 if market_scope == "MIXED" else 0.0
        ),
        "notes": [
            "Every trade must select the KR or US profile from its market field.",
            "US sells require date-aware SEC Section 31 and FINRA TAF reconciliation.",
            "US buy and sell cash flows require KRW/USD conversion-spread reconciliation.",
            "Package-reported returns remain research-only until the same market-specific ledger reconciles.",
        ],
    }

FOLDERS = tuple(dict.fromkeys(STATUS_FOLDERS.values()))

REQUIRED_FIELDS = (
    "package_id",
    "source_name",
    "source_type",
    "source_url",
    "license",
    "market",
    "strategy_id",
    "strategy_name",
    "description",
    "entry_rules",
    "exit_rules",
    "stop_rules",
    "position_sizing_rules",
    "required_data",
    "performance",
)

REQUIRED_PERFORMANCE_FIELDS = (
    "start_date",
    "end_date",
    "return_pct",
    "annualized_return_pct",
    "mdd_pct",
    "win_rate_pct",
    "profit_factor",
    "trade_count",
    "fees_included",
    "tax_included",
    "slippage_included",
)

OPEN_SOURCE_CATALOG = [
    {
        "source_name": "QuantConnect Lean",
        "source_type": "github",
        "source_url": "https://github.com/QuantConnect/Lean",
        "license": "verify_required",
        "what_to_absorb": [
            "event-driven engine structure",
            "common research/backtest/live interfaces",
            "brokerage/data model separation",
            "fee/slippage/fill model discipline",
        ],
        "safe_use": "메타데이터와 설계 원칙만 연구용으로 수입합니다. 코드는 실행하지 않습니다.",
    },
    {
        "source_name": "NautilusTrader",
        "source_type": "github",
        "source_url": "https://github.com/nautechsystems/nautilus_trader",
        "license": "verify_required",
        "what_to_absorb": [
            "deterministic replay",
            "same semantics across backtest and live",
            "order/fill/latency model separation",
            "high-performance event processing",
        ],
        "safe_use": "체결/리플레이 설계만 학습하고 실전 주문 모듈에는 연결하지 않습니다.",
    },
    {
        "source_name": "vectorbt",
        "source_type": "github",
        "source_url": "https://github.com/polakowo/vectorbt",
        "license": "verify_required",
        "what_to_absorb": [
            "large-scale parameter sweeps",
            "vectorized strategy comparison",
            "indicator matrix evaluation",
            "fast research feedback loop",
        ],
        "safe_use": "대량 실험/순위화 구조를 연구합니다. 검증 전 결과는 Paper 전용입니다.",
    },
    {
        "source_name": "Freqtrade",
        "source_type": "github",
        "source_url": "https://github.com/freqtrade/freqtrade",
        "license": "verify_required",
        "what_to_absorb": [
            "strategy config format",
            "backtesting plus hyperopt workflow",
            "risk and money management settings",
            "Telegram/WebUI operation patterns",
        ],
        "safe_use": "운영 패턴과 전략 설정 스키마를 참고하되 자동주문 권한은 부여하지 않습니다.",
    },
    {
        "source_name": "Backtrader",
        "source_type": "github",
        "source_url": "https://github.com/mementum/backtrader",
        "license": "verify_required",
        "what_to_absorb": [
            "strategy/analyzer/broker abstraction",
            "classic event-driven backtesting",
            "indicator composition patterns",
        ],
        "safe_use": "레거시 전략 표현 변환 참고용으로만 사용합니다.",
    },
    {
        "source_name": "vn.py",
        "source_type": "github",
        "source_url": "https://github.com/vnpy/vnpy",
        "license": "verify_required",
        "what_to_absorb": [
            "gateway architecture",
            "CTA strategy templates",
            "risk manager separation",
            "multi-market trading app structure",
        ],
        "safe_use": "게이트웨이/리스크 분리 구조만 연구합니다. 브로커 연결 코드는 실행하지 않습니다.",
    },
]

ENGINE_DATA_CONTRACT_FIELDS = (
    "dataset_id",
    "snapshot_id",
    "symbol",
    "market",
    "currency",
    "timezone",
    "adjustment_type",
    "as_of",
    "source",
    "data_hash",
    "calendar_version",
    "corporate_action_version",
)

ENGINE_RESULT_CONTRACT_FIELDS = (
    "engine_name",
    "engine_version",
    "code_commit",
    "dataset_hash",
    "snapshot_id",
    "strategy_version",
    "parameters",
    "start_date",
    "end_date",
    "initial_cash",
    "fees",
    "tax",
    "slippage_model",
    "fill_model",
    "trade_count",
    "return_pct",
    "cagr_pct",
    "mdd_pct",
    "sharpe",
    "profit_factor",
    "turnover",
    "rejected_orders",
    "partial_fills",
    "execution_time_ms",
    "artifact_path",
)

ENGINE_PROMOTION_STAGES = [
    {
        "stage": 1,
        "name": "vectorbt_mass_screen",
        "description": "대량 파라미터 탐색과 후보 압축만 수행합니다.",
        "promotion_rule": "상위 후보를 바로 실전 승격하지 않고 Stage 2 정밀 검증으로 넘깁니다.",
    },
    {
        "stage": 2,
        "name": "nautilus_or_lean_cross_validation",
        "description": "수수료, 세금, 슬리피지, 체결 모델을 적용해 독립 엔진으로 재검증합니다.",
        "promotion_rule": "결과 괴리가 크면 코덱스스톡 실전 후보 승격을 차단합니다.",
    },
    {
        "stage": 3,
        "name": "codexstock_paper_rehearsal",
        "description": "코덱스스톡 Paper/과거장 리플레이에서 동일 데이터 해시로 재현성을 확인합니다.",
        "promotion_rule": "30~60일 Paper 또는 충분한 리플레이 통과 전 실전 연결 금지.",
    },
    {
        "stage": 4,
        "name": "risk_gate_live_candidate",
        "description": "최종 주문 권한은 코덱스스톡 단일 리스크 게이트만 갖습니다.",
        "promotion_rule": "외부 엔진은 PROPOSE_* 제안만 가능하고 KIS 주문 API 권한은 금지합니다.",
    },
]

ENGINE_ROLE_CATALOG = [
    {
        "engine_name": "CodexStock",
        "role": "central_control_room",
        "priority": 0,
        "allowed_actions": ["final_decision", "risk_gate", "paper_rehearsal", "kis_readonly", "kis_order_after_user_approval"],
        "forbidden_actions": ["blindly_average_external_returns", "promote_without_reconciliation"],
        "status": "active",
    },
    {
        "engine_name": "DuckDB/SQLite",
        "role": "common_data_contract_store",
        "priority": 1,
        "allowed_actions": ["snapshot_index", "data_hash", "result_search", "reconciliation_index"],
        "forbidden_actions": ["submit_order"],
        "status": "local_first",
    },
    {
        "engine_name": "vectorbt",
        "role": "mass_parameter_screening",
        "priority": 2,
        "allowed_actions": ["run_parameter_sweep", "compare_strategy_matrix", "walk_forward_candidate_scan"],
        "forbidden_actions": ["submit_order", "approve_live_candidate"],
        "status": "planned_stage2_adapter",
    },
    {
        "engine_name": "NautilusTrader",
        "role": "deterministic_replay_and_fill_audit",
        "priority": 3,
        "allowed_actions": ["replay_events", "audit_fill_sequence", "audit_order_state_machine"],
        "forbidden_actions": ["hold_kis_secret", "submit_order"],
        "status": "planned_stage2_adapter",
    },
    {
        "engine_name": "QuantConnect Lean",
        "role": "standard_backtest_cross_validation",
        "priority": 4,
        "allowed_actions": ["standard_backtest", "fee_slippage_fill_model_check", "portfolio_result_compare"],
        "forbidden_actions": ["hold_kis_secret", "submit_order"],
        "status": "planned_stage2_adapter",
    },
    {
        "engine_name": "OpenBB",
        "role": "global_data_gateway_and_cross_check",
        "priority": 5,
        "allowed_actions": ["global_data_fetch", "macro_cross_check", "provider_field_standardization"],
        "forbidden_actions": ["submit_order"],
        "status": "deferred",
    },
    {
        "engine_name": "Qlib",
        "role": "ml_oos_research",
        "priority": 6,
        "allowed_actions": ["rank_prediction_research", "regime_classification", "feature_importance"],
        "forbidden_actions": ["submit_order", "train_on_unverified_data"],
        "status": "deferred_after_data_contract",
    },
    {
        "engine_name": "Freqtrade/vn.py/Backtrader/FinRL",
        "role": "operation_pattern_and_experiment_lab",
        "priority": 7,
        "allowed_actions": ["dry_run_pattern_study", "lookahead_bias_check_study", "gateway_design_study", "paper_rl_experiment"],
        "forbidden_actions": ["submit_order", "copy_code_without_license_review"],
        "status": "research_only",
    },
]

ENGINE_CONTRACT_SAFETY_RULES = [
    "외부 엔진은 실전 주문 API 키와 계좌번호를 받지 않습니다.",
    "외부 엔진 출력은 PROPOSE_* 제안과 검증 리포트까지만 허용합니다.",
    "같은 dataset_hash와 snapshot_id를 사용한 결과만 서로 비교합니다.",
    "vectorbt 결과는 탐색 결과이며 Lean/Nautilus/CodexStock 검증 전 실전 승격 금지입니다.",
    "여러 엔진 수익률을 평균내지 않고 가장 현실적인 체결 조건의 보수적 결과를 기준으로 삼습니다.",
]
