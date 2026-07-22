"use strict";

const STORAGE = {
  serverUrl: "codexstock.mobile.serverUrl",
  token: "codexstock.mobile.token",
  deviceName: "codexstock.mobile.deviceName",
  chat: "codexstock.mobile.chat.v1",
};

const state = {
  serverUrl: localStorage.getItem(STORAGE.serverUrl) || defaultServerUrl(),
  token: localStorage.getItem(STORAGE.token) || "",
  deviceName: localStorage.getItem(STORAGE.deviceName) || "내 휴대폰",
  connected: false,
  loadingCount: 0,
  loadedTabs: new Set(),
  chat: loadChat(),
};

const elements = Object.fromEntries(
  Array.from(document.querySelectorAll("[id]")).map((element) => [element.id, element])
);

function defaultServerUrl() {
  const servedByCodexStock = /^https?:$/.test(location.protocol) && location.pathname.includes("/mobile");
  return servedByCodexStock ? location.origin : "";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function cleanUrl(value) {
  const raw = String(value || "").trim().replace(/\/+$/, "");
  if (!raw) return "";
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error("PC 주소 형식이 올바르지 않습니다.");
  }
  const local = ["127.0.0.1", "localhost"].includes(parsed.hostname);
  if (parsed.protocol !== "https:" && !(local && parsed.protocol === "http:")) {
    throw new Error("휴대폰 연결은 HTTPS 주소만 허용합니다.");
  }
  return parsed.origin + parsed.pathname.replace(/\/+$/, "");
}

function beginLoading() {
  state.loadingCount += 1;
  elements.requestProgress.classList.remove("is-done");
  elements.requestProgress.classList.add("is-loading");
}

function endLoading() {
  state.loadingCount = Math.max(0, state.loadingCount - 1);
  if (state.loadingCount > 0) return;
  elements.requestProgress.classList.remove("is-loading");
  elements.requestProgress.classList.add("is-done");
  window.setTimeout(() => elements.requestProgress.classList.remove("is-done"), 320);
}

function showToast(message, error = false) {
  elements.toast.textContent = message;
  elements.toast.classList.toggle("is-error", error);
  elements.toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => elements.toast.classList.remove("is-visible"), 3300);
}

async function api(path, options = {}) {
  if (!state.serverUrl) throw new Error("PC 본체 주소를 먼저 연결하세요.");
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), options.timeout || 25000);
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token && !options.noAuth) headers.Authorization = `Bearer ${state.token}`;
  beginLoading();
  try {
    const response = await fetch(`${state.serverUrl}${path}`, {
      method: options.method || "GET",
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
      cache: "no-store",
    });
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) {
      state.connected = false;
      state.token = "";
      localStorage.removeItem(STORAGE.token);
      renderConnection();
      throw new Error("휴대폰 연결이 만료됐습니다. 새 연결 코드를 입력하세요.");
    }
    if (!response.ok) {
      throw new Error(payload.reply || payload.message || payload.error || `요청 실패 (${response.status})`);
    }
    return payload;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("PC 응답이 늦습니다. 본체와 네트워크 상태를 확인하세요.");
    throw error;
  } finally {
    window.clearTimeout(timeout);
    endLoading();
  }
}

function setText(id, value, fallback = "-") {
  if (elements[id]) elements[id].textContent = value === undefined || value === null || value === "" ? fallback : value;
}

function statusTone(value) {
  const text = String(value || "").toLowerCase();
  if (/incident|danger|error|failed|offline|blocked|정지|고장/.test(text)) return "bad";
  if (/warning|stale|delay|observ|확인|지연|주의/.test(text)) return "warn";
  if (/healthy|normal|connected|ready|monitoring|recovered|정상|가동/.test(text)) return "good";
  return "neutral";
}

function formatNumber(value, digits = 0) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? number.toLocaleString("ko-KR", { maximumFractionDigits: digits }) : "-";
}

function formatWon(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || !number) return "-";
  if (Math.abs(number) >= 1_000_000_000_000) return `${(number / 1_000_000_000_000).toFixed(1)}조`;
  if (Math.abs(number) >= 100_000_000) return `${(number / 100_000_000).toFixed(1)}억`;
  if (Math.abs(number) >= 10_000) return `${(number / 10_000).toFixed(1)}만`;
  return `${formatNumber(number)}원`;
}

function formatTime(value) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value).slice(-8);
  return parsed.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
}

function renderConnection(detail = "") {
  const connected = Boolean(state.connected && state.token);
  elements.connectionBanner.classList.toggle("is-connected", connected);
  elements.connectionBanner.classList.toggle("is-disconnected", !connected);
  setText("connectionTitle", connected ? "PC 본체 안전 연결" : "PC 본체 연결 필요");
  setText(
    "connectionDetail",
    detail || (connected ? `${state.deviceName} · 기기 토큰 인증` : "설정에서 PC 주소와 일회용 연결 코드를 입력하세요.")
  );
  elements.connectShortcut.textContent = connected ? "설정" : "연결";
}

function renderSummary(data) {
  const overall = data.overall || {};
  const focus = data.focus || {};
  const operations = data.operations || {};
  const executor = data.executor || {};
  const developer = data.developer || {};
  const staff = data.staff || {};
  const clock = data.market_clock || {};
  const flags = operations.flags || {};
  const stages = executor.stage_counts || {};

  state.connected = true;
  renderConnection(`마지막 응답 ${formatTime(data.generated_at)} · ${Math.round(Number(data.elapsed_ms || 0))}ms`);
  elements.heroCard.classList.remove("is-healthy", "is-warning", "is-danger");
  elements.heroCard.classList.add(overall.ok ? "is-healthy" : overall.system_healthy ? "is-warning" : "is-danger");
  setText("overallLabel", overall.label || "상태 확인 완료");
  setText(
    "overallMessage",
    overall.ok ? "본체·매매 파이프라인·외부 실행기가 함께 응답했습니다." : "일부 업무 흐름을 확인해야 합니다. 내부 개발자 상태를 보세요."
  );
  setText("marketPhase", clock.label || clock.phase || focus.market_phase || "대기");

  const trading = Math.max(0, Math.min(100, Number(focus.trading_focus_pct || 0)));
  const research = Math.max(0, Math.min(100, Number(focus.research_focus_pct || 0)));
  elements.focusFill.style.width = `${trading}%`;
  setText("tradingFocus", `${formatNumber(trading)}%`);
  setText("researchFocus", `${formatNumber(research)}%`);
  setText("focusMode", focus.label || focus.mode || "운영 모드");
  elements.focusMode.className = `status-pill ${statusTone(focus.mode || focus.label)}`;
  setText("focusReason", focus.reason || focus.current_task || "현재 우선 업무를 확인했습니다.");

  setText("operationMode", operations.mode || (flags.live_execution_enabled ? "완전자동" : "반자동"));
  setText(
    "capitalLimit",
    `총 ${formatNumber(operations.auto_submit_max_cash_pct)}% · 종목당 ${formatNumber(operations.max_position_cash_pct)}% · ${formatNumber(operations.target_symbol_count)}종목`
  );
  setText("executorState", executor.ok ? `${String(executor.mode || "").toUpperCase()} 가동` : "확인 필요");
  setText("executorDetail", `처리 ${formatNumber(executor.processed_total)} · 대기 ${formatNumber(executor.inbox_pending)}`);
  setText("pipelineState", executor.pipeline_state || (overall.trading_pipeline_healthy ? "정상 진행" : "확인 필요"));
  setText(
    "pipelineDetail",
    `후보 ${formatNumber(stages.candidate_tickets)} → 신호 ${formatNumber(stages.signed_signal_published)} → 결과 ${formatNumber(stages.executor_results)}`
  );
  setText("developerState", developer.label || developer.status || "감시 중");
  setText("developerDetail", developer.message || "현재 실제 장애가 없습니다.");

  const workers = Array.isArray(staff.workers) ? staff.workers : [];
  elements.staffList.innerHTML = workers.length
    ? workers.map((worker, index) => `
      <article class="staff-row">
        <span class="row-index">${String(index + 1).padStart(2, "0")}</span>
        <div class="row-copy">
          <strong>${escapeHtml(worker.name || worker.id || "AI 직원")}</strong>
          <p>${escapeHtml(worker.task || "상태 감시 중")}</p>
        </div>
        <span class="status-pill ${statusTone(worker.status)}">${escapeHtml(worker.status || "대기")}</span>
      </article>`).join("")
    : '<div class="empty-state">직원 상세 상태가 아직 기록되지 않았습니다.</div>';
}

async function loadSummary({ quiet = false } = {}) {
  if (!state.token || !state.serverUrl) {
    renderConnection();
    if (!quiet) elements.settingsDialog.showModal();
    return;
  }
  try {
    const data = await api("/api/mobile/summary");
    renderSummary(data);
    state.loadedTabs.add("home");
  } catch (error) {
    state.connected = false;
    renderConnection(error.message);
    if (!quiet) showToast(error.message, true);
  }
}

function renderCandidates(data) {
  const regime = data.market_regime || {};
  setText("regimeStrip", regime.headline || `${regime.stance || "시장 국면"} · 점수 ${formatNumber(regime.score, 1)}`);
  const rows = Array.isArray(data.candidates) ? data.candidates : [];
  elements.candidateList.innerHTML = rows.length
    ? rows.map((row, index) => {
      const price = row.price ? `${formatNumber(row.price)}원` : "가격 확인 필요";
      const reasons = (row.reasons || []).slice(0, 3).join(" · ") || row.next_action || "근거 확인 중";
      const risks = [...(row.risk_gate_failed || []), ...(row.risk_flags || [])].slice(0, 3).join(" · ");
      return `
        <article class="candidate-card">
          <span class="candidate-rank">${String(row.rank || index + 1).padStart(2, "0")}</span>
          <div class="candidate-head">
            <div><h3>${escapeHtml(row.name || row.symbol)}</h3><p>${escapeHtml(row.symbol)} · ${escapeHtml(row.market)}</p></div>
            <div class="candidate-score">${formatNumber(row.score, 2)}<small>점수</small></div>
          </div>
          <div class="candidate-facts">
            <span>${escapeHtml(row.action || "관찰")}</span>
            <span>${escapeHtml(row.trade_mode || row.lane || "구간 미정")}</span>
            <span>${escapeHtml(row.sector || "업종 확인")}</span>
            <span>${price}</span>
            <span>${Number(row.change_pct || 0) >= 0 ? "+" : ""}${formatNumber(row.change_pct, 2)}%</span>
            <span>거래대금 ${formatWon(row.amount)}</span>
          </div>
          <p class="candidate-reason">${escapeHtml(reasons)}</p>
          <p class="candidate-risk">${escapeHtml(risks ? `확인: ${risks}` : `게이트: ${row.risk_gate_status || "검토 중"}`)}</p>
        </article>`;
    }).join("")
    : '<div class="empty-state">현재 표시할 후보가 없습니다. 정상 관망인지 파이프라인 지연인지 홈 상태를 확인하세요.</div>';
}

async function loadCandidates() {
  try {
    const data = await api("/api/mobile/candidates?limit=8", { timeout: 35000 });
    renderCandidates(data);
    state.loadedTabs.add("candidates");
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderActivity(data) {
  const today = data.today || {};
  const counts = today.counts || {};
  const chips = [
    ["실전 전송", counts.live_submitted],
    ["차단", counts.live_blocked],
    ["실전 후보", counts.live_candidates],
    ["Dry-run", counts.dry_ready],
    ["모의체결", counts.paper_filled],
  ];
  elements.tradeCounts.innerHTML = chips.map(([label, value]) => `
    <div class="count-chip"><strong>${formatNumber(value)}</strong><span>${escapeHtml(label)}</span></div>`).join("");
  setText("tradeDate", today.date);
  setText("tradeHeadline", today.headline || "오늘 기록 없음");
  const groups = today.trades || {};
  const rows = [
    ...(groups.live_submitted || []).map((row) => ({ ...row, group: "실전" })),
    ...(groups.live_blocked || []).map((row) => ({ ...row, group: "차단" })),
    ...(groups.live_candidates || []).map((row) => ({ ...row, group: "후보" })),
    ...(groups.paper_filled || []).map((row) => ({ ...row, group: "모의" })),
  ];
  elements.tradeList.innerHTML = rows.length
    ? rows.slice(0, 18).map((row) => `
      <article class="timeline-row">
        <span class="timeline-side ${String(row.side).toLowerCase() === "buy" ? "buy" : "sell"}">${escapeHtml(row.group)}</span>
        <div class="row-copy">
          <strong>${escapeHtml(row.name || row.symbol || "기록")}${row.side ? ` · ${escapeHtml(row.side)}` : ""}</strong>
          <p>${formatNumber(row.quantity, 3)}주 · ${row.price ? `${formatNumber(row.price)}원` : "가격 -"} · ${escapeHtml(row.status || "")}</p>
          ${row.reason ? `<p>${escapeHtml(row.reason)}</p>` : ""}
        </div>
      </article>`).join("")
    : '<div class="empty-state">오늘 주문·후보 원장 기록이 없습니다.</div>';

  const alerts = Array.isArray(data.alerts) ? data.alerts : [];
  setText("alertCount", `${alerts.length}건`);
  elements.alertCount.className = `status-pill ${alerts.length ? "warn" : "good"}`;
  elements.alertList.innerHTML = alerts.length
    ? alerts.map((row) => `
      <article class="alert-row ${statusTone(row.level)}">
        <div class="row-copy">
          <strong>${escapeHtml(row.title)}</strong>
          <p>${escapeHtml(row.message || "")}</p>
          ${row.next_action ? `<p>다음: ${escapeHtml(row.next_action)}</p>` : ""}
        </div>
      </article>`).join("")
    : '<div class="empty-state">현재 표시할 중요 알림이 없습니다.</div>';
}

async function loadActivity() {
  try {
    const data = await api("/api/mobile/activity", { timeout: 35000 });
    renderActivity(data);
    state.loadedTabs.add("activity");
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderPortfolio(data) {
  const summary = data.summary || {};
  elements.portfolioSummary.innerHTML = `오늘 확정손익 <strong>${formatWon(summary.today_realized_gross_pnl)}</strong> · 누적 확정손익 <strong>${formatWon(summary.realized_gross_pnl)}</strong> · 보유 ${formatNumber(summary.open_position_count)}종목`;
  const rows = Array.isArray(data.positions) ? data.positions : [];
  elements.positionList.innerHTML = rows.length
    ? rows.map((row) => `
      <article class="position-row">
        <span class="row-index">${escapeHtml(row.symbol.slice(-2))}</span>
        <div class="row-copy">
          <strong>${escapeHtml(row.name || row.symbol)}</strong>
          <p>${formatNumber(row.quantity, 3)}주 · 평균 ${formatNumber(row.entry_price)}원 · 현재 ${formatNumber(row.current_price)}원</p>
        </div>
        <span class="status-pill ${Number(row.pnl_pct) >= 0 ? "good" : "bad"}">${Number(row.pnl_pct) >= 0 ? "+" : ""}${formatNumber(row.pnl_pct, 2)}%</span>
      </article>`).join("")
    : '<div class="empty-state">현재 모바일 요약에 표시할 보유 포지션이 없습니다.</div>';
}

async function loadPortfolio() {
  try {
    renderPortfolio(await api("/api/mobile/portfolio", { timeout: 35000 }));
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderEngines(data) {
  const rows = Array.isArray(data.engines) ? data.engines : [];
  const summary = data.summary || {};
  setText("engineSummary", summary.headline || summary.label || `연결된 하위엔진 ${rows.length}개`);
  elements.engineList.innerHTML = rows.length
    ? rows.map((row, index) => `
      <article class="engine-row">
        <span class="row-index">${String(index + 1).padStart(2, "0")}</span>
        <div class="row-copy"><strong>${escapeHtml(row.name)}</strong><p>${escapeHtml(row.role || row.detail || "전문 분석 엔진")}</p></div>
        <span class="status-pill ${statusTone(row.status || row.tone)}">${escapeHtml(row.status || "확인")}</span>
      </article>`).join("")
    : '<div class="empty-state">하위엔진 상세 상태가 없습니다.</div>';
}

async function loadEngines() {
  try {
    renderEngines(await api("/api/mobile/engines", { timeout: 45000 }));
  } catch (error) {
    showToast(error.message, true);
  }
}

function loadChat() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE.chat) || "[]");
    return Array.isArray(parsed) ? parsed.slice(-20) : [];
  } catch {
    return [];
  }
}

function renderChat() {
  if (!state.chat.length) return;
  elements.chatThread.innerHTML = state.chat.map((row) => `
    <article class="chat-message ${row.role === "user" ? "user" : "assistant"}">
      <span>${row.role === "user" ? "나" : "코덱스스톡 비서"}</span>
      <p>${escapeHtml(row.text)}</p>
    </article>`).join("");
  elements.chatThread.scrollTop = elements.chatThread.scrollHeight;
}

function addChat(role, text) {
  state.chat.push({ role, text: String(text || ""), at: new Date().toISOString() });
  state.chat = state.chat.slice(-20);
  localStorage.setItem(STORAGE.chat, JSON.stringify(state.chat));
  renderChat();
}

async function askAssistant(command) {
  const text = String(command || "").trim();
  if (!text) return;
  addChat("user", text);
  elements.chatInput.value = "";
  elements.chatInput.disabled = true;
  try {
    const context = state.chat.slice(-8).map((row) => `${row.role}: ${row.text}`).join("\n");
    const data = await api("/api/mobile/assistant", {
      method: "POST",
      body: { command: text, conversation_context: context },
      timeout: 60000,
    });
    addChat("assistant", data.reply || "답변을 만들지 못했습니다.");
  } catch (error) {
    addChat("assistant", `확인하지 못했습니다. ${error.message}`);
  } finally {
    elements.chatInput.disabled = false;
    elements.chatInput.focus();
  }
}

async function pairDevice() {
  try {
    const serverUrl = cleanUrl(elements.serverUrlInput.value);
    const code = elements.pairingCodeInput.value.replace(/\D/g, "");
    const deviceName = elements.deviceNameInput.value.trim() || "내 휴대폰";
    if (code.length !== 8) throw new Error("8자리 일회용 연결 코드를 입력하세요.");
    state.serverUrl = serverUrl;
    const health = await api("/api/mobile/health", { noAuth: true, timeout: 12000 });
    if (!health.ok) throw new Error("PC 모바일 서비스가 준비되지 않았습니다.");
    const paired = await api("/api/mobile/pair", {
      method: "POST",
      noAuth: true,
      timeout: 12000,
      body: { code, device_name: deviceName },
    });
    state.token = paired.token;
    state.deviceName = paired.device_name || deviceName;
    localStorage.setItem(STORAGE.serverUrl, state.serverUrl);
    localStorage.setItem(STORAGE.token, state.token);
    localStorage.setItem(STORAGE.deviceName, state.deviceName);
    elements.pairingCodeInput.value = "";
    elements.settingsDialog.close();
    showToast("PC 본체와 안전하게 연결했습니다.");
    await loadSummary();
  } catch (error) {
    showToast(error.message, true);
  }
}

function disconnectDevice() {
  state.token = "";
  state.connected = false;
  localStorage.removeItem(STORAGE.token);
  renderConnection("이 휴대폰의 저장 토큰을 삭제했습니다. PC 목록에서는 별도로 폐기할 수 있습니다.");
  elements.settingsDialog.close();
  showToast("이 휴대폰 연결을 해제했습니다.");
}

async function emergencyStop() {
  const confirmation = elements.emergencyConfirmInput.value.trim();
  if (confirmation !== "긴급정지") {
    showToast("확인란에 긴급정지를 정확히 입력하세요.", true);
    return;
  }
  try {
    const data = await api("/api/mobile/emergency-stop", {
      method: "POST",
      body: { confirmation },
      timeout: 30000,
    });
    elements.emergencyConfirmInput.value = "";
    elements.emergencyDialog.close();
    showToast(data.message || "신규 자동운용을 정지했습니다.");
    await loadSummary();
  } catch (error) {
    showToast(error.message, true);
  }
}

function activateTab(name) {
  document.querySelectorAll("[data-panel]").forEach((panel) => panel.classList.toggle("is-active", panel.dataset.panel === name));
  document.querySelectorAll("[data-tab]").forEach((button) => button.classList.toggle("is-active", button.dataset.tab === name));
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (!state.token || state.loadedTabs.has(name)) return;
  if (name === "candidates") loadCandidates();
  if (name === "activity") loadActivity();
}

function openSettings() {
  elements.serverUrlInput.value = state.serverUrl;
  elements.deviceNameInput.value = state.deviceName;
  elements.settingsDialog.showModal();
}

function bindEvents() {
  elements.settingsButton.addEventListener("click", openSettings);
  elements.connectShortcut.addEventListener("click", openSettings);
  elements.pairButton.addEventListener("click", pairDevice);
  elements.disconnectButton.addEventListener("click", disconnectDevice);
  elements.engineRefresh.addEventListener("click", loadEngines);
  elements.portfolioRefresh.addEventListener("click", loadPortfolio);
  elements.emergencyButton.addEventListener("click", () => elements.emergencyDialog.showModal());
  elements.confirmEmergencyButton.addEventListener("click", emergencyStop);
  elements.chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    askAssistant(elements.chatInput.value);
  });
  elements.chatInput.addEventListener("input", () => {
    elements.chatInput.style.height = "auto";
    elements.chatInput.style.height = `${Math.min(112, elements.chatInput.scrollHeight)}px`;
  });
  document.querySelectorAll("[data-tab]").forEach((button) => button.addEventListener("click", () => activateTab(button.dataset.tab)));
  document.querySelectorAll("[data-refresh]").forEach((button) => button.addEventListener("click", () => {
    if (button.dataset.refresh === "summary") loadSummary();
    if (button.dataset.refresh === "candidates") loadCandidates();
    if (button.dataset.refresh === "activity") loadActivity();
  }));
  document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => askAssistant(button.dataset.prompt)));
  window.addEventListener("online", () => loadSummary({ quiet: true }));
  window.addEventListener("offline", () => {
    state.connected = false;
    renderConnection("휴대폰 네트워크가 끊겼습니다.");
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) loadSummary({ quiet: true });
  });
}

function startClock() {
  const render = () => setText("clockText", new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }));
  render();
  window.setInterval(render, 1000);
}

async function boot() {
  bindEvents();
  renderConnection();
  renderChat();
  startClock();
  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
  if (state.token && state.serverUrl) await loadSummary({ quiet: true });
  else window.setTimeout(openSettings, 320);
  window.setInterval(() => {
    if (!document.hidden && state.token) loadSummary({ quiet: true });
  }, 15000);
}

boot();
