(function attachCodexStockVisualFixture(global) {
  "use strict";

  const params = new URLSearchParams(global.location.search);
  const localHost = ["localhost", "127.0.0.1", "::1"].includes(global.location.hostname);
  const enabled = localHost && params.get("ui") === "v2" && params.get("fixture") === "visual";
  const positions = [
    ["삼성전자전자부품", "005930", 185000000, 4.31], ["SK하이닉스", "000660", 163000000, -1.82],
    ["한화에어로스페이스", "012450", 119000000, 2.15], ["현대차", "005380", 86000000, 0.74],
    ["두산에너빌리티", "034020", 62000000, -0.61], ["기타 보유종목", "ETC", 35000000, 1.05],
  ].map(([name, symbol, value, unrealized_pct]) => ({ name, symbol, value, unrealized_pct }));

  function get() {
    if (!enabled) return null;
    return {
      account: { ok: true, readonly: true, generated_at: "2026-09-25T10:24:17", summary: { net_liquidation_value: 1000000000, stock_value: 650000000, available_cash: 350000000 }, positions: positions.map((row) => ({ ...row, evaluation_amount: row.value, profit_loss_rate: row.unrealized_pct })) },
      performance: { today_realized_gross_pnl: -12500000, today_realized_count: 4 },
      ops: { generated_at: "2026-09-25T10:24:17", safety: "정상 감시", paper: null, approvals: { pending: 3, recent: [{ status: "pending", side: "매수", name: "한화에어로스페이스", created_at: "2026-09-25T10:08:00" }, { status: "pending", side: "매도", name: "현대차", created_at: "2026-09-25T10:03:00" }, { status: "pending", side: "매수", name: "두산에너빌리티", created_at: "2026-09-25T09:58:00" }] } },
      clock: { sessions: [{ id: "KR", name: "한국장", phase: "regular", phase_label: "정규장" }] },
      staff: { worker_board: { summary: { active: 7, working: 3, attention: 1 }, workers: [
        { name: "시장 연구 AI", status: "working", task: "반도체 주도주 거래대금 검증", progress: 72, updated_at: "2026-09-25T10:23:00" },
        { name: "수급 분석 AI", status: "active", task: "외국인·기관 순매수 흐름 정리", updated_at: "2026-09-25T10:22:00" },
        { name: "전략 검증 AI", status: "working", task: "돌파 전략 표본 외 검증 진행 중", progress: 46, updated_at: "2026-09-25T10:22:00" },
        { name: "리스크 관리자 AI", status: "active", task: "포지션 노출도와 손절 기준 감시", updated_at: "2026-09-25T10:21:00" },
        { name: "매매 감독 AI", status: "attention", task: "승인 대기 3건의 근거 재확인", updated_at: "2026-09-25T10:20:00" },
        { name: "뉴스 재료 AI", status: "working", task: "미국 장 마감 뉴스 영향도 분류", progress: 88, updated_at: "2026-09-25T10:20:00" },
        { name: "복기 AI", status: "ready", task: "최근 체결 원장 복기 대기", updated_at: "2026-09-25T10:19:00" },
      ] } },
      alerts: { summary: { total: 4 }, alerts: [
        { priority: "warning", title: "승인 대기 3건", message: "사람의 최종 검토가 필요한 후보가 있습니다.", action: "감독석 확인" },
        { priority: "info", title: "시장 변동성 확대", message: "반도체 업종의 체결 강도가 평소보다 높습니다.", action: "시장 관찰" },
        { priority: "opportunity", title: "후보 점수 갱신", message: "거래대금 조건을 통과한 후보가 새로 집계됐습니다.", action: "후보 보기" },
        { priority: "danger", title: "손절 기준 점검", message: "보유 종목 한 개가 설정된 변동성 구간에 접근했습니다.", action: "리스크 확인" },
      ] },
      screener: { candidates: ["한화에어로스페이스", "현대일렉트릭", "두산에너빌리티", "삼성중공업", "HD현대중공업"].map((name, index) => ({ name, symbol: `00${index + 11}00`, score: 94 - index * 3, risk_gate_status: index === 4 ? "재확인" : "통과" })) },
      market: { quotes: ["삼성전자전자부품", "SK하이닉스", "한화에어로스페이스", "현대차", "두산에너빌리티"].map((name, index) => ({ name, symbol: `00${index + 1}00`, price: [74500, 182000, 903000, 287500, 59600][index], change_pct: [2.45, -1.21, 3.14, -0.74, 1.88][index] })) },
    };
  }

  global.CodexStockUiV2VisualFixture = { enabled, get };
})(window);
