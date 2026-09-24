(function attachCodexStockUiV2(global) {
  "use strict";

  const sourceText = (selector, fallback = "조회 대기") => {
    const node = document.querySelector(selector);
    const value = node?.textContent?.trim();
    return value || fallback;
  };

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);

  const sourceRows = (selector, limit = 5) => [...document.querySelectorAll(selector)]
    .slice(0, limit)
    .map((row) => row.textContent.replace(/\s+/g, " ").trim())
    .filter(Boolean);

  function valueTone(value) {
    if (/[-▼]|손실/.test(value)) return "v2-loss";
    if (/[+▲]|수익/.test(value)) return "v2-profit";
    return "";
  }

  function listMarkup(rows, emptyText) {
    if (!rows.length) return `<p class="v2-empty">${escapeHtml(emptyText)}</p>`;
    return `<div class="v2-list">${rows.map((row) => `<div class="v2-row"><strong>${escapeHtml(row)}</strong></div>`).join("")}</div>`;
  }

  function kpi(label, value, detail, extraClass = "") {
    return `<article class="v2-card ${extraClass}"><div class="v2-label">${label}</div><div class="v2-value ${valueTone(value)}">${escapeHtml(value)}</div><div class="v2-detail">${escapeHtml(detail)}</div></article>`;
  }

  function navigate(page) {
    const target = document.querySelector(`.tab[data-page="${page}"]`);
    target?.click();
    document.body.dataset.uiV2 = "false";
    document.querySelector("#codexstockUiV2")?.remove();
    const nextUrl = new URL(global.location.href);
    nextUrl.searchParams.delete("ui");
    global.history.replaceState({}, "", nextUrl);
  }

  function mount() {
    const host = document.createElement("section");
    host.id = "codexstockUiV2";
    host.className = "v2-shell";
    host.innerHTML = `
      <aside class="v2-sidebar" aria-label="코덱스스톡 메뉴">
        <div class="v2-brand"><strong>코덱스스톡</strong><span>AI가 만드는 더 나은 투자</span></div>
        <nav class="v2-nav">
          <button type="button" aria-current="page" data-v2-page="dashboard">대시보드</button>
          <button type="button" data-v2-page="aiTrader">AI 트레이더</button>
          <button type="button" data-v2-page="recommendations">후보/추천</button>
          <button type="button" data-v2-page="trading">매매 승인</button>
          <button type="button" data-v2-page="research">전략 연구</button>
          <button type="button" data-v2-page="settings">시스템 관제</button>
        </nav>
      </aside>
      <main class="v2-main">
        <header class="v2-topbar"><div><h1>대시보드</h1><p>자산, 위험, 승인, AI 상태를 우선 확인합니다.</p></div><strong class="v2-state" data-v2="system">상태 조회 중</strong></header>
        <section class="v2-grid v2-kpis" data-v2="kpis"></section>
        <section class="v2-grid v2-content" data-v2="content"></section>
        <section class="v2-grid v2-bottom" data-v2="bottom"></section>
      </main>`;
    document.body.append(host);
    host.querySelectorAll("[data-v2-page]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.v2Page)));
    return host;
  }

  function render(host) {
    const equity = sourceText("#dashEquity", sourceText("#accountTotalValue"));
    const profit = sourceText("#accountPnlValue", "오늘 손익 조회 대기");
    const invested = sourceText("#accountStockValue", sourceText("#marketValue"));
    const risk = sourceText("#dashRisk", sourceText("#riskLine"));
    const state = sourceText("#suiteStatus", "시스템 상태 조회 중");
    host.querySelector('[data-v2="system"]').textContent = state;
    host.querySelector('[data-v2="kpis"]').innerHTML = [
      kpi("총 자산", equity, sourceText("#accountSubValue", "실제/훈련 계좌 상태 확인 중")),
      kpi("오늘 손익", profit, sourceText("#accountDashboardState", "계좌 조회 기준")),
      kpi("투자중 금액", invested, sourceText("#accountPositionCount", "보유 종목 확인 중")),
      kpi("리스크 상태", risk, sourceText("#riskLine", "리스크 한도 확인 중"), "v2-warning"),
    ].join("");

    const positions = sourceRows("#accountPositionRows > *", 6);
    const workers = sourceRows("#aiStaffQuickList > *, #aiStaffMeetingList > *", 4);
    host.querySelector('[data-v2="content"]').innerHTML = `
      <article class="v2-card"><div class="v2-section-head"><h2>포트폴리오 현황</h2><button class="v2-link" data-v2-page="trading">상세 보기</button></div>${listMarkup(positions, "현재 포트폴리오 데이터를 기다리고 있습니다.")}</article>
      <article class="v2-card"><div class="v2-section-head"><h2>AI 직원 상태</h2><button class="v2-link" data-v2-page="aiTrader">전체 현황</button></div>${workers.length ? `<div class="v2-list">${workers.map((worker) => `<div class="v2-worker"><strong>${escapeHtml(worker)}</strong><span class="v2-ok">정상/확인</span><small>기존 AI 상태 원장을 기준으로 표시</small></div>`).join("")}</div>` : '<p class="v2-empty">AI 직원 상태를 기다리고 있습니다.</p>'}</article>`;

    const market = sourceRows("#dashboardMarketRows > *, #watchlistRows > *", 5);
    const candidates = sourceRows("#candidateRows > *, #recommendationList > *", 5);
    const approvals = sourceRows("#approvalRows > *, #approvalQueue > *", 4);
    host.querySelector('[data-v2="bottom"]').innerHTML = `
      <article class="v2-card"><div class="v2-section-head"><h2>실시간 주요 종목</h2><button class="v2-link" data-v2-page="recommendations">전체 보기</button></div>${listMarkup(market, "시장 종목 데이터를 기다리고 있습니다.")}</article>
      <article class="v2-card"><div class="v2-section-head"><h2>AI 추천 후보</h2><button class="v2-link" data-v2-page="recommendations">후보 보기</button></div>${listMarkup(candidates, "추천 후보 데이터를 기다리고 있습니다.")}</article>
      <article class="v2-card v2-warning"><div class="v2-section-head"><h2>승인 필요</h2><button class="v2-link" data-v2-page="trading">감독석 열기</button></div>${listMarkup(approvals, "현재 승인 대기 항목이 없습니다.")}</article>`;
    host.querySelectorAll("[data-v2-page]").forEach((button) => {
      if (!button.dataset.bound) {
        button.dataset.bound = "true";
        button.addEventListener("click", () => navigate(button.dataset.v2Page));
      }
    });
  }

  global.CodexStockUiV2 = { mount, render };
})(window);
