(function attachExternalEngineDashboard(global) {
  "use strict";

  const IMPROVEMENT_PHASE_LABELS = Object.freeze({
    prepare_common_snapshot: "공통 데이터 고정",
    openbb_crosscheck: "OpenBB 교차검증",
    lean_market_lifecycle: "Lean 시장 생애주기 검증",
    vectorbt_portfolio_scenarios: "vectorbt 포트폴리오 시나리오",
    qlib_rolling_model_comparison: "Qlib 롤링 OOS 모델 비교",
    nautilus_execution_stress: "Nautilus 체결 스트레스",
    persist_verified_lessons: "검증 교훈·재훈련 기록",
  });

  function improvementStatusLabel(state = {}) {
    return {
      IDLE: "대기",
      RUNNING: "검증 중",
      COMPLETED: "완료",
      COMPLETED_WITH_BLOCKERS: "보완 과제와 함께 완료",
      FAILED: "실패",
    }[state.status] || String(state.status || "대기");
  }

  function reconcileEngineDashboardWithImprovement(payload = {}, improvement = {}) {
    const state = improvement.state || {};
    if (!["COMPLETED", "COMPLETED_WITH_BLOCKERS"].includes(String(state.status || ""))) return payload;
    const resultByEngine = new Map(
      (Array.isArray(state.engine_results) ? state.engine_results : [])
        .map((row) => [String(row.engine_id || "").toLowerCase(), row]),
    );
    const engineAliases = Object.freeze({
      vectorbt: "vectorbt",
      nautilustrader: "nautilus",
      "quantconnect-lean": "lean",
      openbb: "openbb",
      qlib: "qlib",
    });
    const engines = (Array.isArray(payload.engines) ? payload.engines : []).map((engine) => {
      const improvementId = engineAliases[String(engine.engine_id || "").toLowerCase()];
      const result = resultByEngine.get(improvementId);
      if (result?.execution_ok !== true || result?.contract_passed !== true) return engine;
      return {
        ...engine,
        status: engine.in_use ? "running" : "ready",
        status_label: "실행 검증 완료·온디맨드 대기",
        connected: true,
        runtime_connected: true,
        formal_connected: true,
        adapter_ready: true,
        round_trip_verified: true,
        success_evidence_fresh: true,
        current_usable: true,
        connection_truth: {
          runtime_connected: true,
          round_trip_verified: true,
          proof_fresh: true,
          current_usable: true,
          formal_connected: true,
        },
        connection_stage: "formal_connected",
        connection_proof_type: "verified_improvement_cycle_round_trip",
        operational_state: "normal",
        operational_state_label: "정상",
        progress_pct: 100,
        progress_label: "실제 입력·출력 왕복 계약 통과",
        current_task: "검증 요청 대기",
        eta_label: "요청 시 즉시 실행",
        last_success_at: state.finished_at || engine.last_success_at,
        last_job_success_at: state.finished_at || engine.last_job_success_at,
        health_note: result.quality_gate_passed === false
          ? "엔진 연결은 정상입니다. 최신 연구 결과는 품질 기준 미달로 후보점수·자동승격에서 차단했습니다."
          : engine.health_note,
      };
    });
    const summary = {
      ...(payload.summary || {}),
      engine_count: engines.length,
      connected_count: engines.filter((row) => row.runtime_connected ?? row.connected).length,
      runtime_connected_count: engines.filter((row) => row.runtime_connected ?? row.connected).length,
      adapter_connected_count: engines.filter((row) => row.runtime_connected ?? row.connected).length,
      formal_connected_count: engines.filter((row) => row.formal_connected).length,
      adapter_ready_count: engines.filter((row) => row.adapter_ready).length,
      round_trip_verified_count: engines.filter((row) => row.round_trip_verified).length,
      fresh_round_trip_count: engines.filter((row) => row.success_evidence_fresh).length,
      current_usable_count: engines.filter((row) => row.current_usable).length,
      error_count: engines.filter((row) => row.status === "error").length,
      warning_count: engines.filter((row) => row.status === "warning").length,
      operational_counts: {
        normal: engines.filter((row) => row.operational_state === "normal").length,
        delayed: engines.filter((row) => row.operational_state === "delayed").length,
        verification_pending: engines.filter((row) => row.operational_state === "verification_pending").length,
        broken: engines.filter((row) => row.operational_state === "broken").length,
      },
    };
    return { ...payload, engines, summary };
  }

  function renderImprovement(payload = {}, deps = {}) {
    const { setText, el, formatDateTimeShort, escapeHtml } = deps;
    const state = payload.state || {};
    const lessons = Array.isArray(payload.latest_verified_lessons) ? payload.latest_verified_lessons : [];
    const tasks = Array.isArray(payload.latest_retraining_tasks) ? payload.latest_retraining_tasks : [];
    const resolution = state.retraining_resolution && typeof state.retraining_resolution === "object"
      ? state.retraining_resolution
      : {};
    const resolvedTasks = Array.isArray(resolution.resolved) ? resolution.resolved : [];
    const retryTasks = Array.isArray(resolution.retry_queued) ? resolution.retry_queued : [];
    const exhaustedTasks = Array.isArray(resolution.exhausted) ? resolution.exhausted : [];
    const activeStatuses = new Set(["QUEUED", "CLAIMED", "RETRY_QUEUED"]);
    const resolutionActiveCount = Number(resolution.active_count);
    const hasResolutionActiveCount = Number.isFinite(resolutionActiveCount);
    const activeTasks = Array.isArray(payload.active_retraining_tasks)
      ? payload.active_retraining_tasks
      : hasResolutionActiveCount && resolutionActiveCount === 0
        ? []
        : tasks.filter((task) => activeStatuses.has(String(task.status || "")));
    const outcomeByEngine = new Map(
      [...resolvedTasks, ...retryTasks, ...exhaustedTasks]
        .map((task) => [String(task.engine_id || "").toLowerCase(), task]),
    );
    const activeEngineIds = new Set(activeTasks.map((task) => String(task.engine_id || "").toLowerCase()));
    const engineResults = Array.isArray(state.engine_results) ? state.engine_results : [];
    const progress = Math.max(0, Math.min(100, Number(state.progress_pct || 0)));
    const phaseCount = Math.max(5, Number(state.phase_count || 5));
    const phaseIndex = Math.max(0, Math.min(phaseCount, Number(state.phase_index || 0)));
    const running = payload.thread_alive === true || state.status === "RUNNING" || state.status === "FINALIZING";
    const statusLabel = improvementStatusLabel(state);
    const phaseLabel = IMPROVEMENT_PHASE_LABELS[state.phase] || state.phase || "실행 대기";

    setText("externalImprovementStatus", statusLabel);
    setText("externalImprovementPhase", phaseLabel);
    setText("externalImprovementStep", `${phaseIndex}/${phaseCount}`);
    setText("externalImprovementContractPass", Number(state.contract_pass_count || 0).toLocaleString());
    setText("externalImprovementQualityPass", Number(state.quality_pass_count || 0).toLocaleString());
    setText("externalImprovementLessonCount", lessons.length.toLocaleString());
    setText(
      "externalImprovementRetrainingCount",
      Number(state.active_retraining_task_count ?? activeTasks.length).toLocaleString(),
    );
    setText("externalImprovementProgressText", `${Math.round(progress)}%`);
    setText(
      "externalImprovementUpdatedAt",
      state.finished_at
        ? `마지막 완료 ${formatDateTimeShort(state.finished_at)}`
        : state.started_at
          ? `시작 ${formatDateTimeShort(state.started_at)}`
          : "실행 기록 대기",
    );

    const root = el("#externalImprovementLoop");
    if (root) {
      root.classList.toggle("running", running);
      root.classList.toggle("blocked", state.status === "COMPLETED_WITH_BLOCKERS" || state.status === "FAILED");
    }
    const meter = el("#externalImprovementMeterFill");
    if (meter) meter.style.width = `${progress}%`;
    const progressBar = el("#externalImprovementMeter");
    if (progressBar) progressBar.setAttribute("aria-valuenow", String(Math.round(progress)));
    const runButton = el("#runExternalImprovement");
    if (runButton) {
      runButton.disabled = running;
      runButton.textContent = running ? "검증 진행 중" : "전략 개선 1회 실행";
    }

    const resultGrid = el("#externalImprovementEngineResults");
    if (resultGrid) {
      const engineOrder = ["openbb", "lean", "vectorbt", "qlib", "nautilus"];
      const resultByEngine = new Map(engineResults.map((row) => [String(row.engine_id || "").toLowerCase(), row]));
      resultGrid.innerHTML = engineOrder.map((engineId) => {
        const result = resultByEngine.get(engineId);
        const outcome = outcomeByEngine.get(engineId);
        const passed = result?.contract_passed === true && result?.quality_gate_passed === true;
        const failed = Boolean(result) && !passed;
        const stateClass = passed ? "passed" : failed ? "failed" : running ? "pending" : "idle";
        const label = passed
          ? "교훈 반영 가능"
          : outcome?.status === "EXHAUSTED"
            ? "품질 미달 · 3회 종료"
            : activeEngineIds.has(engineId)
              ? "재훈련 대기"
              : failed
                ? "품질 미달 · 점수 차단"
                : running
                  ? "차례 대기"
                  : "미실행";
        return `<span class="${stateClass}"><b>${escapeHtml(engineId)}</b>${escapeHtml(label)}</span>`;
      }).join("");
    }

    const lessonSummary = el("#externalImprovementLessonSummary");
    if (lessonSummary) {
      const latest = lessons[0] || {};
      const corroborated = latest.strategy_corroborated === true;
      lessonSummary.textContent = lessons.length
        ? `${latest.quality_pass_count || 0}개 품질 통과 · 독립 전략검증 ${corroborated ? "일치" : "미일치"} · 후보점수 영향 ${Number(latest.candidate_score_delta || 0).toFixed(1)}점`
        : "아직 장기기억에 넣을 검증 교훈이 없습니다.";
    }
    const taskSummary = el("#externalImprovementTaskSummary");
    if (taskSummary) {
      taskSummary.textContent = activeTasks.length
        ? `${activeTasks.length}개 보완 과제가 다음 검증 주기에 자동 재투입됩니다.`
        : exhaustedTasks.length
          ? `${exhaustedTasks.length}개 품질 미달 과제는 3회 검증 후 종료됐습니다. 데이터나 조건이 달라지면 다시 생성됩니다.`
          : "현재 재훈련 대기 과제가 없습니다.";
    }
  }

  function render(payload = {}, deps = {}) {
    const { setText, el, formatDateTimeShort, escapeHtml, koreanStatusText } = deps;
    const summary = payload.summary || {};
    const engines = Array.isArray(payload.engines) ? payload.engines : [];
    setText("externalEngineTotal", Number(summary.engine_count || engines.length || 0).toLocaleString());
    setText("externalEngineActive", Number(summary.in_use_count || 0).toLocaleString());
    setText("externalEngineAdapterReady", Number(summary.adapter_ready_count || 0).toLocaleString());
    setText("externalEngineRoundTrip", Number(summary.fresh_round_trip_count || 0).toLocaleString());
    setText("externalEngineConnected", Number(summary.connected_count || 0).toLocaleString());
    setText("externalEngineErrors", Number(summary.error_count || 0).toLocaleString());
    setText("externalEnginePersistent", Number(summary.persistent_heavy_engine_count || 0).toLocaleString());
    setText(
      "externalEngineUpdatedAt",
      payload.generated_at ? `최근 확인 ${formatDateTimeShort(payload.generated_at)}` : "최근 확인 대기",
    );
    const grid = el("#externalEngineGrid");
    if (!grid) return;
    if (!engines.length) {
      grid.innerHTML = `
        <article class="external-engine-loading">
          <strong>등록된 외부 엔진이 없습니다</strong>
          <span>엔진 계약과 연결 상태를 다시 확인합니다.</span>
        </article>`;
      return;
    }
    grid.innerHTML = engines.map((engine) => {
      const progress = Math.max(0, Math.min(100, Number(engine.progress_pct || 0)));
      const statusClass = ["running", "watching", "preparing", "ready", "idle", "error"].includes(engine.status)
        ? engine.status
        : "idle";
      const taskPrefix = engine.in_use ? "LIVE JOB" : engine.status === "watching" ? "MONITOR" : "STANDBY";
      const lastActivity = engine.last_activity_at ? formatDateTimeShort(engine.last_activity_at) : "작업 기록 없음";
      const executionPolicy = {
        spawn_on_demand_only: "완전 온디맨드: 요청할 때만 실행",
        lightweight_status_resident_heavy_jobs_on_demand: "가벼운 상태 확인 상주 · 무거운 연구는 요청 시 실행",
        lightweight_file_poller_resident_scan_on_demand: "가벼운 보고서 수신 상주 · 긴 탐색은 요청 시 실행",
        optional_read_only_gateway_manual_start: "선택형 조회 게이트웨이 · 수동 시작 · 주문 차단",
      }[engine.execution_policy] || "실행 정책 확인 대기";
      const operationalLabel = engine.operational_state_label || "확인중";
      const lastSuccess = engine.last_success_at ? formatDateTimeShort(engine.last_success_at) : "성공 기록 없음";
      const connectionLabel = engine.connected
        ? engine.success_evidence_fresh
          ? "연결 완료·최근 검증 정상"
          : "연결 완료·최근 검증 지연"
        : engine.round_trip_verified
          ? "왕복 이력 있음·현재 연결 끊김"
          : engine.adapter_ready
            ? "설치·어댑터 준비·왕복 미검증"
            : "연결 준비 중";
      return `
        <article class="external-engine-card ${escapeHtml(statusClass)}" data-external-engine="${escapeHtml(engine.engine_id || "engine")}">
          <div class="external-engine-card-head">
            <div class="external-engine-identity">
              <strong>${escapeHtml(engine.display_name || engine.engine_name || "외부 엔진")}</strong>
              <span>${escapeHtml(engine.role_label || "검증 하위엔진")}</span>
            </div>
            <span class="external-engine-status">${escapeHtml(engine.status_label || "대기")}</span>
          </div>
          <div class="external-engine-description">${escapeHtml(engine.description || "외부 검증 작업을 수행합니다.")}</div>
          ${Array.isArray(engine.specialist_groups) && engine.specialist_groups.length ? `
            <div class="external-engine-specialists">
              ${engine.specialist_groups.map((group) => `
                <div><b>${escapeHtml(group.label || "구분")}</b><strong>${escapeHtml(group.engines || "-")}</strong><span>${escapeHtml(group.purpose || "")}</span></div>
              `).join("")}
            </div>
          ` : ""}
          ${engine.health_note ? `<div class="external-engine-health-note">${escapeHtml(engine.health_note)}</div>` : ""}
          <div class="external-engine-runtime-policy">
            <b>${engine.heavy_compute_policy === "on_demand_only" ? "ON-DEMAND" : "CHECK"}</b>
            <span>${escapeHtml(executionPolicy)}</span>
          </div>
          <div class="external-engine-runtime-policy">
            <b>LINK</b>
            <span>${escapeHtml(connectionLabel)}</span>
          </div>
          <div class="external-engine-task"><b>${escapeHtml(taskPrefix)}</b><span>${escapeHtml(engine.current_task || "호출 대기")}</span></div>
          <div class="external-engine-io">
            <span><b>코덱스스톡 → 엔진</b>${escapeHtml(engine.input_label || "검증 계약")}</span>
            <span><b>엔진 → 코덱스스톡</b>${escapeHtml(engine.output_label || "검증 결과")}</span>
          </div>
          <div class="external-engine-progress-head">
            <span>${escapeHtml(engine.progress_label || "작업 진행률")}</span>
            <b>${Math.round(progress)}%</b>
          </div>
          <div class="external-engine-meter" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(progress)}">
            <span style="width:${progress}%"></span>
          </div>
          <div class="external-engine-foot">
            <span>${escapeHtml(operationalLabel)} · 마지막 성공 ${escapeHtml(lastSuccess)} · 활동 ${escapeHtml(lastActivity)}</span>
            <span class="external-engine-eta">예상 완료 ${escapeHtml(engine.eta_label || "작업 없음")}</span>
          </div>
        </article>`;
    }).join("");
  }

  async function load(silent = true, deps = {}) {
    const { fetchJson, addLog, el, escapeHtml, setText } = deps;
    const sidecarPromise = loadExecutionSidecar(true, deps);
    try {
      const response = await fetchJson("/api/external-engines/status", { cache: "no-store" });
      const result = await response.json();
      if (!response.ok || result.ok === false) throw new Error(result.error || "외부 엔진 상태 조회 실패");
      const improvement = await loadImprovement(true, deps);
      const reconciled = reconcileEngineDashboardWithImprovement(result, improvement || {});
      render(reconciled, deps);
      await sidecarPromise;
      if (!silent) {
        addLog(`외부 엔진 상태 새로고침: ${Number(reconciled.summary?.engine_count || 0)}개 · 사용 중 ${Number(reconciled.summary?.in_use_count || 0)}개`);
      }
      return reconciled;
    } catch (error) {
      await sidecarPromise;
      const grid = el("#externalEngineGrid");
      if (grid) {
        grid.innerHTML = `
          <article class="external-engine-loading">
            <strong>외부 엔진 상태를 불러오지 못했습니다</strong>
            <span>${escapeHtml(error.message)}</span>
          </article>`;
      }
      setText("externalEngineUpdatedAt", "상태 확인 실패");
      if (!silent) addLog(`외부 엔진 상태 조회 실패: ${error.message}`);
      return null;
    }
  }

  function percent(value, total) {
    if (!(Number(total) > 0)) return 0;
    return Math.max(0, Math.min(100, (Number(value || 0) / Number(total)) * 100));
  }

  function renderExecutionSidecar(payload = {}, deps = {}) {
    const { el, setText, formatDateTimeShort } = deps;
    const card = el("#executionSidecarCard");
    if (!card) return;
    const process = payload.runtime_process || {};
    const proof = payload.validation_proof || {};
    const pipeline = payload.candidate_pipeline || {};
    const drill = payload.pipeline_drill || {};
    const stages = pipeline.stage_counts || {};
    const alive = process.process_alive === true;
    const fresh = process.status_fresh === true;
    const operational = payload.ok === true;
    const pipelineHealthy = pipeline.trading_pipeline_healthy !== false;
    const complete = proof.proof_complete === true;
    const healthy = alive && fresh && operational && pipelineHealthy;
    const state = healthy ? (complete ? "ready" : "running") : "error";
    const badge = state === "ready" ? "연결됨 · 검증 완료" : state === "running" ? "연결됨 · 상시 작동" : "연결 이상";
    const summary = healthy
      ? "코덱스스톡의 신호를 독립적으로 감시·검증하는 실행기가 계속 작동 중입니다."
      : "외부 실행기의 프로세스 또는 heartbeat가 정상 범위를 벗어났습니다.";
    card.className = `execution-sidecar-card ${state}`;
    setText("executionSidecarBadge", badge);
    setText("executionSidecarSummary", summary);
    const pipelineLabels = {
      normal_watch: "정상 관망",
      normal_risk_block: "정상 차단",
      data_wait: "데이터 대기",
      system_bottleneck: "시스템 병목",
      candidate_not_promoted: "후보 승격 확인",
      executor_processing: "실행기 처리 중",
      connected: "종단 연결 정상",
      pipeline_stalled: "파이프라인 정지",
    };
    const pipelineLabel = pipelineLabels[pipeline.state] || "상태 확인 중";
    setText("executionSidecarBadge", healthy ? pipelineLabel : `확인 필요 · ${pipelineLabel}`);
    setText("executionSidecarSummary", healthy ? `시스템 정상 · 매매 파이프라인 ${pipelineLabel}` : `확인 필요 · ${pipelineLabel}`);
    setText("executionSidecarMode", String(payload.mode || "unknown").toUpperCase());
    setText("executionSidecarProcess", alive ? `실행 중 · PID ${Number(process.process_id || 0)}` : "중지됨");
    const age = Number(process.status_age_seconds);
    setText("executionSidecarHeartbeat", Number.isFinite(age) ? `${Math.max(0, Math.round(age))}초 전` : "확인 불가");
    setText("executionSidecarProcessed", `${Number(payload.processed_total || 0).toLocaleString()}건 · 대기 ${Number(payload.inbox_pending || 0).toLocaleString()}건`);
    setText("executionSidecarOrderBoundary", payload.real_order_supported === true ? "실주문 지원" : "실주문 차단 · Shadow/Paper");
    setText("executionPipelineCandidates", `${Number(stages.candidate_tickets || 0).toLocaleString()}건`);
    setText("executionPipelineScanned", `${Number(stages.market_scan_items || 0).toLocaleString()}종목`);
    setText("executionPipelineValidated", `${Number(stages.validation_complete || 0).toLocaleString()}건`);
    setText("executionPipelineValidationPending", `${Number(stages.validation_pending || 0).toLocaleString()}건`);
    setText("executionPipelinePassed", `${Number(stages.risk_passed || 0).toLocaleString()}건`);
    setText("executionPipelineSignals", `${Number(stages.signed_signal_published || 0).toLocaleString()}건`);
    setText("executionPipelineResults", `${Number(stages.matched_executor_results ?? stages.executor_results ?? 0).toLocaleString()}건`);
    const noTradeLabels = {
      NORMAL_WATCH: "정상 관망",
      NORMAL_RISK_BLOCK: "위험 기준에 따른 정상 차단",
      DATA_UNAVAILABLE: "필수 데이터 대기",
      NORMAL_IN_PROGRESS: "정상 처리 중",
      SYSTEM_BOTTLENECK: "시스템 병목",
      EXECUTION_OBSERVED: "실행기 결과 확인",
    };
    const noTradeCode = String(pipeline.no_trade_classification || "-");
    setText("executionPipelineNoTrade", noTradeLabels[noTradeCode] || noTradeCode.replaceAll("_", " "));
    const evidence = pipeline.evidence_levels || {};
    setText("executionPipelineEvidence", String(evidence.executor_handoff || "not_observed_today").replaceAll("_", " "));
    setText(
      "executionPipelineDrill",
      drill.ok === true && drill.real_order_allowed === false
        ? `통과 · ${String(drill.result_state || "SHADOW_ACCEPTED")}`
        : (drill.error ? "실패 · 로그 확인" : "확인 대기"),
    );

    const observed = Number(proof.observation_hours || 0);
    const requiredHours = Number(proof.required_observation_hours || 24);
    const results = Number(proof.qualifying_result_count || 0);
    const requiredResults = Number(proof.required_result_count || 10);
    const symbols = Number(proof.observed_symbol_count || 0);
    const requiredSymbols = Number(proof.required_symbol_count || 2);
    const observationPct = percent(observed, requiredHours);
    const resultPct = Math.min(percent(results, requiredResults), percent(symbols, requiredSymbols));
    setText("executionSidecarObservationLabel", `${observed.toFixed(2)} / ${requiredHours}시간`);
    setText("executionSidecarCandidateLabel", `${results} / ${requiredResults}건 · 종목 ${symbols} / ${requiredSymbols}`);
    const observationBar = el("#executionSidecarObservationBar");
    const candidateBar = el("#executionSidecarCandidateBar");
    if (observationBar) {
      observationBar.style.width = `${observationPct}%`;
      observationBar.parentElement?.setAttribute("aria-valuenow", String(Math.round(observationPct)));
    }
    if (candidateBar) {
      candidateBar.style.width = `${resultPct}%`;
      candidateBar.parentElement?.setAttribute("aria-valuenow", String(Math.round(resultPct)));
    }
    setText(
      "executionSidecarFooter",
      `세션 ${String(payload.runtime_session_id || "-").slice(0, 8)} · ${Number(payload.cycles || 0).toLocaleString()}회 감시 · 최근 확인 ${payload.updated_at ? formatDateTimeShort(payload.updated_at) : "대기"}`,
    );
  }

  async function loadExecutionSidecar(silent = true, deps = {}) {
    const { fetchJson, addLog, el, setText } = deps;
    try {
      const response = await fetchJson("/api/execution-sidecar/status", { cache: "no-store" });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "외부 실행기 상태 조회 실패");
      renderExecutionSidecar(result, deps);
      if (!silent) addLog(`외부 실행기 상태: ${result.ok ? "상시 작동 중" : "점검 필요"}`);
      return result;
    } catch (error) {
      const card = el("#executionSidecarCard");
      if (card) card.className = "execution-sidecar-card error";
      setText("executionSidecarBadge", "연결 확인 실패");
      setText("executionSidecarSummary", "외부 실행기 상태 API에 연결하지 못했습니다.");
      setText("executionSidecarFooter", error.message);
      if (!silent) addLog(`외부 실행기 상태 조회 실패: ${error.message}`);
      return null;
    }
  }

  async function loadImprovement(silent = true, deps = {}) {
    const { fetchJson, addLog } = deps;
    try {
      const response = await fetchJson("/api/external-engines/improvement-loop/status", { cache: "no-store" });
      const result = await response.json();
      if (!response.ok || result.ok === false) throw new Error(result.error || "자동 개선 상태 조회 실패");
      renderImprovement(result, deps);
      if (!silent) addLog(`외부엔진 자동 개선 상태: ${improvementStatusLabel(result.state || {})}`);
      return result;
    } catch (error) {
      if (!silent) addLog(`외부엔진 자동 개선 상태 조회 실패: ${error.message}`);
      return null;
    }
  }

  async function runImprovement(deps = {}) {
    const { fetchJson, addLog, el } = deps;
    const button = el("#runExternalImprovement");
    if (button) button.disabled = true;
    try {
      const response = await fetchJson("/api/external-engines/improvement-loop/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requested_by: "launcher-ui" }),
      });
      const result = await response.json();
      if (!response.ok || result.ok === false) {
        const message = result.message || result.status || result.error || "자동 개선 실행 실패";
        throw new Error(message);
      }
      addLog(`외부엔진 전략 개선 시작: ${result.cycle_id || "새 주기"} · 실전 주문 권한 없음`);
      return await loadImprovement(false, deps);
    } catch (error) {
      addLog(`외부엔진 전략 개선 실행 보류: ${error.message}`);
      const status = await loadImprovement(true, deps);
      if (!status && button) button.disabled = false;
      return status;
    }
  }

  global.CodexExternalEngineDashboard = Object.freeze({
    render,
    load,
    renderImprovement,
    reconcileEngineDashboardWithImprovement,
    loadImprovement,
    runImprovement,
    renderExecutionSidecar,
    loadExecutionSidecar,
  });
}(window));
