(function () {
  "use strict";

  const STORAGE_KEY = "codexstock.workspace.subviews.v1";

  const PAGE_CONFIG = {
    dashboard: {
      label: "대시보드",
      groups: [
        group("summary", "오늘 요약", "지금 가장 먼저 확인할 핵심 상태입니다.", [".command-hero", ".user-compass-panel", ".metric-wall"], ["시장 상태와 오늘 할 일을 먼저 확인합니다.", "큰 버튼으로 다음 업무 화면으로 이동합니다."], "핵심 상태와 바로가기", "세부 분석은 다음 보기에서 확인하세요."),
        group("intelligence", "AI·외부지식", "AI 직원과 외부 정보가 정상적으로 일하는지 봅니다.", [".maturity-score-panel", ".ai-worker-strip", ".external-knowledge-panel"], ["AI 성숙도와 직원 상태를 확인합니다.", "외부 정보가 오래됐다는 경고가 있으면 새 보고서를 기다립니다."], "AI·외부엔진 상태", "외부 정보는 검증 전 매매 근거로 확정되지 않습니다."),
        group("account", "계좌·성과", "실전과 Paper 계좌, 손익과 최근 매매를 확인합니다.", [".account-dashboard-panel"], ["먼저 실전/Paper 탭을 확인합니다.", "손익보다 주문·체결·잔고 대사가 맞는지 먼저 봅니다."], "계좌·손익·매매 복기", "계좌 모드가 맞는지 확인한 뒤 수치를 읽으세요."),
        group("operations", "시장·운영", "시장 레이더, 임무, 전략, 리스크와 로그를 한곳에서 봅니다.", [".dashboard-grid"], ["시장 레이더와 오늘 임무를 확인합니다.", "오류가 있으면 리스크와 로그 카드를 확인합니다."], "운영 상태와 오류 원인", "빨간 경고가 있으면 주문보다 원인 해결이 먼저입니다."),
      ],
    },
    aiTrader: {
      label: "AI 트레이더",
      groups: [
        group("briefing", "장전 준비", "오늘 시장과 AI의 첫 판단을 확인합니다.", [":scope > .ai-hero", ":scope > .page-role-panel", ":scope > .page-action-guide", ":scope > .premarket-brief-panel"], ["장전 브리핑을 새로 불러옵니다.", "추천 종목으로 넘어가기 전에 시장 위험을 확인합니다."], "장전 브리핑과 첫 행동", "장전 자료는 개장 후 상황에 따라 달라질 수 있습니다."),
        group("autopilot", "자동운용", "자동운용 비중, 시장 국면, 경보와 보고 상태를 봅니다.", [":scope > .autopilot-panel", ":scope > .market-regime-panel", ":scope > .ai-alert-panel", ":scope > .telegram-dispatch-panel"], ["자동운용 비중과 실전 잠금 상태를 먼저 봅니다.", "시장 국면과 경보를 함께 확인합니다."], "자동운용·경보 상태", "권한 표시와 위험 게이트가 일치하지 않으면 실행하지 마세요."),
        group("staff", "직원·안전", "AI 직원이 무슨 일을 하고 있으며 안전 게이트가 통과됐는지 봅니다.", [":scope > .agent-daemon-panel", ":scope > .ai-staff-panel", ":scope > .ops-gate-panel"], ["직원 현재 작업과 최근 회의를 확인합니다.", "실전 후보는 안전 게이트의 차단 사유를 먼저 해소합니다."], "직원 작업·회의·안전 판정", "안전 게이트는 AI 의견보다 우선합니다."),
        group("work", "업무 기록", "AI 임무, 근무일지, 처리 흐름과 국내 시장 분석을 봅니다.", [":scope > .ai-mission-panel", ":scope > .ai-worklog-panel", ":scope > .ai-pipeline-panel", ":scope > .kr-market-panel", ":scope > .ai-grid", ":scope > section.panel:last-of-type"], ["오늘 임무와 처리 단계를 확인합니다.", "근무일지에서 판단 근거가 남았는지 확인합니다."], "업무 이력과 시장 분석", "기록이 없는 판단은 학습 근거로 사용하지 않습니다."),
      ],
    },
    recommendations: {
      label: "추천 종목",
      groups: [
        group("start", "사용 안내", "추천 화면의 의미와 올바른 확인 순서를 설명합니다.", [":scope > .recommendation-hero-panel", ":scope > .page-action-guide"], ["추천은 주문이 아니라 검토 후보라는 점을 확인합니다.", "업종부터 보고 종목으로 내려갑니다."], "추천 화면 사용 순서", "점수 하나만 보고 종목을 고르지 마세요."),
        group("selection", "업종·조건검색", "강한 업종과 조건을 통과한 종목을 좁힙니다.", [":scope > .sector-committee-panel", ":scope > .ai-screener-panel"], ["업종 편중 경고를 확인합니다.", "조건검색 결과의 데이터 시각과 출처를 확인합니다."], "업종 순위와 1차 후보", "오래된 시세 후보는 다음 단계로 넘기지 않습니다."),
        group("analysis", "후보 분석", "기회·기업보고서·레이더·뉴스를 함께 비교합니다.", [":scope > .opportunity-panel", ":scope > .ai-dossier-panel", ":scope > .ai-radar-panel", ":scope > .sector-news-panel"], ["후보의 재료와 반대 근거를 함께 읽습니다.", "AI 감독 화면에서 체결 가능성을 다시 확인합니다."], "후보별 근거와 위험", "뉴스 재료는 가격·공시·다중 출처 검증 후 사용합니다."),
      ],
    },
    trading: {
      label: "AI 감독·승인",
      groups: [
        group("market", "차트·판단", "종목 차트와 AI가 압축한 통합 판단을 한 화면에서 확인합니다.", [":scope > .trade-layout > .watchlist-panel", ":scope > .trade-layout > .chart-panel"], ["확인할 종목과 시세 시각을 선택합니다.", "AI 통합 판단에서 선정 이유와 반대 근거를 확인합니다.", "무효화 조건과 안전 게이트를 확인합니다."], "차트와 AI 판단 요약", "분봉·호가 원본은 AI 내부 검증에 사용되며, 이 화면은 실전 주문을 실행하지 않습니다."),
      ],
    },
    research: {
      label: "전략 연구",
      groups: [
        group("guide", "연구 안내", "전략 연구의 목적과 순서를 먼저 익힙니다.", [":scope > section:nth-of-type(1)", ":scope > section:nth-of-type(2)"], ["종목·기간·전략을 정합니다.", "검증 결과가 좋아도 곧바로 실전에 쓰지 않습니다."], "연구 절차", "백테스트 성과와 실전 성과는 다를 수 있습니다."),
        group("backtest", "백테스트·과거장", "전략 성과와 과거장 Paper 훈련을 실행합니다.", [":scope > section:nth-of-type(3)", ":scope > section:nth-of-type(4)"], ["비용과 기간을 확인한 뒤 실행합니다.", "수익률뿐 아니라 MDD·거래 수·체결 증거를 봅니다."], "성과·차트·과거장 기록", "과최적화와 생존편향을 별도 검증해야 합니다."),
        group("validation", "강건성 검증", "워크포워드, 스트레스, 보호장치와 다중 전략을 비교합니다.", [":scope > section:nth-of-type(5)", ":scope > section:nth-of-type(6)", ":scope > section:nth-of-type(7)", ":scope > section:nth-of-type(8)"], ["검증 센터의 경고부터 읽습니다.", "여러 구간에서 살아남는 전략만 연구 후보로 유지합니다."], "강건성·보호장치·비교 결과", "좋은 한 구간보다 여러 구간의 일관성을 우선하세요."),
        group("sources", "외부전략·후보", "외부 설명을 전략으로 옮겨 검증하고 후보를 관리합니다.", [":scope > section:nth-of-type(9)", ":scope > section:nth-of-type(10)", ":scope > section:nth-of-type(11)", ":scope > details"], ["외부 전략 원문과 변환 규칙을 확인합니다.", "저장 전 독립 검증 결과와 실패 이유를 기록합니다."], "외부전략 검증과 저장 후보", "출처가 유명해도 우리 데이터 검증을 통과해야 합니다."),
      ],
    },
    settings: {
      label: "설정·기록",
      groups: [
        group("overview", "설정 안내", "연구·운용·리스크 역할과 현재 환경을 설명합니다.", [":scope > .settings-hero-panel"], ["각 역할이 분리되어 있는지 확인합니다.", "비밀값은 화면에 직접 표시하지 않습니다."], "역할과 환경 안내", "설정 변경 전 현재 값을 기록하세요."),
        group("engines", "하위엔진", "10개 하위엔진의 연결·작업·진행률을 봅니다.", [":scope > .external-engine-ops-panel"], ["연결 수와 경고 수를 먼저 봅니다.", "사용 중인 엔진의 진행률과 예상 완료시간을 확인합니다."], "엔진 연결과 작업 상태", "하위엔진은 연구 결과만 반환하며 주문 권한이 없어야 합니다."),
        group("models", "AI 직원 모델", "운용·연구 직원이 사용할 AI 모델을 설정합니다.", [":scope > .staff-brain-settings-panel"], ["직원 역할에 맞는 모델을 선택합니다.", "저장 뒤 실제 적용 모델을 다시 확인합니다."], "직원별 모델 설정", "리스크 관리 규칙은 AI 모델과 별도로 항상 적용됩니다."),
        group("sharing", "소개·배포", "소개문과 친구용 안전 배포 패키지를 준비합니다.", [":scope > .program-intro-panel", ":scope > .friend-release-panel"], ["배포 준비도 검사를 먼저 실행합니다.", "API 키·계좌·개인 로그가 빠졌는지 확인합니다."], "소개문과 안전 배포 자료", "개인 데이터 폴더는 프로젝트 코드와 함께 배포하지 마세요."),
        group("records", "운영 기록", "리스크, API, 매매일지, AI 근무일지와 로그를 확인합니다.", [":scope > details.merged-workspace-panel"], ["고급 관리 상자를 펼칩니다.", "오류·매매·복기 기록을 날짜순으로 확인합니다."], "운영·감사 기록", "기록이 바뀌면 원본 시각과 생성 ID를 함께 확인하세요."),
      ],
    },
    capitalChallenge: {
      label: "장기 프로젝트",
      groups: [
        group("overview", "프로젝트 현황", "장기 훈련의 현재 위치와 핵심 결과를 봅니다.", [":scope > section:nth-of-type(1)", ":scope > section:nth-of-type(2)", ":scope > section:nth-of-type(3)"], ["최근 결과 보기를 먼저 누릅니다.", "수익률과 함께 MDD·남은 배수·실행 시각을 확인합니다."], "장기 목표 진행률", "높은 누적수익률만으로 전략 우수성을 판단하지 마세요."),
        group("phases", "구간별 훈련", "상승장·약세장 등 구간별 성과와 실패를 비교합니다.", [":scope > section:nth-of-type(4)"], ["취약한 장세를 찾습니다.", "필요한 구간만 다시 훈련합니다."], "장세별 성과와 교훈", "전체 평균이 좋아도 특정 장세 붕괴를 숨길 수 있습니다."),
        group("lab", "전략 탐색기", "여러 전략 조합을 비교해 깊게 검증할 후보를 찾습니다.", [":scope > section:nth-of-type(5)"], ["빠른 탐색으로 작동을 확인합니다.", "집중 탐색 후 위험효율과 MDD를 함께 비교합니다."], "상위 연구 후보", "탐색 순위는 실전 승인 순위가 아닙니다."),
        group("tournament", "왕중왕전·과제", "AI 직원 대회 결과와 다음 개선 과제를 확인합니다.", [":scope > section:nth-of-type(6)", ":scope > section:nth-of-type(7)"], ["같은 조건에서 직원별 결과를 비교합니다.", "진입·청산·비용 증거가 검증된 기록만 평가합니다."], "직원 전적과 개선 과제", "누적 수익률보다 CAGR·MDD·비용·검증 건수를 함께 보세요."),
      ],
    },
  };

  function group(id, label, description, selectors, steps, result, caution) {
    return { id, label, description, selectors, steps, result, caution };
  }

  function readSaved() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); } catch (_) { return {}; }
  }

  function save(pageId, groupId) {
    const saved = readSaved();
    saved[pageId] = groupId;
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(saved)); } catch (_) {}
  }

  function nodesFor(page, groupConfig) {
    const nodes = [];
    groupConfig.selectors.forEach((selector) => {
      page.querySelectorAll(selector).forEach((node) => {
        if (!nodes.includes(node)) nodes.push(node);
      });
    });
    return nodes;
  }

  function allManagedNodes(page, config) {
    const nodes = [];
    config.groups.forEach((item) => nodesFor(page, item).forEach((node) => {
      if (!nodes.includes(node)) nodes.push(node);
    }));
    return nodes;
  }

  function guideMarkup(item) {
    return `<div class="workspace-subview-guide-copy"><small>이 화면은 무엇인가요?</small><strong>${item.description}</strong></div>
      <ol>${item.steps.map((step) => `<li>${step}</li>`).join("")}</ol>
      <div class="workspace-subview-guide-result"><span><b>확인 결과</b>${item.result}</span><span><b>주의</b>${item.caution}</span></div>`;
  }

  function toolbarMarkup(config) {
    return `<div class="workspace-subview-main">
        <div class="workspace-view-menu">
          <button type="button" class="workspace-view-menu-trigger" data-instant-navigation="true" aria-haspopup="true" aria-expanded="false">메뉴 <span>▾</span></button>
          <div class="workspace-view-menu-popover" role="menu"></div>
        </div>
        <div class="workspace-subview-location"><small>${config.label}</small><strong data-subview-current>불러오는 중</strong><span data-subview-summary></span></div>
        <button type="button" class="workspace-subview-help" data-instant-navigation="true" aria-expanded="false">기능 설명</button>
      </div>
      <div class="workspace-subview-guide" hidden></div>`;
  }

  function ensureToolbar(pageId) {
    const page = document.getElementById(pageId);
    const host = document.getElementById("workspaceSubviewHost");
    const config = PAGE_CONFIG[pageId];
    if (!page || !host || !config) return null;
    let toolbar = host.querySelector(`:scope > .workspace-subview-nav[data-subview-page="${pageId}"]`);
    if (toolbar) return toolbar;
    toolbar = document.createElement("div");
    toolbar.className = "workspace-subview-nav";
    toolbar.classList.toggle("single-view", config.groups.length === 1);
    toolbar.dataset.subviewPage = pageId;
    toolbar.hidden = true;
    toolbar.setAttribute("aria-label", `${config.label} 하위 보기`);
    toolbar.innerHTML = toolbarMarkup(config);
    host.appendChild(toolbar);
    const popover = toolbar.querySelector(".workspace-view-menu-popover");
    config.groups.forEach((item, index) => {
      const menuButton = document.createElement("button");
      menuButton.type = "button";
      menuButton.dataset.instantNavigation = "true";
      menuButton.dataset.subview = item.id;
      menuButton.setAttribute("role", "menuitem");
      menuButton.innerHTML = `<span>${String(index + 1).padStart(2, "0")}</span><b>${item.label}</b>`;
      popover.appendChild(menuButton);
    });
    toolbar.querySelectorAll("button").forEach((button) => {
      delete button.dataset.runState;
      delete button.dataset.runStateLabel;
      button.removeAttribute("aria-busy");
    });
    toolbar.addEventListener("click", (event) => {
      const trigger = event.target.closest(".workspace-view-menu-trigger");
      if (trigger) {
        const open = toolbar.classList.toggle("menu-open");
        trigger.setAttribute("aria-expanded", String(open));
        if (open) requestAnimationFrame(() => positionPopover(toolbar));
        return;
      }
      const target = event.target.closest("[data-subview]");
      if (target) {
        select(pageId, target.dataset.subview, true);
        return;
      }
      const help = event.target.closest(".workspace-subview-help");
      if (help) {
        const guide = toolbar.querySelector(".workspace-subview-guide");
        guide.hidden = !guide.hidden;
        help.classList.toggle("active", !guide.hidden);
        help.setAttribute("aria-expanded", String(!guide.hidden));
        help.textContent = guide.hidden ? "기능 설명" : "설명 닫기";
      }
    });
    return toolbar;
  }

  function positionPopover(toolbar) {
    const trigger = toolbar?.querySelector(".workspace-view-menu-trigger");
    const popover = toolbar?.querySelector(".workspace-view-menu-popover");
    if (!trigger || !popover || !toolbar.classList.contains("menu-open")) return;
    const triggerRect = trigger.getBoundingClientRect();
    const width = Math.min(280, Math.max(220, window.innerWidth - 24));
    const left = Math.min(window.innerWidth - width - 12, Math.max(12, triggerRect.left));
    popover.style.width = `${width}px`;
    popover.style.left = `${left}px`;
    popover.style.right = "auto";
    popover.style.top = `${triggerRect.bottom + 8}px`;
    const popoverRect = popover.getBoundingClientRect();
    if (popoverRect.bottom > window.innerHeight - 12 && triggerRect.top > popoverRect.height + 12) {
      popover.style.top = `${triggerRect.top - popoverRect.height - 8}px`;
    }
  }

  function select(pageId, groupId, userInitiated) {
    const page = document.getElementById(pageId);
    const config = PAGE_CONFIG[pageId];
    const toolbar = ensureToolbar(pageId);
    if (!page || !config || !toolbar) return;
    const index = Math.max(0, config.groups.findIndex((item) => item.id === groupId));
    const active = config.groups[index];
    allManagedNodes(page, config).forEach((node) => node.classList.add("workspace-subview-hidden"));
    nodesFor(page, active).forEach((node) => node.classList.remove("workspace-subview-hidden"));
    page.dataset.activeSubview = active.id;
    toolbar.dataset.activeSubview = active.id;
    toolbar.querySelector("[data-subview-current]").textContent = active.label;
    toolbar.querySelector("[data-subview-summary]").textContent = active.description;
    toolbar.querySelector(".workspace-subview-guide").innerHTML = guideMarkup(active);
    toolbar.querySelectorAll("[data-subview]").forEach((button) => {
      const selected = button.dataset.subview === active.id;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-current", selected ? "page" : "false");
    });
    toolbar.classList.remove("menu-open");
    toolbar.querySelector(".workspace-view-menu-trigger").setAttribute("aria-expanded", "false");
    save(pageId, active.id);
    if (userInitiated) {
      window.dispatchEvent(new CustomEvent("codexstock:subviewchange", { detail: { pageId, subviewId: active.id, label: active.label } }));
    }
  }

  function activate(pageId) {
    const config = PAGE_CONFIG[pageId];
    if (!config) return;
    document.querySelectorAll("#workspaceSubviewHost > .workspace-subview-nav").forEach((toolbar) => {
      toolbar.hidden = toolbar.dataset.subviewPage !== pageId;
      if (toolbar.hidden) toolbar.classList.remove("menu-open");
    });
    const saved = readSaved()[pageId];
    const valid = config.groups.some((item) => item.id === saved) ? saved : config.groups[0].id;
    select(pageId, valid, false);
  }

  function init() {
    Object.keys(PAGE_CONFIG).forEach((pageId) => ensureToolbar(pageId));
    activate(document.querySelector(".page.active")?.id || "dashboard");
    if (document.body.dataset.subpagesBound === "1") return;
    document.body.dataset.subpagesBound = "1";
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".workspace-view-menu")) {
        document.querySelectorAll(".workspace-subview-nav.menu-open").forEach((toolbar) => {
          toolbar.classList.remove("menu-open");
          toolbar.querySelector(".workspace-view-menu-trigger")?.setAttribute("aria-expanded", "false");
        });
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      document.querySelectorAll(".workspace-subview-nav.menu-open").forEach((toolbar) => {
        toolbar.classList.remove("menu-open");
        toolbar.querySelector(".workspace-view-menu-trigger")?.setAttribute("aria-expanded", "false");
      });
    });
    window.addEventListener("resize", () => {
      document.querySelectorAll(".workspace-subview-nav.menu-open").forEach(positionPopover);
    });
  }

  window.CodexStockSubpages = { init, activate, select, config: PAGE_CONFIG };
})();
