// api/web/app.js - Vanilla Single-Page Clinical Decision Support Client

(function () {
  "use strict";

  // Elements
  const healthBadge = document.getElementById("healthBadge");
  const healthText = document.getElementById("healthText");
  const reportForm = document.getElementById("reportForm");
  const btnSubmit = document.getElementById("btnSubmit");
  const btnSubmitText = document.getElementById("btnSubmitText");
  const formAlertBanner = document.getElementById("formAlertBanner");
  const btnLoadRefCase = document.getElementById("btnLoadRefCase");
  const btnEmptyLoadRef = document.getElementById("btnEmptyLoadRef");

  // State Containers
  const emptyState = document.getElementById("emptyState");
  const runningState = document.getElementById("runningState");
  const resultDisplay = document.getElementById("resultDisplay");
  const elapsedTimeSpan = document.getElementById("elapsedTime");
  const stepperAnnounce = document.getElementById("stepperAnnounce");

  // Stepper Elements
  const stepQueued = document.getElementById("stepQueued");
  const stepRetrieving = document.getElementById("stepRetrieving");
  const stepAssessing = document.getElementById("stepAssessing");
  const stepVerifying = document.getElementById("stepVerifying");
  const stepDone = document.getElementById("stepDone");

  // Result Elements
  const routingBadge = document.getElementById("routingBadge");
  const verificationBadge = document.getElementById("verificationBadge");
  const resultRunId = document.getElementById("resultRunId");
  const resultLatencyPill = document.getElementById("resultLatencyPill");
  const btnCopyRunId = document.getElementById("btnCopyRunId");

  const escalationBanner = document.getElementById("escalationBanner");
  const escalationReason = document.getElementById("escalationReason");
  const escalationAction = document.getElementById("escalationAction");

  const seriousnessValue = document.getElementById("seriousnessValue");
  const seriousnessBasis = document.getElementById("seriousnessBasis");
  const expectednessValue = document.getElementById("expectednessValue");
  const expectednessBasis = document.getElementById("expectednessBasis");
  const routingValue = document.getElementById("routingValue");
  const routingBasisText = document.getElementById("routingBasisText");

  const citationCount = document.getElementById("citationCount");
  const citationList = document.getElementById("citationList");

  const btnToggleTrace = document.getElementById("btnToggleTrace");
  const traceChevron = document.getElementById("traceChevron");
  const traceContent = document.getElementById("traceContent");
  const traceItems = document.getElementById("traceItems");

  // Feedback Elements
  const btnThumbUp = document.getElementById("btnThumbUp");
  const btnThumbDown = document.getElementById("btnThumbDown");
  const feedbackReason = document.getElementById("feedbackReason");
  const btnSubmitFeedback = document.getElementById("btnSubmitFeedback");
  const toastContainer = document.getElementById("toastContainer");

  // Synthetic Reference Case Data
  const REFERENCE_CASE = {
    patient_age: 42,
    patient_sex: "female",
    reporter_type: "physician",
    suspect_drug: "Lamotrigine",
    drug_start_date: "2024-01-01",
    event_date: "2024-01-08",
    outcome: "recovering",
    reaction_description: "The patient's skin started peeling badly a week after starting the drug, and she was admitted to hospital.",
    narrative: "Patient presented with erythema and epidermal detachment consistent with TEN/SJS requiring inpatient care after initiating lamotrigine therapy."
  };

  let activeRunId = null;
  let pollIntervalId = null;
  let timerIntervalId = null;
  let runStartTimeEpoch = null;
  let selectedFeedbackRating = null;

  // Initialize
  document.addEventListener("DOMContentLoaded", () => {
    checkHealth();
    setInterval(checkHealth, 10000);

    btnLoadRefCase.addEventListener("click", loadReferenceCase);
    btnEmptyLoadRef.addEventListener("click", loadReferenceCase);
    reportForm.addEventListener("submit", handleFormSubmit);

    btnCopyRunId.addEventListener("click", copyRunIdToClipboard);
    btnToggleTrace.addEventListener("click", toggleTraceDrawer);

    btnThumbUp.addEventListener("click", () => selectFeedback("thumbs_up"));
    btnThumbDown.addEventListener("click", () => selectFeedback("thumbs_down"));
    btnSubmitFeedback.addEventListener("click", submitFeedback);

    // Support state preview via URL parameter (e.g. ?state=completed, ?state=escalated)
    const urlParams = new URLSearchParams(window.location.search);
    const previewState = urlParams.get("state");
    if (previewState) {
      applyPreviewState(previewState);
    }
  });

  // Apply Preview State for Documentation / Testing
  function applyPreviewState(state) {
    if (state === "empty") {
      showEmptyState();
    } else if (state === "running") {
      loadReferenceCase();
      showRunningState();
      updateStepper(3);
      elapsedTimeSpan.textContent = "1.4s";
    } else if (state === "completed") {
      loadReferenceCase();
      const mockCompleted = {
        run_id: "rep_ref_lamotrigine_001",
        status: "completed",
        timestamps: { started_at: "2026-10-22T18:15:12.314901Z", finished_at: "2026-10-22T18:15:12.434436Z" },
        result: {
          routing: "expedited",
          routing_basis: "Expedited 15-day reporting recommended: Suspect drug 'Lamotrigine' caused reaction 'The patient's skin started peeling badly a week after starting the drug, and she was admitted to hospital.', satisfying statutory seriousness criteria (hospitalisation) and not listed as expected.",
          seriousness: { is_serious: true, criteria: ["hospitalisation"] },
          expectedness: { is_listed: false, matched_term: null },
          citations: [
            {
              passage_id: "ipc-pv-guidance-sec4-seriousness",
              quote: "A serious adverse event (SAE) or reaction is any untoward medical occurrence that at any dose results in death, inpatient hospitalisation or prolongation of existing hospitalisation, persistent or significant disability or incapacity, or is a congenital anomaly or birth defect, or is life-threatening."
            },
            {
              passage_id: "ndct-2019-second-sched-table1",
              quote: "Any serious unexpected adverse event shall be reported by the sponsor or marketing authorisation holder to the Central Licencing Authority within fifteen calendar days of receipt of the information."
            },
            {
              passage_id: "lamotrigine-pi-sec4-8-undesirable",
              quote: "Rare: Stevens-Johnson syndrome (SJS); Very rare: Toxic epidermal necrolysis (TEN). Severe cutaneous adverse reactions require immediate discontinuation."
            }
          ]
        }
      };
      renderAssessmentResult(mockCompleted);
      // Inject trace items
      traceItems.innerHTML = `
        <div class="trace-item">
          <div class="trace-dot" style="background-color: var(--accent-teal);"></div>
          <div class="trace-info">
            <div class="trace-line1"><span class="trace-step-name">Tool: search_corpus</span><span class="trace-metrics">0.8ms &bull; ok</span></div>
            <div class="trace-detail">Retrieved 4 passages from regulatory corpus and package insert</div>
          </div>
        </div>
        <div class="trace-item">
          <div class="trace-dot"></div>
          <div class="trace-info">
            <div class="trace-line1"><span class="trace-step-name">Assessor (assessment_generation)</span><span class="trace-metrics">62.3ms &bull; 212 tok &bull; $0.000060</span></div>
            <div class="trace-detail">{"action": "draft_triage_assessment", "routing": "expedited", "is_serious": true, "citations_count": 3}</div>
          </div>
        </div>
        <div class="trace-item">
          <div class="trace-dot"></div>
          <div class="trace-info">
            <div class="trace-line1"><span class="trace-step-name">Verifier (verification_audit)</span><span class="trace-metrics">15.0ms &bull; 127 tok &bull; $0.000033</span></div>
            <div class="trace-detail">{"verification_passed": true, "verified_citations": 3, "errors": [], "status": "completed"}</div>
          </div>
        </div>
      `;
    } else if (state === "escalated") {
      loadReferenceCase();
      document.getElementById("suspectDrug").value = "ExperimentalCompound-X";
      const mockEscalated = {
        run_id: "rep_esc_out_of_corpus_002",
        status: "escalated",
        timestamps: { started_at: "2026-10-22T18:15:12.314901Z", finished_at: "2026-10-22T18:15:12.420000Z" },
        result: {
          routing: null,
          routing_basis: "System cannot produce a confident determination for out-of-corpus drug.",
          seriousness: { is_serious: false, criteria: [] },
          expectedness: { is_listed: false, matched_term: null },
          escalation_reason: "Suspect drug 'ExperimentalCompound-X' is not present in approved regulatory corpus or package insert database.",
          citations: []
        }
      };
      renderAssessmentResult(mockEscalated);
      traceItems.innerHTML = `
        <div class="trace-item">
          <div class="trace-dot" style="background-color: var(--status-escalated-text);"></div>
          <div class="trace-info">
            <div class="trace-line1"><span class="trace-step-name">Assessor (escalation_handling)</span><span class="trace-metrics">35.0ms &bull; 80 tok &bull; $0.000021</span></div>
            <div class="trace-detail">{"action": "escalate", "reason": "out_of_corpus_drug"}</div>
          </div>
        </div>
      `;
    } else if (state === "validation_error") {
      loadReferenceCase();
      document.getElementById("reactionDesc").value = "";
      document.getElementById("patientAge").value = 150;
      handleValidationError({
        detail: [
          { loc: ["body", "patient_age"], msg: "Input should be less than or equal to 120" },
          { loc: ["body", "reaction_description"], msg: "reaction_description cannot be empty or purely whitespace" }
        ]
      });
    }
  }

  // Health Probe
  async function checkHealth() {
    try {
      const resp = await fetch("/health");
      if (resp.ok) {
        healthBadge.classList.remove("unhealthy");
        healthText.textContent = "Service operational";
      } else {
        healthBadge.classList.add("unhealthy");
        healthText.textContent = "Degraded";
      }
    } catch (e) {
      healthBadge.classList.add("unhealthy");
      healthText.textContent = "Offline";
    }
  }

  // Pre-fill Synthetic Reference Case
  function loadReferenceCase() {
    document.getElementById("patientAge").value = REFERENCE_CASE.patient_age;
    document.getElementById("patientSex").value = REFERENCE_CASE.patient_sex;
    document.getElementById("reporterType").value = REFERENCE_CASE.reporter_type;
    document.getElementById("suspectDrug").value = REFERENCE_CASE.suspect_drug;
    document.getElementById("drugStartDate").value = REFERENCE_CASE.drug_start_date;
    document.getElementById("eventDate").value = REFERENCE_CASE.event_date;
    document.getElementById("outcome").value = REFERENCE_CASE.outcome;
    document.getElementById("reactionDesc").value = REFERENCE_CASE.reaction_description;
    document.getElementById("narrative").value = REFERENCE_CASE.narrative;

    clearFieldErrors();
    showToast("Synthetic reference case loaded");
  }

  // Clear Validation UI
  function clearFieldErrors() {
    formAlertBanner.style.display = "none";
    formAlertBanner.textContent = "";
    document.querySelectorAll(".form-control").forEach(el => el.classList.remove("is-invalid"));
    document.querySelectorAll(".field-error").forEach(el => el.classList.remove("active"));
  }

  // Show Inline Field Error
  function showFieldError(fieldName, msg) {
    const errorMap = {
      patient_age: { input: "patientAge", err: "patientAgeErr" },
      patient_sex: { input: "patientSex", err: "patientSexErr" },
      reporter_type: { input: "reporterType", err: "reporterTypeErr" },
      suspect_drug: { input: "suspectDrug", err: "suspectDrugErr" },
      drug_start_date: { input: "drugStartDate", err: "drugStartDateErr" },
      event_date: { input: "eventDate", err: "eventDateErr" },
      outcome: { input: "outcome", err: "outcomeErr" },
      reaction_description: { input: "reactionDesc", err: "reactionDescErr" }
    };

    const target = errorMap[fieldName];
    if (target) {
      const inputEl = document.getElementById(target.input);
      const errEl = document.getElementById(target.err);
      if (inputEl) inputEl.classList.add("is-invalid");
      if (errEl) {
        errEl.textContent = msg;
        errEl.classList.add("active");
      }
    }
  }

  // Form Submit Handler
  async function handleFormSubmit(e) {
    e.preventDefault();
    clearFieldErrors();

    const formData = new FormData(reportForm);
    const payload = {};
    for (const [key, value] of formData.entries()) {
      if (value.trim() !== "") {
        payload[key] = (key === "patient_age") ? parseInt(value, 10) : value.trim();
      }
    }

    // Set UI to loading state
    btnSubmit.disabled = true;
    btnSubmit.classList.add("loading");
    btnSubmitText.textContent = "Validating and enqueueing...";

    showRunningState();

    try {
      const response = await fetch("/v1/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (response.status === 422) {
        // Validation Error State
        const errorData = await response.json();
        handleValidationError(errorData);
        resetSubmitState();
        showEmptyState();
        return;
      }

      if (response.status === 429) {
        // Rate Limited
        const retryAfter = response.headers.get("Retry-After") || "30";
        formAlertBanner.textContent = `Client rate limit exceeded. Please retry after ${retryAfter} seconds.`;
        formAlertBanner.style.display = "block";
        resetSubmitState();
        showEmptyState();
        return;
      }

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const data = await response.json();
      activeRunId = data.run_id;
      startPollingRun(activeRunId);

    } catch (err) {
      formAlertBanner.textContent = `Submission error: ${err.message}`;
      formAlertBanner.style.display = "block";
      resetSubmitState();
      showEmptyState();
    }
  }

  // Handle 422 Unprocessable Entity
  function handleValidationError(errorData) {
    const details = errorData.detail || [];
    let bannerMsg = "Report rejected by schema validation. Please correct the highlighted fields.";

    details.forEach(err => {
      const field = (err.loc && err.loc.length > 0) ? err.loc[err.loc.length - 1] : "";
      showFieldError(field, err.msg);
    });

    formAlertBanner.textContent = bannerMsg;
    formAlertBanner.style.display = "block";
    showToast("Validation failed (HTTP 422)");
  }

  // Stepper Visual Progression
  function updateStepper(step) {
    const steps = [
      { el: stepQueued, label: "Job enqueued in Redis task queue; awaiting worker pickup..." },
      { el: stepRetrieving, label: "Worker active: retrieving product inserts and regulatory clauses from vector store..." },
      { el: stepAssessing, label: "Assessor agent drafting seriousness and expectedness determination..." },
      { el: stepVerifying, label: "Verifier agent auditing citation accuracy and grounding against source text..." },
      { el: stepDone, label: "Assessment complete." }
    ];

    steps.forEach((s, idx) => {
      if (idx + 1 < step) {
        s.el.className = "step-item completed";
      } else if (idx + 1 === step) {
        s.el.className = "step-item active";
        stepperAnnounce.textContent = s.label;
      } else {
        s.el.className = "step-item";
      }
    });
  }

  // State Transition Handlers
  function showEmptyState() {
    emptyState.style.display = "flex";
    runningState.style.display = "none";
    resultDisplay.style.display = "none";
  }

  function showRunningState() {
    emptyState.style.display = "none";
    runningState.style.display = "block";
    resultDisplay.style.display = "none";

    runStartTimeEpoch = performance.now();
    updateStepper(1);

    clearInterval(timerIntervalId);
    timerIntervalId = setInterval(() => {
      const elapsed = ((performance.now() - runStartTimeEpoch) / 1000).toFixed(1);
      elapsedTimeSpan.textContent = `${elapsed}s`;

      const num = parseFloat(elapsed);
      if (num > 0.4 && num <= 1.0) updateStepper(2);
      else if (num > 1.0 && num <= 1.8) updateStepper(3);
      else if (num > 1.8 && num <= 2.6) updateStepper(4);
    }, 100);
  }

  function showResultDisplay() {
    emptyState.style.display = "none";
    runningState.style.display = "none";
    resultDisplay.style.display = "block";
  }

  function resetSubmitState() {
    btnSubmit.disabled = false;
    btnSubmit.classList.remove("loading");
    btnSubmitText.textContent = "Submit for assessment";
    clearInterval(timerIntervalId);
  }

  // Polling /v1/runs/{id}
  function startPollingRun(runId) {
    clearInterval(pollIntervalId);

    pollIntervalId = setInterval(async () => {
      try {
        const resp = await fetch(`/v1/runs/${runId}`);
        if (!resp.ok) return;

        const data = await resp.json();
        const status = data.status;

        if (status === "running") {
          updateStepper(3);
        } else if (status === "completed" || status === "escalated") {
          clearInterval(pollIntervalId);
          clearInterval(timerIntervalId);
          updateStepper(5);
          resetSubmitState();
          renderAssessmentResult(data);
          fetchAndRenderTrace(runId);
        } else if (status === "failed") {
          clearInterval(pollIntervalId);
          clearInterval(timerIntervalId);
          resetSubmitState();
          showEmptyState();
          formAlertBanner.textContent = `Triage run failed: ${data.error || "Execution terminated unconfidently"}`;
          formAlertBanner.style.display = "block";
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 1500);
  }

  // Render Completed / Escalated Result
  function renderAssessmentResult(data) {
    const res = data.result || {};
    const status = data.status;
    const runId = data.run_id || activeRunId;

    resultRunId.textContent = runId;

    // Latency calculation
    let latencyText = "120ms";
    if (data.timestamps && data.timestamps.started_at && data.timestamps.finished_at) {
      const t0 = new Date(data.timestamps.started_at).getTime();
      const t1 = new Date(data.timestamps.finished_at).getTime();
      const diff = Math.max(0, t1 - t0);
      latencyText = `${diff}ms`;
    }
    resultLatencyPill.textContent = latencyText;

    // Badges & Escalation Banner
    if (status === "escalated") {
      routingBadge.className = "badge badge-escalated";
      routingBadge.textContent = "Escalated";

      verificationBadge.className = "badge badge-escalated";
      verificationBadge.innerHTML = "Review required";

      escalationBanner.style.display = "block";
      escalationReason.textContent = `Reason: ${res.escalation_reason || data.error || "Clinical criteria could not be established with confidence"}`;
      escalationAction.textContent = "Recommended human action: Qualified Person review required. Verify product insert and consult prescribing physician.";
    } else {
      escalationBanner.style.display = "none";
      const routing = res.routing || "expedited";

      if (routing === "expedited") {
        routingBadge.className = "badge badge-expedited";
        routingBadge.textContent = "Expedited 15-day";
      } else if (routing === "periodic") {
        routingBadge.className = "badge badge-periodic";
        routingBadge.textContent = "Periodic PSUR";
      } else {
        routingBadge.className = "badge badge-nonrep";
        routingBadge.textContent = "Non-reportable";
      }

      verificationBadge.className = "badge badge-verified";
      verificationBadge.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        Verified
      `;
    }

    // Tiles
    const seriousness = res.seriousness || {};
    seriousnessValue.textContent = seriousness.is_serious ? "Serious" : "Non-serious";
    const crit = (seriousness.criteria && seriousness.criteria.length > 0)
      ? seriousness.criteria.join(", ")
      : "None met";
    seriousnessBasis.textContent = `Criteria: ${crit}`;

    const expectedness = res.expectedness || {};
    expectednessValue.textContent = expectedness.is_listed ? "Listed" : "Unlisted";
    expectednessBasis.textContent = expectedness.is_listed
      ? `Matched: ${expectedness.matched_term || "Listed term"}`
      : "Reaction not listed in approved package insert";

    routingValue.textContent = res.routing ? capitalize(res.routing) : (status === "escalated" ? "Escalated" : "Expedited 15-day");
    routingBasisText.textContent = res.routing_basis || "Statutory timeline evaluation applied under NDCT Rules 2019 Table 1.";

    // Render Citations
    const citations = res.citations || [];
    citationCount.textContent = citations.length;
    citationList.innerHTML = "";

    if (citations.length === 0) {
      citationList.innerHTML = `<div class="form-hint">No passages retrieved for this run.</div>`;
    } else {
      citations.forEach((cit, idx) => {
        const card = document.createElement("div");
        card.className = "citation-card";

        const docTitle = formatSourceDoc(cit.passage_id);
        const highlightedQuote = highlightKeywords(cit.quote || "");

        card.innerHTML = `
          <div class="citation-header">
            <span class="citation-doc">${escapeHtml(docTitle)}</span>
            <span class="citation-clause">${escapeHtml(cit.passage_id)}</span>
          </div>
          <div class="citation-quote">"${highlightedQuote}"</div>
          <button type="button" class="passage-expander" aria-expanded="false" data-index="${idx}">
            <span>View passage context</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
          <div id="passageBody_${idx}" class="passage-body">
            <strong>Passage Reference:</strong> ${escapeHtml(cit.passage_id)}<br>
            <strong>Verbatim Retrievable Text:</strong> ${escapeHtml(cit.quote)}
          </div>
        `;
        citationList.appendChild(card);
      });

      // Attach expander toggles
      document.querySelectorAll(".passage-expander").forEach(btn => {
        btn.addEventListener("click", () => {
          const idx = btn.getAttribute("data-index");
          const body = document.getElementById(`passageBody_${idx}`);
          const isOpen = body.classList.contains("open");
          if (isOpen) {
            body.classList.remove("open");
            btn.setAttribute("aria-expanded", "false");
            btn.querySelector("span").textContent = "View passage context";
          } else {
            body.classList.add("open");
            btn.setAttribute("aria-expanded", "true");
            btn.querySelector("span").textContent = "Hide passage context";
          }
        });
      });
    }

    // Reset Feedback Form
    resetFeedbackWidget();

    showResultDisplay();
  }

  // Fetch and Render Execution Trace from /v1/runs/{id}/trace
  async function fetchAndRenderTrace(runId) {
    traceItems.innerHTML = `<div class="form-hint">Loading execution trace...</div>`;
    try {
      const resp = await fetch(`/v1/runs/${runId}/trace`);
      if (!resp.ok) {
        traceItems.innerHTML = `<div class="form-hint">Trace unavailable.</div>`;
        return;
      }
      const data = await resp.json();
      const steps = data.trace || [];
      const toolCalls = data.tool_calls || [];

      let html = "";

      // Tool Calls
      if (toolCalls.length > 0) {
        toolCalls.forEach(tc => {
          html += `
            <div class="trace-item">
              <div class="trace-dot" style="background-color: var(--accent-teal);"></div>
              <div class="trace-info">
                <div class="trace-line1">
                  <span class="trace-step-name">Tool: ${escapeHtml(tc.tool)}</span>
                  <span class="trace-metrics">${tc.latency_ms.toFixed(1)}ms &bull; ${tc.ok ? "ok" : "err"}</span>
                </div>
                <div class="trace-detail">${escapeHtml(tc.output_summary)}</div>
              </div>
            </div>
          `;
        });
      }

      // Agent Steps
      if (steps.length > 0) {
        steps.forEach(st => {
          const tokens = (st.prompt_tokens || 0) + (st.completion_tokens || 0);
          const cost = st.cost_usd ? `$${st.cost_usd.toFixed(6)}` : "$0.000000";
          const detailStr = typeof st.detail === "object" ? JSON.stringify(st.detail) : (st.detail || "");

          html += `
            <div class="trace-item">
              <div class="trace-dot"></div>
              <div class="trace-info">
                <div class="trace-line1">
                  <span class="trace-step-name">${capitalize(st.agent)} (${st.kind})</span>
                  <span class="trace-metrics">${st.latency_ms.toFixed(1)}ms &bull; ${tokens} tok &bull; ${cost}</span>
                </div>
                <div class="trace-detail">${escapeHtml(detailStr)}</div>
              </div>
            </div>
          `;
        });
      }

      traceItems.innerHTML = html || `<div class="form-hint">No trace steps recorded.</div>`;

    } catch (e) {
      traceItems.innerHTML = `<div class="form-hint">Trace fetch error: ${escapeHtml(e.message)}</div>`;
    }
  }

  // Toggle Trace Drawer
  function toggleTraceDrawer() {
    const isOpen = traceContent.classList.contains("open");
    if (isOpen) {
      traceContent.classList.remove("open");
      btnToggleTrace.setAttribute("aria-expanded", "false");
      traceChevron.style.transform = "rotate(0deg)";
    } else {
      traceContent.classList.add("open");
      btnToggleTrace.setAttribute("aria-expanded", "true");
      traceChevron.style.transform = "rotate(180deg)";
    }
  }

  // Feedback Selection & Submission
  function selectFeedback(rating) {
    selectedFeedbackRating = rating;
    if (rating === "thumbs_up") {
      btnThumbUp.classList.add("active");
      btnThumbDown.classList.remove("active");
    } else {
      btnThumbDown.classList.add("active");
      btnThumbUp.classList.remove("active");
    }
    feedbackReason.style.display = "block";
    btnSubmitFeedback.style.display = "inline-block";
  }

  async function submitFeedback() {
    if (!activeRunId || !selectedFeedbackRating) return;

    const payload = {
      rating: selectedFeedbackRating,
      reason: feedbackReason.value.trim() || null
    };

    btnSubmitFeedback.disabled = true;
    btnSubmitFeedback.textContent = "Saving...";

    try {
      const resp = await fetch(`/v1/runs/${activeRunId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (resp.ok) {
        showToast("Evaluator feedback recorded");
        feedbackReason.style.display = "none";
        btnSubmitFeedback.style.display = "none";
      } else {
        showToast("Error saving feedback");
      }
    } catch (e) {
      showToast("Network error submitting feedback");
    } finally {
      btnSubmitFeedback.disabled = false;
      btnSubmitFeedback.textContent = "Submit feedback";
    }
  }

  function resetFeedbackWidget() {
    selectedFeedbackRating = null;
    btnThumbUp.classList.remove("active");
    btnThumbDown.classList.remove("active");
    feedbackReason.value = "";
    feedbackReason.style.display = "none";
    btnSubmitFeedback.style.display = "none";
  }

  // Toast Helper
  function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    toastContainer.appendChild(toast);

    setTimeout(() => toast.classList.add("show"), 10);
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 250);
    }, 3000);
  }

  // Copy to Clipboard
  function copyRunIdToClipboard() {
    if (!activeRunId) return;
    navigator.clipboard.writeText(activeRunId).then(() => {
      showToast("Run ID copied to clipboard");
    }).catch(() => {
      showToast("Failed to copy run ID");
    });
  }

  // Helpers
  function capitalize(s) {
    if (!s) return "";
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatSourceDoc(passageId) {
    if (!passageId) return "Corpus Reference";
    if (passageId.startsWith("ipc")) return "IPC Pharmacovigilance Guidance for MAHs";
    if (passageId.startsWith("ndct")) return "New Drugs and Clinical Trials Rules 2019";
    if (passageId.startsWith("lamotrigine")) return "Lamotrigine Approved Package Insert";
    return passageId;
  }

  function highlightKeywords(quote) {
    const escaped = escapeHtml(quote);
    const keywords = [
      "death", "hospitalisation", "inpatient hospitalisation",
      "disability", "life-threatening", "congenital anomaly",
      "fifteen calendar days", "expedited", "Stevens-Johnson syndrome",
      "Toxic epidermal necrolysis", "cutaneous adverse reactions"
    ];

    let result = escaped;
    keywords.forEach(kw => {
      const regex = new RegExp(`(${kw})`, "gi");
      result = result.replace(regex, "<mark>$1</mark>");
    });
    return result;
  }

})();
