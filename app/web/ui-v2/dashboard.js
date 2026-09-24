(function attachCodexStockUiV2(global) {
  "use strict";

  const REFRESH_MS = 30_000;
  const ACCOUNT_REFRESH_MS = 60_000;
  const state = { host: null, timer: 0, clockTimer: 0, accountAt: 0, account: null, signatures: new Map(), refreshing: false };
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
  const number = (value) => (value === null || value === undefined || value === "" || !Number.isFinite(Number(value)) ? null : Number(value));
  const money = (value) => number(value) === null ? "조회 대기" : `${Math.round(number(value)).toLocaleString("ko-KR")}원`;
  const signedMoney = (value) => number(value) === null ? "당일 정산 대기" : `${number(value) > 0 ? "+" : ""}${Math.round(number(value)).toLocaleString("ko-KR")}원`;
  const percent = (value) => number(value) === null ? "-" : `${number(value) > 0 ? "+" : ""}${number(value).toFixed(2)}%`;
  const compactTime = (value) => value ? String(value).replace("T", " ").slice(0, 16) : "최근 활동시간 미제공";
  const toneForNumber = (value) => number(value) > 0 ? "profit" : number(value) < 0 ? "loss" : "neutral";
  const hash = (value) => JSON.stringify(value);
  const TONE_CLASSES = ["v2-profit", "v2-loss", "v2-warning", "v2-danger", "v2-ok", "v2-muted", "v2-neutral", "v2-working"];
  const ICONS = { dashboard: "⌂", trader: "◌", candidates: "◇", approval: "✓", portfolio: "◒", research: "⌁", backtest: "◫", staff: "◎", journal: "▤", system: "◉", settings: "⚙", search: "⌕", bell: "◌" };

  async function readJson(path) {
    const response = await fetch(path, { headers: { Accept: "application/json" }, cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }

  async function readOptional(path) {
    try { return await readJson(path); } catch (error) { return { __error: "조회 실패" }; }
  }

  function navItem(icon, label, page) {
    return `<button type="button" data-v2-page="${page}" ${page === "dashboard" ? 'aria-current="page"' : ""}><span class="v2-nav-icon" aria-hidden="true">${ICONS[icon]}</span>${label}</button>`;
  }

  function mount() {
    const host = document.createElement("section");
    host.id = "codexstockUiV2";
    host.className = "v2-shell";
    host.innerHTML = `
      <aside class="v2-sidebar" aria-label="코덱스스톡 메뉴">
        <div class="v2-brand"><span class="v2-logo" aria-hidden="true">▥</span><div><strong>코덱스스톡</strong><small>AI 투자 운용실</small></div></div>
        <nav class="v2-nav">
          ${navItem("dashboard", "대시보드", "dashboard")}${navItem("trader", "AI 트레이더", "aiTrader")}${navItem("candidates", "후보/추천", "recommendations")}${navItem("approval", "매매 승인", "trading")}${navItem("portfolio", "포트폴리오", "trading")}${navItem("research", "전략 연구", "research")}${navItem("backtest", "백테스트", "research")}${navItem("staff", "AI 직원", "aiTrader")}${navItem("journal", "매매일지", "settings")}${navItem("system", "시스템 관제", "settings")}${navItem("settings", "설정", "settings")}
        </nav>
        <div class="v2-sidebar-foot"><span data-v2="mode">운용 모드 조회 중</span><small>v2는 읽기 전용 화면입니다.</small></div>
      </aside>
      <main class="v2-main">
        <header class="v2-topbar">
          <form class="v2-search" id="v2SearchForm" role="search"><span aria-hidden="true">${ICONS.search}</span><input id="v2SearchInput" autocomplete="off" placeholder="종목명, 코드로 기존 관심종목 검색" /><button type="submit">검색</button></form>
          <div class="v2-header-status"><div data-v2="marketState" class="v2-header-item">시장 상태 조회 중</div><div data-v2="marketSummary" class="v2-header-item muted">시장 요약 대기</div><div data-v2="aiState" class="v2-header-item">AI 상태 조회 중</div></div>
          <div class="v2-header-tools"><time data-v2="clock">--:--:--</time><button type="button" class="v2-icon-button" data-v2-page="settings" aria-label="알림"><span aria-hidden="true">${ICONS.bell}</span><b data-v2="alertCount" hidden>0</b></button></div>
        </header>
        <section class="v2-grid v2-kpis" aria-label="핵심 현황">
          <article class="v2-card v2-kpi"><span>총 자산</span><strong data-v2="totalAsset">조회 대기</strong><small data-v2="totalAssetMeta">계좌 상태 확인 중</small></article>
          <article class="v2-card v2-kpi"><span>오늘 실현 손익</span><strong data-v2="todayPnl">당일 정산 대기</strong><small data-v2="todayPnlMeta">체결 원장 기준</small></article>
          <article class="v2-card v2-kpi"><span>투자중 금액</span><strong data-v2="invested">조회 대기</strong><small data-v2="investedMeta">보유 종목 확인 중</small></article>
          <article class="v2-card v2-kpi v2-risk-card"><span>리스크 상태</span><strong data-v2="riskState">조회 대기</strong><small data-v2="riskMeta">운영 게이트 확인 중</small></article>
        </section>
        <section class="v2-grid v2-primary-grid">
          <article class="v2-card v2-asset-card"><div class="v2-section-head"><div><h1>자산 추이</h1></div></div><div class="v2-empty-chart"><strong>계좌 자산 시계열 데이터가 아직 없습니다.</strong><span>실제 계좌 히스토리 수집 후 표시됩니다.</span></div></article>
          <article class="v2-card v2-portfolio-card"><div class="v2-section-head"><div><h2>포트폴리오 현황</h2><p data-v2="portfolioMeta">계좌 데이터 대기</p></div><button class="v2-link" type="button" data-v2-page="trading">상세 보기</button></div><div class="v2-allocation"><div class="v2-donut" data-v2="donut"><span data-v2="positionCount">-</span></div><div class="v2-legend" data-v2="portfolioLegend"></div></div><div class="v2-table-scroll"><table class="v2-table"><thead><tr><th>종목</th><th>평가금액</th><th>비중</th><th>손익률</th></tr></thead><tbody data-v2="portfolioRows"></tbody></table></div></article>
          <article class="v2-card v2-staff-card"><div class="v2-section-head"><div><h2>AI 직원 상태</h2><p data-v2="staffMeta">직원 원장 대기</p></div><button class="v2-link" type="button" data-v2-page="aiTrader">전체 현황</button></div><div class="v2-staff-list" data-v2="staffRows"></div></article>
        </section>
        <section class="v2-grid v2-operations-grid">
          <article class="v2-card"><div class="v2-section-head"><h2>실시간 주요 종목</h2><button class="v2-link" type="button" data-v2-page="recommendations">전체 보기</button></div><div class="v2-table-scroll"><table class="v2-table"><thead><tr><th>종목</th><th>현재가</th><th>등락률</th></tr></thead><tbody data-v2="marketRows"></tbody></table></div></article>
          <article class="v2-card"><div class="v2-section-head"><h2>AI 추천 후보</h2><button class="v2-link" type="button" data-v2-page="recommendations">후보 보기</button></div><div class="v2-table-scroll"><table class="v2-table"><thead><tr><th>종목</th><th>점수</th><th>게이트</th></tr></thead><tbody data-v2="candidateRows"></tbody></table></div></article>
          <article class="v2-card v2-approval-card"><div class="v2-section-head"><h2>승인 필요 <b data-v2="approvalCount">-</b></h2><button class="v2-link" type="button" data-v2-page="trading">감독석 열기</button></div><div class="v2-table-scroll"><table class="v2-table"><thead><tr><th>유형</th><th>종목</th><th>상태</th><th>요청시간</th></tr></thead><tbody data-v2="approvalRows"></tbody></table></div></article>
          <article class="v2-card"><div class="v2-section-head"><h2>공지 및 시스템 알림</h2><button class="v2-link" type="button" data-v2-page="settings">전체 보기</button></div><div class="v2-alert-list" data-v2="alertRows"></div></article>
        </section>
      </main>`;
    document.body.append(host);
    host.querySelectorAll("[data-v2-page]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.v2Page)));
    host.querySelector("#v2SearchForm")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const query = host.querySelector("#v2SearchInput")?.value.trim();
      const legacyInput = document.querySelector("#watchlistInput");
      if (legacyInput && query) { legacyInput.value = query; legacyInput.dispatchEvent(new Event("input", { bubbles: true })); }
      navigate("recommendations");
    });
    state.host = host;
    return host;
  }

  function navigate(page) {
    document.querySelector(`.tab[data-page="${page}"]`)?.click();
    stop();
    document.body.dataset.uiV2 = "false";
    state.host?.remove();
    const nextUrl = new URL(global.location.href);
    nextUrl.searchParams.delete("ui");
    global.history.replaceState({}, "", nextUrl);
  }

  function text(name, value, className = "") {
    const node = state.host?.querySelector(`[data-v2="${name}"]`);
    if (!node) return;
    node.textContent = value;
    // Preserve layout classes while replacing only the semantic state color.
    TONE_CLASSES.forEach((tone) => node.classList.remove(tone));
    if (className) node.classList.add(`v2-${className}`);
  }

  function renderMarkup(name, markup, signature) {
    const node = state.host?.querySelector(`[data-v2="${name}"]`);
    if (!node || state.signatures.get(name) === signature) return;
    node.innerHTML = markup;
    state.signatures.set(name, signature);
  }

  function accountModel(account, ops) {
    const liveOk = Boolean(account?.ok && account?.summary);
    const paperAvailable = Boolean(!ops?.__error && ops?.paper && typeof ops.paper === "object");
    const paper = paperAvailable ? ops.paper : {};
    const summary = account?.summary || {};
    const positions = liveOk ? (Array.isArray(account.positions) ? account.positions : []) : (paperAvailable && Array.isArray(paper.positions) ? paper.positions : []);
    const cash = liveOk ? number(summary.available_cash ?? summary.cash) : (paperAvailable ? number(paper.cash) : null);
    const stockValue = liveOk ? number(summary.stock_value) : (paperAvailable ? number(paper.market_value) : null);
    const equity = liveOk ? number(summary.net_liquidation_value ?? summary.total_value) : (paperAvailable ? number(paper.equity) : null);
    const normalized = positions.map((row) => {
      const value = number(liveOk ? (row.evaluation_amount ?? row.value) : row.value) ?? 0;
      return { name: row.name || row.prdt_name || row.symbol || "종목명 미제공", symbol: row.symbol || "-", value, weight: equity && equity > 0 ? value / equity * 100 : null, pnlPct: number(liveOk ? row.profit_loss_rate : row.unrealized_pct) };
    }).filter((row) => row.value > 0);
    const mode = liveOk ? "실전 계좌 · KIS" : (paperAvailable ? "Paper 모의 계좌" : "계좌 상태 조회 실패");
    const reason = liveOk ? (account.readonly ? "KIS 읽기전용 잔고" : "KIS 잔고") : (paperAvailable ? "실계좌 자료 미확인, Paper 장부 표시" : "실계좌 및 Paper 장부를 불러오지 못했습니다.");
    return { mode, live: liveOk, cash, stockValue, equity, positions: normalized, updatedAt: liveOk ? account.generated_at : (paperAvailable ? ops?.generated_at : null), reason };
  }

  function renderHeader(model, clock, staff, alerts, market) {
    const kr = Array.isArray(clock?.sessions) ? clock.sessions.find((row) => row.id === "KR") : null;
    text("marketState", kr ? `${kr.name} ${kr.phase_label || kr.phase || "상태 미확인"}` : "한국장 상태 조회 실패", kr?.phase === "regular" ? "ok" : kr?.phase === "closed" ? "muted" : "warning");
    const quotes = Array.isArray(market?.quotes) ? market.quotes : [];
    text("marketSummary", quotes.length ? `관심종목 ${quotes.length}개 시세 수신` : "KOSPI/KOSDAQ 요약 데이터 미제공", quotes.length ? "muted" : "warning");
    const summary = staff?.summary || staff?.worker_board?.summary || {};
    text("aiState", staff?.__error ? "AI 상태 조회 실패" : `${Number(summary.working || 0)}명 작업 · ${Number(summary.attention || 0)}명 주의`, staff?.__error ? "danger" : Number(summary.attention || 0) ? "warning" : "ok");
    const totalAlerts = number(alerts?.summary?.total) ?? 0;
    const alertNode = state.host?.querySelector('[data-v2="alertCount"]');
    if (alertNode) { alertNode.textContent = String(totalAlerts); alertNode.hidden = totalAlerts <= 0; }
    text("mode", model.mode, model.live ? "danger" : (model.equity === null ? "warning" : "muted"));
  }

  function renderKpis(model, performance, ops) {
    const safety = ops?.safety || ops?.safety_state?.real_order || "운영 상태 미제공";
    const today = number(performance?.today_realized_gross_pnl);
    text("totalAsset", money(model.equity));
    text("totalAssetMeta", `${model.mode} · ${model.reason}`);
    text("todayPnl", signedMoney(today), toneForNumber(today));
    text("todayPnlMeta", performance?.__error ? "당일 실현 손익 조회 실패" : `체결 원장 기준 · ${Number(performance?.today_realized_count || 0)}건 정산`);
    text("invested", money(model.stockValue));
    text("investedMeta", model.positions.length ? `${model.positions.length}종목 · 현금 ${money(model.cash)}` : "보유 종목 없음 또는 계좌 자료 대기");
    const riskTone = /BLOCK|HALT|CONFLICT|REQUIRED|차단|정지|오류/i.test(safety) ? "danger" : /승인|주의|대기/i.test(safety) ? "warning" : "ok";
    text("riskState", safety, riskTone);
    text("riskMeta", `승인 대기 ${Number(ops?.approvals?.pending || 0)}건 · ${ops?.generated_at ? compactTime(ops.generated_at) : "갱신시간 미제공"}`);
  }

  function renderPortfolio(model) {
    const positions = model.positions;
    const palette = positions.map((_, index) => `var(--v2-chart-${index % 6 + 1})`);
    let cursor = 0;
    const slices = positions.map((item, index) => { const start = cursor; cursor += item.weight || 0; return `${palette[index]} ${start.toFixed(2)}% ${Math.min(cursor, 100).toFixed(2)}%`; });
    if (model.cash && model.equity && model.equity > 0) { const cashPct = Math.max(0, model.cash / model.equity * 100); const start = Math.min(cursor, 100); slices.push(`var(--v2-chart-cash) ${start.toFixed(2)}% ${Math.min(100, start + cashPct).toFixed(2)}%`); }
    const donut = state.host?.querySelector('[data-v2="donut"]');
    if (donut) donut.style.setProperty("--v2-donut", slices.length ? slices.join(", ") : "var(--v2-border) 0% 100%");
    text("positionCount", positions.length ? `${positions.length}종목` : "현금");
    text("portfolioMeta", `${model.mode} · ${model.updatedAt ? compactTime(model.updatedAt) : "갱신시간 미제공"}`);
    renderMarkup("portfolioLegend", positions.length ? positions.slice(0, 5).map((item, index) => `<div><i style="background:var(--v2-chart-${index % 6 + 1})"></i><span>${escapeHtml(item.name)}</span><b>${item.weight?.toFixed(1) || "-"}%</b></div>`).join("") : '<p class="v2-empty">보유 종목 데이터가 없습니다.</p>', hash(positions.map((row) => [row.symbol, row.value])));
    renderMarkup("portfolioRows", positions.length ? positions.map((item) => `<tr><td><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.symbol)}</small></td><td>${money(item.value)}</td><td>${item.weight?.toFixed(1) || "-"}%</td><td class="v2-${toneForNumber(item.pnlPct)}">${percent(item.pnlPct)}</td></tr>`).join("") : '<tr><td colspan="4" class="v2-empty-cell">보유 종목 데이터가 없습니다.</td></tr>', hash(positions));
  }

  function workerTone(worker) {
    const raw = `${worker.status || ""} ${worker.state || ""} ${worker.status_label || ""}`.toLowerCase();
    if (/error|fail|danger|장애|오류|failed/.test(raw)) return "danger";
    if (/warning|attention|watch|주의|대기/.test(raw)) return "warning";
    if (/working|running|작업|실행/.test(raw)) return "working";
    if (/normal|ready|active|정상|활성/.test(raw)) return "ok";
    return "muted";
  }

  function renderStaff(staff) {
    const board = staff?.worker_board || staff || {};
    const workers = Array.isArray(board.workers) ? board.workers : [];
    const summary = board.summary || {};
    text("staffMeta", staff?.__error ? "AI 직원 상태 조회 실패" : `활성 ${Number(summary.active || 0)}명 · 작업 ${Number(summary.working || 0)}명 · 주의 ${Number(summary.attention || 0)}명`);
    const markup = workers.length ? workers.map((worker) => {
      const tone = workerTone(worker);
      const label = worker.status_label || worker.state || worker.status || "상태 미제공";
      const task = worker.task || worker.current_task || worker.message || "현재 작업 정보 미제공";
      const activity = worker.updated_at || worker.last_activity_at || worker.last_run_at || worker.last_seen_at || "";
      const progress = number(worker.progress ?? worker.progress_pct);
      return `<article class="v2-worker"><div class="v2-worker-title"><strong>${escapeHtml(worker.name || worker.id || "이름 미제공")}</strong><span class="v2-state-pill v2-${tone}">${escapeHtml(label)}</span></div><p>${escapeHtml(task)}</p>${progress === null ? "" : `<div class="v2-progress"><i class="v2-${tone}" style="width:${Math.max(0, Math.min(100, progress))}%"></i></div>`}<small>${activity ? `최근 활동 ${escapeHtml(compactTime(activity))}` : "최근 활동시간 미제공"}</small></article>`;
    }).join("") : `<p class="v2-empty">${staff?.__error ? "AI 직원 상태를 불러오지 못했습니다." : "등록된 AI 직원 상태가 아직 없습니다."}</p>`;
    renderMarkup("staffRows", markup, hash(workers));
  }

  function renderMarket(market) {
    const rows = Array.isArray(market?.quotes) ? market.quotes : [];
    const markup = rows.length ? rows.slice(0, 6).map((row) => {
      const price = number(row.price ?? row.last);
      const change = number(row.change_pct ?? row.change);
      return `<tr><td><strong>${escapeHtml(row.name || row.symbol || "종목명 미제공")}</strong><small>${escapeHtml(row.symbol || "-")}</small></td><td>${money(price)}</td><td class="v2-${toneForNumber(change)}">${percent(change)}</td></tr>`;
    }).join("") : `<tr><td colspan="3" class="v2-empty-cell">${market?.__error ? "시세 조회 실패" : "실시간 주요 종목 데이터가 없습니다."}</td></tr>`;
    renderMarkup("marketRows", markup, hash(rows));
  }

  function renderCandidates(screener) {
    const rows = Array.isArray(screener?.candidates) ? screener.candidates : [];
    const markup = rows.length ? rows.slice(0, 6).map((row) => `<tr><td><strong>${escapeHtml(row.name || row.symbol || "후보명 미제공")}</strong><small>${escapeHtml(row.symbol || "-")}</small></td><td>${number(row.score) === null ? "-" : number(row.score).toFixed(1)}</td><td>${escapeHtml(row.risk_gate_status || row.gate || "게이트 미제공")}</td></tr>`).join("") : `<tr><td colspan="3" class="v2-empty-cell">${screener?.__error ? "추천 후보 조회 실패" : "추천 후보가 아직 없습니다."}</td></tr>`;
    renderMarkup("candidateRows", markup, hash(rows));
  }

  function renderApprovals(ops) {
    const approvals = Array.isArray(ops?.approvals?.recent) ? ops.approvals.recent : [];
    const pending = approvals.filter((row) => String(row.status || "").toLowerCase() === "pending");
    text("approvalCount", `${Number(ops?.approvals?.pending ?? pending.length)}`);
    state.host?.querySelector(".v2-approval-card")?.classList.toggle("v2-has-pending", pending.length > 0);
    const markup = pending.length ? pending.slice(0, 5).map((row) => `<tr><td>${escapeHtml(row.side || row.type || "승인")}</td><td><strong>${escapeHtml(row.name || row.symbol || "종목 미제공")}</strong></td><td>${escapeHtml(row.status || "대기")}</td><td>${escapeHtml(compactTime(row.created_at || row.requested_at))}</td></tr>`).join("") : '<tr><td colspan="4" class="v2-empty-cell">현재 승인 대기 항목이 없습니다.</td></tr>';
    renderMarkup("approvalRows", markup, hash(pending));
  }

  function renderAlerts(alerts) {
    const rows = Array.isArray(alerts?.alerts) ? alerts.alerts : [];
    const alertTone = (priority) => {
      const value = String(priority || "").toLowerCase();
      if (/critical|danger|error|high|긴급|위험|오류/.test(value)) return "danger";
      if (/warning|warn|medium|주의/.test(value)) return "warning";
      if (/opportunity|success|positive|기회/.test(value)) return "opportunity";
      return "info";
    };
    const markup = rows.length ? rows.slice(0, 4).map((row) => `<article class="v2-alert v2-${alertTone(row.priority)}"><strong>${escapeHtml(row.title || "알림")}</strong><p>${escapeHtml(row.message || row.category || "세부 내용 미제공")}</p><small>${escapeHtml(row.action || row.category || "-")}</small></article>`).join("") : `<p class="v2-empty">${alerts?.__error ? "시스템 알림을 불러오지 못했습니다." : "표시할 시스템 알림이 없습니다."}</p>`;
    renderMarkup("alertRows", markup, hash(rows));
  }

  function render(payload) {
    const model = accountModel(payload.account, payload.ops);
    renderHeader(model, payload.clock, payload.staff, payload.alerts, payload.market);
    renderKpis(model, payload.performance, payload.ops);
    renderPortfolio(model);
    renderStaff(payload.staff);
    renderMarket(payload.market);
    renderCandidates(payload.screener);
    renderApprovals(payload.ops);
    renderAlerts(payload.alerts);
  }

  async function refresh() {
    if (!state.host || state.refreshing) return;
    state.refreshing = true;
    try {
      const now = Date.now();
      const accountPromise = now - state.accountAt >= ACCOUNT_REFRESH_MS || !state.account ? readOptional("/api/kis/account") : Promise.resolve(state.account);
      const [ops, account, performance, staff, clock, alerts, screener, market] = await Promise.all([
        readOptional("/api/ops/status/poll"), accountPromise, readOptional("/api/ops/live-performance"), readOptional("/api/agent/staff/quick?ttl=60"), readOptional("/api/agent/market-clock"), readOptional("/api/agent/alerts"), readOptional("/api/agent/screener"), readOptional("/api/market?bars=1"),
      ]);
      if (!account.__error) { state.account = account; state.accountAt = now; }
      render({ ops, account, performance, staff, clock, alerts, screener, market });
    } finally { state.refreshing = false; }
  }

  function updateClock() { text("clock", new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })); }
  function start() { if (state.timer || state.clockTimer) return; updateClock(); refresh(); state.timer = global.setInterval(refresh, REFRESH_MS); state.clockTimer = global.setInterval(updateClock, 1_000); }
  function stop() { global.clearInterval(state.timer); global.clearInterval(state.clockTimer); state.timer = 0; state.clockTimer = 0; }

  global.CodexStockUiV2 = { mount, start, stop };
})(window);
