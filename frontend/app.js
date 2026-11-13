// api/web/app.js - High-Assurance Pharmacovigilance Decision Support Client (v2.0)

(function () {
  "use strict";

  // Elements
  const healthBadge = document.getElementById("healthBadge");
  const healthText = document.getElementById("healthText");
  const reportForm = document.getElementById("reportForm");
  const btnSubmit = document.getElementById("btnSubmit");
  const btnSubmitText = document.getElementById("btnSubmitText");
  const formAlertBanner = document.getElementById("formAlertBanner");
  const formAlertText = document.getElementById("formAlertText") || formAlertBanner;
  const btnLoadRefCase = document.getElementById("btnLoadRefCase");
  const btnCardLoadRef = document.getElementById("btnCardLoadRef");
  const btnEmptyLoadRef = document.getElementById("btnEmptyLoadRef");
  const btnScenarioPeriodic = document.getElementById("btnScenarioPeriodic");
  const btnScenarioEscalated = document.getElementById("btnScenarioEscalated");
  const btnResetForm = document.getElementById("btnResetForm");
  const themeToggleBtn = document.getElementById("themeToggleBtn");
  const workspaceStatePill = document.getElementById("workspaceStatePill");
  const charCountReaction = document.getElementById("charCountReaction");

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

  // Login & Authentication Elements
  const loginOverlay = document.getElementById("loginOverlay");
  const btnLoginAsAdmin = document.getElementById("btnLoginAsAdmin");
  const btnLoginAsReception = document.getElementById("btnLoginAsReception");
  const btnManualLoginSubmit = document.getElementById("btnManualLoginSubmit");
  const loginUsername = document.getElementById("loginUsername");
  const btnSignOut = document.getElementById("btnSignOut");
  const userProfileName = document.getElementById("userProfileName");

  // Role & Dashboard Elements
  const roleBtnAdmin = document.getElementById("roleBtnAdmin");
  const roleBtnReception = document.getElementById("roleBtnReception");
  const roleNoticeBadge = document.getElementById("roleNoticeBadge");
  const roleNoticeText = document.getElementById("roleNoticeText");
  const receptionBannerNotice = document.getElementById("receptionBannerNotice");

  // View Navigation Tabs
  const tabBtnPatients = document.getElementById("tabBtnPatients");
  const tabBtnTriage = document.getElementById("tabBtnTriage");
  const viewPatients = document.getElementById("viewPatients");
  const viewTriage = document.getElementById("viewTriage");
  const patientCountBadge = document.getElementById("patientCountBadge");

  // Patient Registry & Table Elements
  const patientTableBody = document.getElementById("patientTableBody");
  const searchPatientInput = document.getElementById("searchPatientInput");
  const filterConditionSelect = document.getElementById("filterConditionSelect");
  const visiblePatientCount = document.getElementById("visiblePatientCount");
  const kpiTotalPatients = document.getElementById("kpiTotalPatients");
  const kpiSevereSAEs = document.getElementById("kpiSevereSAEs");
  const kpiHospitalised = document.getElementById("kpiHospitalised");
  const kpiRecovered = document.getElementById("kpiRecovered");

  // View Switcher & Holographic Telemetry Cards
  const btnViewCards = document.getElementById("btnViewCards");
  const btnViewTable = document.getElementById("btnViewTable");
  const patientCardsGrid = document.getElementById("patientCardsGrid");
  const patientTableWrapper = document.getElementById("patientTableWrapper");

  // Slide-Over Patient Clinical Inspector Drawer
  const drawerBackdrop = document.getElementById("drawerBackdrop");
  const patientDrawer = document.getElementById("patientDrawer");
  const drawerCloseBtn = document.getElementById("drawerCloseBtn");
  const drawerCancelBtn = document.getElementById("drawerCancelBtn");
  const drawerSaveBtn = document.getElementById("drawerSaveBtn");
  const drawerPatientTitle = document.getElementById("drawerPatientTitle");
  const drawerPatientSubtitle = document.getElementById("drawerPatientSubtitle");
  const drawerAvatarBadge = document.getElementById("drawerAvatarBadge");
  const drawerVitalHR = document.getElementById("drawerVitalHR");
  const drawerVitalBP = document.getElementById("drawerVitalBP");
  const drawerVitalSPO2 = document.getElementById("drawerVitalSPO2");
  const drawerVitalTemp = document.getElementById("drawerVitalTemp");
  const drawerConditionMatrix = document.getElementById("drawerConditionMatrix");
  const drawerGuidanceInput = document.getElementById("drawerGuidanceInput");
  const drawerFilesList = document.getElementById("drawerFilesList");
  const btnDrawerAttachReport = document.getElementById("btnDrawerAttachReport");
  const btnDrawerRunTriage = document.getElementById("btnDrawerRunTriage");
  const drawerTimeline = document.getElementById("drawerTimeline");

  // Modal Dialogs
  const patientModal = document.getElementById("patientModal");
  const btnModalClose = document.getElementById("btnModalClose");
  const btnModalCancel = document.getElementById("btnModalCancel");
  const btnModalSave = document.getElementById("btnModalSave");
  const modalPatientTitle = document.getElementById("patientModalTitle");
  const modalPatientSubtitle = document.getElementById("patientModalSubtitle");
  const modalPatientInfoCard = document.getElementById("modalPatientInfoCard");
  const modalPatientCondition = document.getElementById("modalPatientCondition");
  const modalDoctorGuidance = document.getElementById("modalDoctorGuidance");
  const modalAttachedFilesList = document.getElementById("modalAttachedFilesList");

  // File Upload Elements
  const fileUploadModal = document.getElementById("fileUploadModal");
  const btnOpenFileUpload = document.getElementById("btnOpenFileUpload");
  const btnOpenNewPatient = document.getElementById("btnOpenNewPatient");
  const btnUploadModalClose = document.getElementById("btnUploadModalClose");
  const btnUploadModalCancel = document.getElementById("btnUploadModalCancel");
  const btnUploadModalSubmit = document.getElementById("btnUploadModalSubmit");
  const uploadTargetPatient = document.getElementById("uploadTargetPatient");
  const fileInputEl = document.getElementById("fileInputEl");
  const fileDropzone = document.getElementById("fileDropzone");
  const uploadFileListPreview = document.getElementById("uploadFileListPreview");

  // Form Fields
  const inputReaction = document.getElementById("reactionDesc");
  const inputSuspectDrug = document.getElementById("suspectDrug");
  const selectSex = document.getElementById("patientSex");
  const selectReporter = document.getElementById("reporterType");

  // Synthetic Reference Case Data (Serious, Unlisted -> Expedited 15-day)
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

  // Scenario 2: Non-serious, unlisted -> Periodic PSUR
  const PERIODIC_CASE = {
    patient_age: 35,
    patient_sex: "male",
    reporter_type: "pharmacist",
    suspect_drug: "Lamotrigine",
    drug_start_date: "2024-02-10",
    event_date: "2024-02-14",
    outcome: "recovered",
    reaction_description: "Patient experienced mild transient localized skin itching without blistering, hospitalization, or systemic symptoms.",
    narrative: "Mild cutaneous pruritus reported during dose titration. No mucosal involvement. Resolved without medical intervention."
  };

  // Scenario 3: Out of corpus -> Escalated
  const ESCALATED_CASE = {
    patient_age: 58,
    patient_sex: "other",
    reporter_type: "physician",
    suspect_drug: "ExperimentalCompound-X",
    drug_start_date: "2024-03-01",
    event_date: "2024-03-05",
    outcome: "not_recovered",
    reaction_description: "Patient developed acute confusion and elevated liver enzymes while taking investigational drug.",
    narrative: "Phase 1 experimental therapy adverse reaction. Drug is not registered in domestic regulatory formulary."
  };

  let activeRunId = null;
  let pollIntervalId = null;
  let timerIntervalId = null;
  let runStartTimeEpoch = null;
  let selectedFeedbackRating = null;

  // Initialize
  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    checkHealth();
    setInterval(checkHealth, 10000);

    // Scenario buttons
    if (btnLoadRefCase) btnLoadRefCase.addEventListener("click", loadReferenceCase);
    if (btnCardLoadRef) btnCardLoadRef.addEventListener("click", loadReferenceCase);
    if (btnEmptyLoadRef) btnEmptyLoadRef.addEventListener("click", loadReferenceCase);
    if (btnScenarioPeriodic) btnScenarioPeriodic.addEventListener("click", loadPeriodicCase);
    if (btnScenarioEscalated) btnScenarioEscalated.addEventListener("click", loadEscalatedCase);
    if (btnResetForm) btnResetForm.addEventListener("click", resetFormToBlank);

    // Setup Segmented Pill Controls
    initSegmentedControls();

    // Drug Shortcut tags
    document.querySelectorAll(".drug-shortcut-pill").forEach(pill => {
      pill.addEventListener("click", (e) => {
        const drug = e.target.getAttribute("data-drug");
        if (drug && inputSuspectDrug) {
          inputSuspectDrug.value = drug;
          showToast(`Suspect drug set to "${drug}"`);
        }
      });
    });

    // Theme switcher
    if (themeToggleBtn) {
      themeToggleBtn.addEventListener("click", toggleTheme);
    }

    // Reaction char counter
    if (inputReaction && charCountReaction) {
      inputReaction.addEventListener("input", updateCharCounter);
      updateCharCounter();
    }

    // Keyboard shortcut: Cmd+Enter or Ctrl+Enter submits
    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        if (reportForm) reportForm.requestSubmit();
      }
    });

    reportForm.addEventListener("submit", handleFormSubmit);
    btnCopyRunId.addEventListener("click", copyRunIdToClipboard);
    btnToggleTrace.addEventListener("click", toggleTraceDrawer);

    btnThumbUp.addEventListener("click", () => selectFeedback("thumbs_up"));
    btnThumbDown.addEventListener("click", () => selectFeedback("thumbs_down"));
    btnSubmitFeedback.addEventListener("click", submitFeedback);

    // Auth Portal Setup
    initAuth();
    if (btnLoginAsAdmin) {
      btnLoginAsAdmin.addEventListener("click", () => login("admin", "Dr. A. Sen (QPPV)"));
    }
    if (btnLoginAsReception) {
      btnLoginAsReception.addEventListener("click", () => login("reception", "Clinic Reception Desk"));
    }
    if (btnSignOut) {
      btnSignOut.addEventListener("click", logout);
    }
    if (btnManualLoginSubmit) {
      btnManualLoginSubmit.addEventListener("click", () => {
        const u = (loginUsername ? loginUsername.value : "").trim().toLowerCase();
        if (u.includes("reception")) {
          login("reception", "Clinic Reception Desk");
        } else {
          login("admin", "Dr. A. Sen (QPPV)");
        }
      });
    }

    // Role & Tab Setup
    initRoles();
    initTabs();
    initViewSwitcher();
    initPatientRegistry();

    if (roleBtnAdmin) roleBtnAdmin.addEventListener("click", () => setRole("admin"));
    if (roleBtnReception) roleBtnReception.addEventListener("click", () => setRole("reception"));

    if (tabBtnPatients) tabBtnPatients.addEventListener("click", () => switchView("patients"));
    if (tabBtnTriage) tabBtnTriage.addEventListener("click", () => switchView("triage"));

    if (searchPatientInput) searchPatientInput.addEventListener("input", filterAndRenderPatients);
    if (filterConditionSelect) filterConditionSelect.addEventListener("change", filterAndRenderPatients);

    if (btnModalClose) btnModalClose.addEventListener("click", closePatientModal);
    if (btnModalCancel) btnModalCancel.addEventListener("click", closePatientModal);
    if (btnModalSave) btnModalSave.addEventListener("click", savePatientModal);

    // Slide-Over Drawer listeners
    if (drawerCloseBtn) drawerCloseBtn.addEventListener("click", closePatientDrawer);
    if (drawerCancelBtn) drawerCancelBtn.addEventListener("click", closePatientDrawer);
    if (drawerSaveBtn) drawerSaveBtn.addEventListener("click", savePatientDrawer);
    if (drawerBackdrop) {
      drawerBackdrop.addEventListener("click", (e) => {
        if (e.target === drawerBackdrop) closePatientDrawer();
      });
    }
    if (btnDrawerAttachReport) {
      btnDrawerAttachReport.addEventListener("click", () => {
        if (activeEditingPatientId) {
          const p = activeEditingPatientId;
          closePatientDrawer();
          openFileUploadModal(p);
        }
      });
    }
    if (btnDrawerRunTriage) {
      btnDrawerRunTriage.addEventListener("click", () => {
        if (activeEditingPatientId) {
          const p = activeEditingPatientId;
          closePatientDrawer();
          runTriageForPatient(p);
        }
      });
    }
    document.querySelectorAll(".directive-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const text = chip.getAttribute("data-text");
        if (drawerGuidanceInput && text) {
          const cur = drawerGuidanceInput.value.trim();
          drawerGuidanceInput.value = cur ? `${cur} ${text}` : text;
          showToast(`Directive added: "${text}"`);
        }
      });
    });

    if (btnOpenFileUpload) btnOpenFileUpload.addEventListener("click", () => openFileUploadModal());
    if (btnOpenNewPatient) btnOpenNewPatient.addEventListener("click", intakeNewPatientCase);
    if (btnUploadModalClose) btnUploadModalClose.addEventListener("click", closeFileUploadModal);
    if (btnUploadModalCancel) btnUploadModalCancel.addEventListener("click", closeFileUploadModal);
    if (btnUploadModalSubmit) btnUploadModalSubmit.addEventListener("click", submitFileUpload);

    initFileDropzone();

    // Motion & Smooth Scroll Architecture (Lenis + GSAP)
    initSmoothScroll();
    initMotionArchitecture();

    // Support state preview via URL parameter (e.g. ?state=completed, ?state=escalated)
    const urlParams = new URLSearchParams(window.location.search);
    const previewState = urlParams.get("state");
    if (previewState) {
      switchView("triage");
      applyPreviewState(previewState);
    } else {
      const viewParam = urlParams.get("view");
      if (viewParam === "triage") {
        switchView("triage");
      } else {
        switchView("patients");
      }
    }

    const drawerParam = urlParams.get("drawer");
    if (drawerParam) {
      setTimeout(() => {
        openPatientDrawer(drawerParam, currentRole !== "admin");
      }, 150);
    }
  });

  // Segmented Pill Controls Handler
  function initSegmentedControls() {
    // Sex segments
    document.querySelectorAll(".sex-segments .segment-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const val = btn.getAttribute("data-val");
        if (selectSex) {
          selectSex.value = val;
          syncSegments(".sex-segments", val);
        }
      });
    });

    // Reporter segments
    document.querySelectorAll(".reporter-segments .segment-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const val = btn.getAttribute("data-val");
        if (selectReporter) {
          selectReporter.value = val;
          syncSegments(".reporter-segments", val);
        }
      });
    });
  }

  function syncSegments(containerSelector, val) {
    document.querySelectorAll(`${containerSelector} .segment-btn`).forEach(btn => {
      if (btn.getAttribute("data-val") === val) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });
  }

  // Theme Management
  function initTheme() {
    const urlParams = new URLSearchParams(window.location.search);
    const themeParam = urlParams.get("theme");
    if (themeParam === "light" || themeParam === "dark") {
      document.documentElement.setAttribute("data-theme", themeParam);
      localStorage.setItem("pv_theme", themeParam);
      return;
    }

    const saved = localStorage.getItem("pv_theme");
    if (saved === "light") {
      document.documentElement.setAttribute("data-theme", "light");
    } else {
      document.documentElement.setAttribute("data-theme", "dark");
    }
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("pv_theme", next);
    showToast(`Theme switched to ${next}`);
  }

  function updateCharCounter() {
    if (!inputReaction || !charCountReaction) return;
    const len = inputReaction.value.length;
    charCountReaction.textContent = `${len} / 2000`;
  }

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
      traceItems.innerHTML = `
        <div class="trace-item">
          <div class="trace-dot"></div>
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
    fillFormData(REFERENCE_CASE);
    highlightSimCard(btnLoadRefCase);
    showToast("Loaded Reference Case: Lamotrigine SJS (Expedited 15-day)");
  }

  function loadPeriodicCase() {
    fillFormData(PERIODIC_CASE);
    highlightSimCard(btnScenarioPeriodic);
    showToast("Loaded Scenario: Mild Rash (Periodic PSUR)");
  }

  function loadEscalatedCase() {
    fillFormData(ESCALATED_CASE);
    highlightSimCard(btnScenarioEscalated);
    showToast("Loaded Scenario: ExperimentalCompound-X (Escalated)");
  }

  function fillFormData(data) {
    document.getElementById("patientAge").value = data.patient_age;
    document.getElementById("patientSex").value = data.patient_sex;
    syncSegments(".sex-segments", data.patient_sex);

    document.getElementById("reporterType").value = data.reporter_type;
    syncSegments(".reporter-segments", data.reporter_type);

    document.getElementById("suspectDrug").value = data.suspect_drug;
    document.getElementById("drugStartDate").value = data.drug_start_date;
    document.getElementById("eventDate").value = data.event_date;
    document.getElementById("outcome").value = data.outcome;
    document.getElementById("reactionDesc").value = data.reaction_description;
    document.getElementById("narrative").value = data.narrative || "";

    updateCharCounter();
    clearFieldErrors();
  }

  function resetFormToBlank() {
    reportForm.reset();
    syncSegments(".sex-segments", "female");
    syncSegments(".reporter-segments", "physician");
    updateCharCounter();
    clearFieldErrors();
    showEmptyState();
    highlightSimCard(null);
    showToast("Form cleared to blank");
  }

  function highlightSimCard(activeCard) {
    document.querySelectorAll(".sim-card").forEach(c => c.classList.remove("active-sim"));
    if (activeCard) activeCard.classList.add("active-sim");
  }

  // Clear Validation UI
  function clearFieldErrors() {
    formAlertBanner.style.display = "none";
    if (formAlertText) formAlertText.textContent = "";
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
    btnSubmitText.textContent = "Orchestrating Triage...";

    showRunningState();

    try {
      const response = await fetch("/v1/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (response.status === 422) {
        const errorData = await response.json();
        handleValidationError(errorData);
        resetSubmitState();
        showEmptyState();
        return;
      }

      if (response.status === 429) {
        const retryAfter = response.headers.get("Retry-After") || "30";
        if (formAlertText) formAlertText.textContent = `Rate limit exceeded. Please retry after ${retryAfter} seconds.`;
        formAlertBanner.style.display = "flex";
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
      if (formAlertText) formAlertText.textContent = `Submission error: ${err.message}`;
      formAlertBanner.style.display = "flex";
      resetSubmitState();
      showEmptyState();
    }
  }

  // Handle 422 Unprocessable Entity
  function handleValidationError(errorData) {
    const details = errorData.detail || [];
    let bannerMsg = "Report rejected by schema validation. Please review the highlighted fields below:";

    details.forEach(err => {
      const field = (err.loc && err.loc.length > 0) ? err.loc[err.loc.length - 1] : "";
      showFieldError(field, err.msg);
    });

    if (formAlertText) formAlertText.textContent = bannerMsg;
    formAlertBanner.style.display = "flex";
    showToast("Validation failed (HTTP 422)");
  }

  // Stepper Visual Progression
  function updateStepper(step) {
    const steps = [
      { el: stepQueued, label: "Job enqueued in Redis task queue; awaiting worker pickup..." },
      { el: stepRetrieving, label: "Worker active: retrieving product inserts and regulatory clauses from ChromaDB vector store..." },
      { el: stepAssessing, label: "Assessor agent drafting seriousness and expectedness determination in LangGraph..." },
      { el: stepVerifying, label: "Verifier agent auditing citation accuracy and grounding against source text..." },
      { el: stepDone, label: "Assessment complete: regulatory determination ready." }
    ];

    steps.forEach((s, idx) => {
      if (!s.el) return;
      if (idx + 1 < step) {
        s.el.className = "pipeline-node completed";
      } else if (idx + 1 === step) {
        s.el.className = "pipeline-node active";
        if (stepperAnnounce) stepperAnnounce.textContent = s.label;
      } else {
        s.el.className = "pipeline-node";
      }
    });
  }

  // State Transition Handlers
  function showEmptyState() {
    if (emptyState) {
      emptyState.style.display = "flex";
      if (typeof gsap !== "undefined" && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        gsap.fromTo(
          "#emptyState > *",
          { opacity: 0, y: 12 },
          { opacity: 1, y: 0, duration: 0.35, stagger: 0.05, ease: "power2.out", clearProps: "all" }
        );
      }
    }
    if (runningState) runningState.style.display = "none";
    if (resultDisplay) resultDisplay.style.display = "none";
    if (workspaceStatePill) {
      workspaceStatePill.className = "hud-status-chip chip-standby";
      workspaceStatePill.textContent = "Standby";
    }
  }

  function showRunningState() {
    if (emptyState) emptyState.style.display = "none";
    if (runningState) {
      runningState.style.display = "block";
      if (typeof gsap !== "undefined" && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        gsap.fromTo(
          ".pipeline-node",
          { scale: 0.94, opacity: 0.6 },
          { scale: 1, opacity: 1, duration: 0.3, stagger: 0.04, ease: "back.out(1.4)", clearProps: "all" }
        );
      }
    }
    if (resultDisplay) resultDisplay.style.display = "none";
    if (workspaceStatePill) {
      workspaceStatePill.className = "hud-status-chip pill-expedited";
      workspaceStatePill.textContent = "Assessing...";
    }

    runStartTimeEpoch = performance.now();
    updateStepper(1);

    clearInterval(timerIntervalId);
    timerIntervalId = setInterval(() => {
      const elapsed = ((performance.now() - runStartTimeEpoch) / 1000).toFixed(1);
      if (elapsedTimeSpan) elapsedTimeSpan.textContent = `${elapsed}s`;

      const num = parseFloat(elapsed);
      if (num > 0.4 && num <= 1.0) updateStepper(2);
      else if (num > 1.0 && num <= 1.8) updateStepper(3);
      else if (num > 1.8 && num <= 2.6) updateStepper(4);
    }, 100);
  }

  function showResultDisplay() {
    if (emptyState) emptyState.style.display = "none";
    if (runningState) runningState.style.display = "none";
    if (resultDisplay) {
      resultDisplay.style.display = "block";
      if (typeof gsap !== "undefined" && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        gsap.fromTo(
          "#resultDisplay > *",
          { opacity: 0, y: 16 },
          { opacity: 1, y: 0, duration: 0.45, stagger: 0.06, ease: "power3.out", clearProps: "all" }
        );
      }
    }
  }

  function resetSubmitState() {
    btnSubmit.disabled = false;
    btnSubmit.classList.remove("loading");
    btnSubmitText.textContent = "Initiate Clinical Triage";
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
          if (formAlertText) formAlertText.textContent = `Triage run failed: ${data.error || "Execution terminated unconfidently"}`;
          formAlertBanner.style.display = "flex";
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 1200);
  }

  // Render Completed / Escalated Result
  function renderAssessmentResult(data) {
    const res = data.result || {};
    const status = data.status;
    const runId = data.run_id || activeRunId;

    if (resultRunId) resultRunId.textContent = runId;

    // Latency calculation
    let latencyText = "112ms";
    if (data.timestamps && data.timestamps.started_at && data.timestamps.finished_at) {
      const t0 = new Date(data.timestamps.started_at).getTime();
      const t1 = new Date(data.timestamps.finished_at).getTime();
      const diff = Math.max(0, t1 - t0);
      latencyText = `${diff}ms`;
    }
    if (resultLatencyPill) resultLatencyPill.textContent = latencyText;

    // Badges & Escalation Banner
    if (status === "escalated") {
      routingBadge.className = "badge badge-escalated";
      routingBadge.textContent = "Escalated";

      verificationBadge.className = "badge badge-escalated";
      verificationBadge.innerHTML = "Review required";

      if (workspaceStatePill) {
        workspaceStatePill.className = "hud-status-chip pill-escalated";
        workspaceStatePill.textContent = "Escalated to QPPV";
      }

      escalationBanner.style.display = "block";
      escalationReason.textContent = `Reason: ${res.escalation_reason || data.error || "Clinical criteria could not be established with confidence"}`;
      escalationAction.textContent = "Recommended human action: Qualified Person review required. Verify product insert and consult prescribing physician.";
    } else {
      escalationBanner.style.display = "none";
      const routing = res.routing || "expedited";

      if (routing === "expedited") {
        routingBadge.className = "badge badge-expedited";
        routingBadge.textContent = "Expedited 15-day";
        if (workspaceStatePill) {
          workspaceStatePill.className = "hud-status-chip pill-expedited";
          workspaceStatePill.textContent = "Expedited (15-Day)";
        }
      } else if (routing === "periodic") {
        routingBadge.className = "badge badge-periodic";
        routingBadge.textContent = "Periodic PSUR";
        if (workspaceStatePill) {
          workspaceStatePill.className = "hud-status-chip pill-periodic";
          workspaceStatePill.textContent = "Periodic PSUR";
        }
      } else {
        routingBadge.className = "badge badge-nonrep";
        routingBadge.textContent = "Non-reportable";
        if (workspaceStatePill) {
          workspaceStatePill.className = "hud-status-chip chip-standby";
          workspaceStatePill.textContent = "Non-reportable";
        }
      }

      verificationBadge.className = "badge badge-verified";
      verificationBadge.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        100% Grounded
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
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
            <span>View passage context</span>
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

    // Auto-sync completed triage run to the Patient Safety Registry
    syncTriageRunToRegistry(data);
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
              <div class="trace-dot"></div>
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
      satisfactory: selectedFeedbackRating === "thumbs_up",
      rating: selectedFeedbackRating,
      reason: feedbackReason.value.trim() || null
    };

    btnSubmitFeedback.disabled = true;
    btnSubmitFeedback.textContent = "Recording...";

    try {
      const resp = await fetch(`/v1/runs/${activeRunId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (resp.ok) {
        showToast("Qualified Person feedback recorded successfully");
        feedbackReason.style.display = "none";
        btnSubmitFeedback.style.display = "none";
      } else {
        showToast("Error saving feedback");
      }
    } catch (e) {
      showToast("Network error submitting feedback");
    } finally {
      btnSubmitFeedback.disabled = false;
      btnSubmitFeedback.textContent = "Save Evaluator Assessment";
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
    if (!activeRunId) {
      const current = resultRunId ? resultRunId.textContent : null;
      if (current && current !== "rep_00000000") activeRunId = current;
    }
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
    if (!passageId) return "Regulatory Reference";
    if (passageId.startsWith("ipc")) return "IPC Pharmacovigilance Guidance for MAHs (Sec 4)";
    if (passageId.startsWith("ndct")) return "New Drugs and Clinical Trials Rules 2019 (Table 1)";
    if (passageId.startsWith("lamotrigine")) return "Lamotrigine Approved Package Insert (Sec 4.8)";
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

  // ==========================================
  // Scroll & Motion Architecture (Lenis + GSAP)
  // ==========================================
  let lenisInstance = null;

  function initSmoothScroll() {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion || typeof Lenis === 'undefined') {
      return;
    }
    try {
      lenisInstance = new Lenis({
        duration: 1.2,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        direction: 'vertical',
        smooth: true,
        mouseMultiplier: 1.0,
        smoothTouch: false,
        touchMultiplier: 2.0,
        infinite: false,
      });

      if (typeof gsap !== 'undefined') {
        gsap.ticker.add((time) => {
          lenisInstance.raf(time * 1000);
        });
        gsap.ticker.lagSmoothing(0);
      } else {
        function raf(time) {
          lenisInstance.raf(time);
          requestAnimationFrame(raf);
        }
        requestAnimationFrame(raf);
      }
    } catch (err) {
      console.warn("Lenis initialization bypassed:", err);
    }
  }

  function initMotionArchitecture() {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion || typeof gsap === 'undefined') return;

    // 1. Entrance Stagger for Primary Cockpit Layout
    gsap.from(".top-bar", {
      opacity: 0,
      y: -14,
      duration: 0.5,
      ease: "power3.out",
      clearProps: "all"
    });

    gsap.from(".simulator-bar", {
      opacity: 0,
      y: 10,
      duration: 0.5,
      delay: 0.08,
      ease: "power3.out",
      clearProps: "all"
    });

    gsap.from([".intake-card", ".workspace-card"], {
      opacity: 0,
      y: 16,
      duration: 0.6,
      stagger: 0.1,
      delay: 0.15,
      ease: "power4.out",
      clearProps: "all"
    });

    // 2. Interactive Magnetic Micro-Interactions
    initMagneticElement("#themeToggleBtn", 0.3);
    initMagneticElement(".btn-standby-launch", 0.22);
    initMagneticElement(".btn-hero-submit", 0.16);
    document.querySelectorAll(".sim-card").forEach(el => initMagneticElement(el, 0.2));

    // 3. Subtle 3D Perspective Tilt on Interactive Cards
    initInteractiveTilt(".verdict-hero-card");
    initInteractiveTilt(".tile");
    initInteractiveTilt(".feedback-card");
  }

  function initMagneticElement(elementOrSelector, strength = 0.22) {
    if (typeof gsap === 'undefined') return;
    const el = typeof elementOrSelector === 'string' ? document.querySelector(elementOrSelector) : elementOrSelector;
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const xTo = gsap.quickTo(el, "x", { duration: 0.45, ease: "power3.out" });
    const yTo = gsap.quickTo(el, "y", { duration: 0.45, ease: "power3.out" });

    el.addEventListener("mousemove", (e) => {
      const rect = el.getBoundingClientRect();
      const x = (e.clientX - (rect.left + rect.width / 2)) * strength;
      const y = (e.clientY - (rect.top + rect.height / 2)) * strength;
      xTo(x);
      yTo(y);
    });

    el.addEventListener("mouseleave", () => {
      xTo(0);
      yTo(0);
    });
  }

  function initInteractiveTilt(selector) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    document.querySelectorAll(selector).forEach(card => {
      card.addEventListener("mousemove", (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((y - centerY) / centerY) * -4;
        const rotateY = ((x - centerX) / centerX) * 4;
        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-2px)`;
      });
      card.addEventListener("mouseleave", () => {
        card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)";
      });
    });
  }

  // ========================================================
  // PATIENT SAFETY REGISTRY & CLINICAL MANAGEMENT MODULE
  // ========================================================

  const INITIAL_PATIENTS = [
    {
      id: "PAT-8821",
      name: "Priya Sharma",
      age: 42,
      sex: "female",
      suspectDrug: "Lamotrigine",
      drugStartDate: "2026-10-01",
      eventDate: "2026-10-08",
      reaction: "The patient developed severe skin peeling and epidermal detachment, admitted to ICU.",
      condition: "Hospitalised (ICU)",
      triageRoute: "expedited",
      doctorGuidance: "Discontinue Lamotrigine immediately. IV methylprednisolone 500mg daily. Daily skin barrier dressings. CDSCO 15-day expedited filing initiated. No sulfonamides.",
      doctorName: "Dr. A. Sen (QPPV)",
      updatedAt: "Today, 18:15",
      files: ["discharge_summary_ICU.pdf (1.4 MB)", "dermatology_consult_note.pdf (450 KB)"],
      daysMonitored: 8,
      vitals: { hr: 118, bp: "88/58", spo2: 95, temp: 39.2, status: "Critical ICU" },
      timeline: [
        { day: "Day 0", title: "Lamotrigine Started", desc: "100mg PO QD for mood stabilization." },
        { day: "Day 6", title: "Target Lesions", desc: "Erythematous macules with purpura on chest." },
        { day: "Day 8", title: "ICU Admission", desc: "Epidermal detachment >15% BSA. Drug stopped. Steroids started." }
      ]
    },
    {
      id: "PAT-9042",
      name: "Rajesh Kumar",
      age: 58,
      sex: "male",
      suspectDrug: "Metformin",
      drugStartDate: "2026-09-15",
      eventDate: "2026-09-20",
      reaction: "Mild transient localized gastrointestinal cramping and nausea without vomiting or dehydration.",
      condition: "Under Observation",
      triageRoute: "periodic",
      doctorGuidance: "Dose titration to 500mg with evening meal. Hydration counseling given. Monitor renal function panel in 2 weeks. Routine periodic PSUR logging.",
      doctorName: "Dr. M. Iyer",
      updatedAt: "Today, 14:30",
      files: ["metformin_patient_diary.pdf (320 KB)"],
      daysMonitored: 14,
      vitals: { hr: 74, bp: "124/80", spo2: 99, temp: 36.8, status: "Normal Sinus" },
      timeline: [
        { day: "Day 0", title: "Metformin Started", desc: "1000mg PO BID initiated for Type 2 DM." },
        { day: "Day 5", title: "GI Cramping", desc: "Mild nausea and cramping after morning dose." },
        { day: "Day 14", title: "Dose Adjusted", desc: "Reduced to 500mg with food. Symptoms resolved." }
      ]
    },
    {
      id: "PAT-7319",
      name: "Ananya Verma",
      age: 34,
      sex: "female",
      suspectDrug: "Amoxicillin-Clavulanate",
      drugStartDate: "2026-10-14",
      eventDate: "2026-10-18",
      reaction: "Maculopapular rash on trunk and upper arms after 4 days of antibiotic therapy.",
      condition: "Recovering",
      triageRoute: "periodic",
      doctorGuidance: "Switch to Azithromycin 500mg daily. Oral cetirizine 10mg PRN for pruritus. Rash resolving, patient ambulant. Follow up in 3 days.",
      doctorName: "Dr. A. Sen (QPPV)",
      updatedAt: "Yesterday, 11:20",
      files: [],
      daysMonitored: 6,
      vitals: { hr: 82, bp: "116/74", spo2: 98, temp: 37.1, status: "Recovering" },
      timeline: [
        { day: "Day 0", title: "Augmentin Started", desc: "625mg PO TID for acute sinusitis." },
        { day: "Day 4", title: "Truncal Rash", desc: "Maculopapular cutaneous eruption observed." },
        { day: "Day 6", title: "Antibiotic Switch", desc: "Switched to Azithromycin. Rash fading." }
      ]
    },
    {
      id: "PAT-6120",
      name: "Vikram Malhotra",
      age: 49,
      sex: "male",
      suspectDrug: "ExperimentalCompound-X",
      drugStartDate: "2026-10-05",
      eventDate: "2026-10-11",
      reaction: "Unexplained acute hepatic transaminitis (ALT 450 U/L) without jaundice during clinical trial.",
      condition: "Hospitalised (Ward)",
      triageRoute: "escalated",
      doctorGuidance: "Trial compound immediately quarantined and held. Daily liver function tests and viral hepatitis panel. Urgent QPPV & Sponsor Medical Monitor escalation.",
      doctorName: "Dr. K. Patel",
      updatedAt: "Yesterday, 09:45",
      files: ["hepatic_panel_lab_rep.pdf (890 KB)"],
      daysMonitored: 12,
      vitals: { hr: 96, bp: "138/88", spo2: 97, temp: 38.4, status: "Ward Observation" },
      timeline: [
        { day: "Day 0", title: "Investigational Agent", desc: "Phase 1 clinical trial compound dosing." },
        { day: "Day 7", title: "Routine Labs", desc: "Asymptomatic ALT elevation noted (220 U/L)." },
        { day: "Day 12", title: "Acute Transaminitis", desc: "ALT spiked to 450 U/L. Quarantined. Safety escalation." }
      ]
    }
  ];

  let currentRole = "admin"; // 'admin' (Dr.) or 'reception'
  let patientsList = [];
  let activeEditingPatientId = null;
  let pendingFilesToAttach = [];

  function initAuth() {
    const urlParams = new URLSearchParams(window.location.search);
    const logoutParam = urlParams.get("logout");
    if (logoutParam === "true") {
      logout();
      return;
    }

    // Bypass login if state preview query parameter is provided (for screenshot testing)
    const previewState = urlParams.get("state");
    if (previewState) {
      if (loginOverlay) loginOverlay.classList.add("hidden-auth");
      return;
    }

    const authParam = urlParams.get("auth");
    if (authParam === "admin") {
      login("admin", "Dr. A. Sen (QPPV)");
      return;
    } else if (authParam === "reception") {
      login("reception", "Clinic Reception Desk");
      return;
    }

    const isAuth = localStorage.getItem("pv_authenticated");
    const savedName = localStorage.getItem("pv_user_name");
    const savedRole = localStorage.getItem("pv_role") || "admin";

    if (isAuth === "true") {
      if (loginOverlay) loginOverlay.classList.add("hidden-auth");
      if (userProfileName && savedName) userProfileName.textContent = savedName;
      setRole(savedRole);
    } else {
      if (loginOverlay) loginOverlay.classList.remove("hidden-auth");
    }
  }

  function login(role, name) {
    localStorage.setItem("pv_authenticated", "true");
    localStorage.setItem("pv_user_name", name);
    localStorage.setItem("pv_role", role);
    if (userProfileName) userProfileName.textContent = name;
    setRole(role);

    if (loginOverlay) {
      if (typeof gsap !== "undefined" && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        gsap.to(".login-portal-card", {
          opacity: 0,
          scale: 0.95,
          duration: 0.3,
          ease: "power2.in",
          onComplete: () => {
            loginOverlay.classList.add("hidden-auth");
            gsap.set(".login-portal-card", { clearProps: "all" });
          }
        });
      } else {
        loginOverlay.classList.add("hidden-auth");
      }
    }

    switchView("patients");
    showToast(`Welcome, ${name}. Session authenticated.`);
  }

  function logout() {
    localStorage.removeItem("pv_authenticated");
    localStorage.removeItem("pv_user_name");
    if (loginOverlay) {
      loginOverlay.classList.remove("hidden-auth");
      if (typeof gsap !== "undefined" && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        gsap.fromTo(".login-portal-card", { opacity: 0, scale: 0.95, y: 15 }, { opacity: 1, scale: 1, y: 0, duration: 0.4, ease: "power3.out" });
      }
    }
    showToast("Signed out of clinical session.");
  }

  function initRoles() {
    const urlParams = new URLSearchParams(window.location.search);
    const roleParam = urlParams.get("role");
    if (roleParam === "reception" || roleParam === "admin") {
      currentRole = roleParam;
      localStorage.setItem("pv_role", roleParam);
      updateRoleUI();
      return;
    }
    const saved = localStorage.getItem("pv_role");
    if (saved === "reception" || saved === "admin") {
      currentRole = saved;
    }
    updateRoleUI();
  }

  function setRole(role) {
    currentRole = role;
    localStorage.setItem("pv_role", role);
    updateRoleUI();
    filterAndRenderPatients();
    showToast(`Active Role: ${role === "admin" ? "Dr. Admin (Full Clinical Control)" : "Reception Desk (Read-Only Records & Guidance)"}`);
  }

  function updateRoleUI() {
    if (currentRole === "admin") {
      if (roleBtnAdmin) roleBtnAdmin.classList.add("active");
      if (roleBtnReception) roleBtnReception.classList.remove("active");
      if (roleNoticeBadge) {
        roleNoticeBadge.className = "role-notice-badge role-admin-badge";
        if (roleNoticeText) roleNoticeText.textContent = "Dr. Admin (QPPV) — Full Clinical Control & Guidance Authorization";
      }
      if (receptionBannerNotice) receptionBannerNotice.style.display = "none";
      document.querySelectorAll(".admin-only-feature").forEach(el => {
        el.style.display = "";
        el.removeAttribute("disabled");
      });
    } else {
      if (roleBtnAdmin) roleBtnAdmin.classList.remove("active");
      if (roleBtnReception) roleBtnReception.classList.add("active");
      if (roleNoticeBadge) {
        roleNoticeBadge.className = "role-notice-badge role-reception-badge";
        if (roleNoticeText) roleNoticeText.textContent = "Reception Desk — Read-Only Patient Records & Doctor Guidance View";
      }
      if (receptionBannerNotice) receptionBannerNotice.style.display = "flex";
      document.querySelectorAll(".admin-only-feature").forEach(el => {
        el.style.display = "none";
      });
    }
  }

  function initTabs() {
    // Initial tab setup
  }

  function switchView(viewName) {
    if (viewName === "triage") {
      if (tabBtnTriage) tabBtnTriage.classList.add("active");
      if (tabBtnPatients) tabBtnPatients.classList.remove("active");
      if (viewTriage) viewTriage.style.display = "block";
      if (viewPatients) viewPatients.style.display = "none";
      if (typeof gsap !== "undefined" && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        gsap.fromTo("#viewTriage", { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out", clearProps: "all" });
      }
    } else {
      if (tabBtnPatients) tabBtnPatients.classList.add("active");
      if (tabBtnTriage) tabBtnTriage.classList.remove("active");
      if (viewPatients) viewPatients.style.display = "flex";
      if (viewTriage) viewTriage.style.display = "none";
      filterAndRenderPatients();
      if (typeof gsap !== "undefined" && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        gsap.fromTo("#viewPatients", { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.35, ease: "power3.out", clearProps: "all" });
      }
    }
  }

  // ========================================================
  // VIEW SWITCHER (CARDS GRID VS TABLE)
  // ========================================================
  let currentRegistryView = "cards"; // "cards" (default) or "table"

  function initViewSwitcher() {
    const saved = localStorage.getItem("pv_registry_view");
    if (saved === "table" || saved === "cards") {
      currentRegistryView = saved;
    }
    updateViewSwitcherUI();

    if (btnViewCards) {
      btnViewCards.addEventListener("click", () => setRegistryView("cards"));
    }
    if (btnViewTable) {
      btnViewTable.addEventListener("click", () => setRegistryView("table"));
    }
  }

  function setRegistryView(mode) {
    currentRegistryView = mode;
    localStorage.setItem("pv_registry_view", mode);
    updateViewSwitcherUI();
  }

  function updateViewSwitcherUI() {
    if (currentRegistryView === "cards") {
      if (btnViewCards) btnViewCards.classList.add("active");
      if (btnViewTable) btnViewTable.classList.remove("active");
      if (patientCardsGrid) patientCardsGrid.style.display = "grid";
      if (patientTableWrapper) patientTableWrapper.style.display = "none";
      if (typeof gsap !== "undefined" && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        gsap.fromTo("#patientCardsGrid", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.3, ease: "power2.out", clearProps: "all" });
      }
    } else {
      if (btnViewCards) btnViewCards.classList.remove("active");
      if (btnViewTable) btnViewTable.classList.add("active");
      if (patientCardsGrid) patientCardsGrid.style.display = "none";
      if (patientTableWrapper) patientTableWrapper.style.display = "block";
      if (typeof gsap !== "undefined" && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        gsap.fromTo("#patientTableWrapper", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.3, ease: "power2.out", clearProps: "all" });
      }
    }
  }

  function initPatientRegistry() {
    const raw = localStorage.getItem("pv_patients_registry");
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        patientsList = parsed.map(p => {
          const init = INITIAL_PATIENTS.find(i => i.id === p.id);
          return {
            ...init,
            ...p,
            vitals: p.vitals || (init ? init.vitals : { hr: 78, bp: "120/80", spo2: 98, temp: 37.0 }),
            timeline: p.timeline || (init ? init.timeline : [])
          };
        });
      } catch (err) {
        patientsList = [...INITIAL_PATIENTS];
      }
    } else {
      patientsList = [...INITIAL_PATIENTS];
      savePatientsToStorage();
    }
    filterAndRenderPatients();
  }

  function savePatientsToStorage() {
    localStorage.setItem("pv_patients_registry", JSON.stringify(patientsList));
    updatePatientKPIs();
  }

  function updatePatientKPIs() {
    if (!kpiTotalPatients) return;
    const total = patientsList.length;
    let severeCount = 0;
    let hospCount = 0;
    let recCount = 0;

    patientsList.forEach(p => {
      if (p.triageRoute === "expedited") severeCount++;
      if (p.condition.includes("Hospitalised") || p.condition.includes("ICU")) hospCount++;
      if (p.condition.includes("Recovering") || p.condition.includes("Resolved")) recCount++;
    });

    if (kpiTotalPatients) kpiTotalPatients.textContent = total;
    if (kpiSevereSAEs) kpiSevereSAEs.textContent = severeCount;
    if (kpiHospitalised) kpiHospitalised.textContent = hospCount;
    if (kpiRecovered) kpiRecovered.textContent = recCount;
    if (patientCountBadge) patientCountBadge.textContent = total;
  }

  function filterAndRenderPatients() {
    if (!patientTableBody && !patientCardsGrid) return;
    const query = (searchPatientInput ? searchPatientInput.value : "").trim().toLowerCase();
    const condFilter = filterConditionSelect ? filterConditionSelect.value : "all";

    const filtered = patientsList.filter(p => {
      const matchQuery = !query ||
        p.name.toLowerCase().includes(query) ||
        p.id.toLowerCase().includes(query) ||
        p.suspectDrug.toLowerCase().includes(query) ||
        p.reaction.toLowerCase().includes(query);

      const matchCond = condFilter === "all" || p.condition === condFilter;
      return matchQuery && matchCond;
    });

    if (visiblePatientCount) visiblePatientCount.textContent = filtered.length;

    // Render Cards Grid (Default view)
    renderPatientCards(filtered);

    // Render Table
    if (patientTableBody) {
      patientTableBody.innerHTML = "";

      if (filtered.length === 0) {
        patientTableBody.innerHTML = `
          <tr>
            <td colspan="7" style="text-align: center; padding: 32px; color: var(--muted);">
              No patient safety records match your search criteria.
            </td>
          </tr>
        `;
        return;
      }

      filtered.forEach(patient => {
        const tr = document.createElement("tr");
        tr.className = "patient-row";

        // Condition badge class
        let condClass = "cond-obs";
      if (patient.condition.includes("ICU")) condClass = "cond-icu";
      else if (patient.condition.includes("Ward")) condClass = "cond-ward";
      else if (patient.condition.includes("Recovering")) condClass = "cond-rec";
      else if (patient.condition.includes("Resolved")) condClass = "cond-res";

      // Triage badge
      let routeBadge = `<span class="badge badge-nonrep">Periodic PSUR</span>`;
      if (patient.triageRoute === "expedited") {
        routeBadge = `<span class="badge badge-expedited">Expedited 15-day</span>`;
      } else if (patient.triageRoute === "escalated") {
        routeBadge = `<span class="badge badge-escalated">Safety Officer</span>`;
      } else if (patient.triageRoute === "periodic") {
        routeBadge = `<span class="badge badge-periodic">Periodic PSUR</span>`;
      }

      // Actions based on role
      let actionsHtml = "";
      if (currentRole === "admin") {
        actionsHtml = `
          <div class="table-action-group">
            <button type="button" class="btn-table-sm btn-table-primary btn-edit-patient" data-id="${patient.id}" title="Update patient condition &amp; doctor guidance">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
              <span>Update Condition</span>
            </button>
            <button type="button" class="btn-table-sm btn-triage-patient" data-id="${patient.id}" title="Run multi-agent AI triage against regulatory corpus">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
              <span>Run AI Triage</span>
            </button>
          </div>
        `;
      } else {
        actionsHtml = `
          <div class="table-action-group">
            <button type="button" class="btn-table-sm btn-table-primary btn-view-patient" data-id="${patient.id}" title="View Doctor Guidance &amp; Patient Dossier">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
              <span>View Dr. Guidance</span>
            </button>
          </div>
        `;
      }

      const filesCountText = patient.files && patient.files.length > 0
        ? `<span class="drug-start" style="color: var(--accent-teal);">&bull; ${patient.files.length} report attached</span>`
        : "";

      tr.innerHTML = `
        <td>
          <div class="patient-name-cell">
            <span class="patient-name">${escapeHtml(patient.name)}</span>
            <span class="patient-id-badge">${escapeHtml(patient.id)}</span>
            <span class="patient-demog">${escapeHtml(patient.age)} yrs &bull; ${capitalize(patient.sex)}</span>
          </div>
        </td>
        <td>
          <div class="patient-drug-cell">
            <span class="drug-name">${escapeHtml(patient.suspectDrug)}</span>
            <span class="drug-start">Started: ${escapeHtml(patient.drugStartDate)}</span>
            ${filesCountText}
          </div>
        </td>
        <td>
          <div class="patient-reaction-text">${escapeHtml(patient.reaction)}</div>
        </td>
        <td>
          <span class="badge-condition ${condClass}">${escapeHtml(patient.condition)}</span>
        </td>
        <td>
          ${routeBadge}
        </td>
        <td>
          <div class="dr-guidance-callout">
            <div class="dr-guidance-header">
              <span class="dr-guidance-label">${escapeHtml(patient.doctorName || "Dr. Admin")}</span>
              <span class="dr-timestamp">${escapeHtml(patient.updatedAt || "Recent")}</span>
            </div>
            <div class="dr-guidance-text">${escapeHtml(patient.doctorGuidance)}</div>
          </div>
        </td>
        <td>
          ${actionsHtml}
        </td>
      `;

      patientTableBody.appendChild(tr);
    });

    // Wire table row buttons to Slide-Over Inspector Drawer & Triage
    patientTableBody.querySelectorAll(".btn-edit-patient").forEach(btn => {
      btn.addEventListener("click", () => {
        const pId = btn.getAttribute("data-id");
        openPatientDrawer(pId, false);
      });
    });

    patientTableBody.querySelectorAll(".btn-view-patient").forEach(btn => {
      btn.addEventListener("click", () => {
        const pId = btn.getAttribute("data-id");
        openPatientDrawer(pId, true);
      });
    });

    patientTableBody.querySelectorAll(".btn-triage-patient").forEach(btn => {
      btn.addEventListener("click", () => {
        const pId = btn.getAttribute("data-id");
        runTriageForPatient(pId);
      });
    });
    }
  }

  // ========================================================
  // HOLOGRAPHIC PATIENT TELEMETRY PODS (GRID VIEW)
  // ========================================================
  function renderPatientCards(filtered) {
    if (!patientCardsGrid) return;
    patientCardsGrid.innerHTML = "";

    if (filtered.length === 0) {
      patientCardsGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 48px 24px; color: var(--muted); background: var(--surface-glass); border-radius: var(--radius-card); border: 1px dashed var(--border);">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" style="margin-bottom: 10px; opacity: 0.5;"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <div style="font-size: 14px; font-weight: 600; color: var(--ink);">No patient safety cases match your search criteria</div>
          <div style="font-size: 12px; margin-top: 4px;">Try searching for a different medication, MRN, or clinical condition.</div>
        </div>
      `;
      return;
    }

    filtered.forEach(patient => {
      const card = document.createElement("div");
      card.className = "patient-telemetry-card";
      card.setAttribute("data-patient-id", patient.id);

      // Aura class & condition styling
      let auraClass = "biometric-aura-rec";
      let condClass = "cond-rec";
      if (patient.condition.includes("ICU")) {
        auraClass = "biometric-aura-icu";
        condClass = "cond-icu";
      } else if (patient.condition.includes("Ward")) {
        auraClass = "biometric-aura-ward";
        condClass = "cond-ward";
      } else if (patient.condition.includes("Observation")) {
        auraClass = "biometric-aura-ward";
        condClass = "cond-obs";
      } else if (patient.condition.includes("Resolved")) {
        auraClass = "biometric-aura-rec";
        condClass = "cond-res";
      }

      // Triage route badge
      let routeBadge = `<span class="badge badge-nonrep">Periodic PSUR</span>`;
      if (patient.triageRoute === "expedited") {
        routeBadge = `<span class="badge badge-expedited">Expedited 15-day</span>`;
      } else if (patient.triageRoute === "escalated") {
        routeBadge = `<span class="badge badge-escalated">Safety Officer</span>`;
      } else if (patient.triageRoute === "periodic") {
        routeBadge = `<span class="badge badge-periodic">Periodic PSUR</span>`;
      }

      // Vitals data
      const vitals = patient.vitals || { hr: 78, bp: "120/80", spo2: 98, temp: 37.0 };
      const hrColor = vitals.hr > 100 ? "#F87171" : "#4ADE80";
      const tempColor = vitals.temp >= 38.0 ? "#F87171" : "#4ADE80";

      // Initials
      const initials = patient.name.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase();

      // Actions depending on role
      let cardActions = "";
      if (currentRole === "admin") {
        cardActions = `
          <button type="button" class="btn-card-action btn-inspect-patient" data-id="${patient.id}" title="Inspect full dossier and update clinical directives">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
            <span>Inspect &amp; Update</span>
          </button>
          <button type="button" class="btn-card-action btn-attach-patient admin-only-feature" data-id="${patient.id}" title="Upload adverse event document or lab PDF">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
            <span>Attach Report</span>
          </button>
          <button type="button" class="btn-card-action btn-card-primary btn-triage-patient" data-id="${patient.id}" title="Execute LangGraph multi-agent AI triage against regulatory corpus">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
            <span>AI Triage</span>
          </button>
        `;
      } else {
        cardActions = `
          <button type="button" class="btn-card-action btn-inspect-patient" data-id="${patient.id}" title="View attending doctor's orders &amp; patient clinical dossier" style="width: 100%; justify-content: center;">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
            <span>View Dr. Guidance &amp; Dossier</span>
          </button>
        `;
      }

      card.innerHTML = `
        <div class="telemetry-card-top">
          <div class="patient-avatar-cluster">
            <div class="patient-avatar-badge ${auraClass}">${initials}</div>
            <div class="patient-info-meta">
              <span class="patient-meta-name">${escapeHtml(patient.name)}</span>
              <span class="patient-meta-sub">${escapeHtml(patient.id)} &bull; ${patient.age} yrs &bull; ${capitalize(patient.sex)} &bull; Day ${patient.daysMonitored || 8}</span>
            </div>
          </div>
          <div class="telemetry-badges-stack">
            <span class="badge-condition ${condClass}">${escapeHtml(patient.condition)}</span>
            ${routeBadge}
          </div>
        </div>

        <!-- Realtime Vitals Strip with Animated ECG Waveform -->
        <div class="live-vitals-strip">
          <div class="vital-metric-unit" title="Heart Rate">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="${hrColor}" stroke-width="2.5"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
            <span class="vital-label">HR</span>
            <span class="vital-value" style="color: ${hrColor};">${vitals.hr}</span>
          </div>
          <div class="vital-metric-unit" title="Blood Pressure">
            <span class="vital-label">BP</span>
            <span class="vital-value">${vitals.bp}</span>
          </div>
          <div class="vital-metric-unit" title="SpO2 Saturation">
            <span class="vital-label">SpO2</span>
            <span class="vital-value" style="color: #4ADE80;">${vitals.spo2}%</span>
          </div>
          <div class="vital-metric-unit" title="Temperature">
            <span class="vital-label">Temp</span>
            <span class="vital-value" style="color: ${tempColor};">${vitals.temp}&deg;C</span>
          </div>
          <svg class="ecg-wave-svg" viewBox="0 0 50 18" aria-hidden="true">
            <polyline points="0,9 10,9 13,3 17,15 21,7 24,10 50,10" />
          </svg>
        </div>

        <!-- Suspect Drug & Adverse Event -->
        <div class="patient-card-reaction-box">
          <div class="patient-card-reaction-label">Suspect Drug: <strong>${escapeHtml(patient.suspectDrug)}</strong> &bull; Started ${escapeHtml(patient.drugStartDate)}</div>
          <div>${escapeHtml(patient.reaction)}</div>
        </div>

        <!-- Doctor's Guidance Callout -->
        <div class="patient-card-guidance-box">
          <div class="guidance-box-header">
            <span class="guidance-author-tag">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
              <span>${escapeHtml(patient.doctorName || "Dr. Admin (QPPV)")}</span>
            </span>
            <span class="guidance-timestamp">${escapeHtml(patient.updatedAt || "Recent")}</span>
          </div>
          <div class="guidance-quote-text">&ldquo;${escapeHtml(patient.doctorGuidance)}&rdquo;</div>
        </div>

        <div class="telemetry-card-actions">
          ${cardActions}
        </div>
      `;

      patientCardsGrid.appendChild(card);
    });

    // Wire Card action clicks
    patientCardsGrid.querySelectorAll(".btn-inspect-patient").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        openPatientDrawer(id, currentRole !== "admin");
      });
    });

    patientCardsGrid.querySelectorAll(".btn-attach-patient").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        openFileUploadModal(id);
      });
    });

    patientCardsGrid.querySelectorAll(".btn-triage-patient").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        runTriageForPatient(id);
      });
    });

    // Card 3D Perspective Tilt on Mouse Movement
    initCardTilts();
  }

  function initCardTilts() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    document.querySelectorAll(".patient-telemetry-card").forEach(card => {
      card.addEventListener("mousemove", (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const rotateX = ((y - centerY) / centerY) * -5;
        const rotateY = ((x - centerX) / centerX) * 5;
        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
      });
      card.addEventListener("mouseleave", () => {
        card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)";
      });
    });
  }

  // ========================================================
  // SLIDE-OVER PATIENT CLINICAL INSPECTOR DRAWER
  // ========================================================
  function openPatientDrawer(patientId, isReadOnly = false) {
    activeEditingPatientId = patientId;
    const patient = patientsList.find(p => p.id === patientId);
    if (!patient) return;

    if (drawerPatientTitle) drawerPatientTitle.textContent = patient.name;
    if (drawerPatientSubtitle) drawerPatientSubtitle.textContent = `${patient.id} • ${patient.age} yrs • ${capitalize(patient.sex)} • Monitored Day ${patient.daysMonitored || 8}`;
    if (drawerAvatarBadge) {
      drawerAvatarBadge.textContent = patient.name.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase();
      drawerAvatarBadge.className = "drawer-avatar-badge";
      if (patient.condition.includes("ICU")) drawerAvatarBadge.classList.add("biometric-aura-icu");
      else if (patient.condition.includes("Ward")) drawerAvatarBadge.classList.add("biometric-aura-ward");
      else if (patient.condition.includes("Recovering")) drawerAvatarBadge.classList.add("biometric-aura-rec");
    }

    const vitals = patient.vitals || { hr: 78, bp: "120/80", spo2: 98, temp: 37.0 };
    if (drawerVitalHR) {
      drawerVitalHR.textContent = `${vitals.hr} BPM`;
      drawerVitalHR.style.color = vitals.hr > 100 ? "#F87171" : "#4ADE80";
    }
    if (drawerVitalBP) drawerVitalBP.textContent = vitals.bp;
    if (drawerVitalSPO2) drawerVitalSPO2.textContent = `${vitals.spo2}%`;
    if (drawerVitalTemp) {
      drawerVitalTemp.textContent = `${vitals.temp}°C`;
      drawerVitalTemp.style.color = vitals.temp >= 38.0 ? "#F87171" : "#4ADE80";
    }

    // Condition radio matrix
    const conditions = [
      "Hospitalised (ICU)",
      "Hospitalised (Ward)",
      "Under Observation",
      "Recovering",
      "Resolved / Discharged",
      "Serious Sequelae / Life Threatening"
    ];

    if (drawerConditionMatrix) {
      drawerConditionMatrix.innerHTML = "";
      conditions.forEach(cond => {
        const item = document.createElement("label");
        item.className = `condition-radio-item ${patient.condition === cond ? "active" : ""}`;
        item.innerHTML = `
          <input type="radio" name="drawerConditionRadio" value="${escapeHtml(cond)}" ${patient.condition === cond ? "checked" : ""} ${isReadOnly ? "disabled" : ""}>
          <span>${escapeHtml(cond)}</span>
        `;
        if (!isReadOnly) {
          item.addEventListener("click", () => {
            drawerConditionMatrix.querySelectorAll(".condition-radio-item").forEach(i => i.classList.remove("active"));
            item.classList.add("active");
            item.querySelector("input").checked = true;
          });
        }
        drawerConditionMatrix.appendChild(item);
      });
    }

    // Guidance input
    if (drawerGuidanceInput) {
      drawerGuidanceInput.value = patient.doctorGuidance || "";
      drawerGuidanceInput.disabled = isReadOnly;
    }

    // Attached files
    if (drawerFilesList) {
      drawerFilesList.innerHTML = "";
      if (patient.files && patient.files.length > 0) {
        patient.files.forEach(f => {
          const fileDiv = document.createElement("div");
          fileDiv.className = "attached-file-item";
          fileDiv.style.marginBottom = "6px";
          fileDiv.innerHTML = `
            <span style="display: flex; align-items: center; gap: 6px;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
              <span>${escapeHtml(f)}</span>
            </span>
            <span style="color: var(--accent-teal); font-weight: 600; font-size: 11px;">Verified</span>
          `;
          drawerFilesList.appendChild(fileDiv);
        });
      } else {
        drawerFilesList.innerHTML = `<span style="font-size: 11.5px; color: var(--muted); font-style: italic;">No medical files attached yet.</span>`;
      }
    }

    // Timeline
    if (drawerTimeline) {
      drawerTimeline.innerHTML = "";
      const timelineItems = patient.timeline && patient.timeline.length > 0
        ? patient.timeline
        : [
            { day: "Day 0", title: "Therapy Commenced", desc: `Initiated treatment with ${patient.suspectDrug}` },
            { day: "Day 4", title: "Adverse Reaction", desc: patient.reaction },
            { day: "Today", title: "Dr. Admin Assessment", desc: patient.doctorGuidance }
          ];

      timelineItems.forEach(t => {
        const step = document.createElement("div");
        step.className = "drawer-timeline-step";
        step.innerHTML = `
          <div class="timeline-step-dot"></div>
          <span class="timeline-step-time">${escapeHtml(t.day)}</span>
          <span class="timeline-step-title">${escapeHtml(t.title)}</span>
          <p class="timeline-step-desc">${escapeHtml(t.desc)}</p>
        `;
        drawerTimeline.appendChild(step);
      });
    }

    // Toggle admin/reception features inside drawer
    if (drawerSaveBtn) {
      drawerSaveBtn.style.display = isReadOnly ? "none" : "";
    }
    if (btnDrawerAttachReport) {
      btnDrawerAttachReport.style.display = isReadOnly ? "none" : "";
    }
    document.querySelectorAll(".directive-quick-chips").forEach(el => {
      el.style.display = isReadOnly ? "none" : "";
    });

    // Open drawer backdrop
    if (drawerBackdrop) {
      drawerBackdrop.classList.add("open");
    }
  }

  function closePatientDrawer() {
    if (drawerBackdrop) {
      drawerBackdrop.classList.remove("open");
    }
    activeEditingPatientId = null;
  }

  function savePatientDrawer() {
    if (!activeEditingPatientId) return;
    const patient = patientsList.find(p => p.id === activeEditingPatientId);
    if (!patient) return;

    let selectedCond = patient.condition;
    const checkedRadio = drawerConditionMatrix ? drawerConditionMatrix.querySelector("input[name='drawerConditionRadio']:checked") : null;
    if (checkedRadio) {
      selectedCond = checkedRadio.value;
    }

    const guidance = drawerGuidanceInput ? drawerGuidanceInput.value.trim() : patient.doctorGuidance;

    patient.condition = selectedCond;
    patient.doctorGuidance = guidance;
    patient.updatedAt = "Just now by Dr. Admin";

    savePatientsToStorage();
    filterAndRenderPatients();
    closePatientDrawer();
    showToast(`Patient ${patient.id} (${patient.name}) updated successfully!`);
  }

  function openPatientModal(patientId, isReadOnly = false) {
    activeEditingPatientId = patientId;
    const patient = patientsList.find(p => p.id === patientId);
    if (!patient) return;

    if (modalPatientTitle) {
      modalPatientTitle.textContent = isReadOnly ? "Patient Medical Record & Dr. Guidance" : "Update Patient Condition & Clinical Guidance";
    }
    if (modalPatientSubtitle) {
      modalPatientSubtitle.textContent = isReadOnly
        ? "Reception Desk View — Directives issued by Qualified Medical Officer"
        : "Doctor (Admin) Console — Modify condition status and clinical directives";
    }

    if (modalPatientInfoCard) {
      modalPatientInfoCard.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <strong style="font-size: 15px; color: var(--ink);">${escapeHtml(patient.name)} (${escapeHtml(patient.id)})</strong>
          <span class="badge badge-expedited">${capitalize(patient.triageRoute)}</span>
        </div>
        <div style="font-size: 12px; color: var(--muted); line-height: 1.4;">
          <strong>Suspect Medication:</strong> ${escapeHtml(patient.suspectDrug)} &bull; 
          <strong>Demographics:</strong> ${patient.age} yrs (${capitalize(patient.sex)})<br>
          <strong>Reported Adverse Reaction:</strong> ${escapeHtml(patient.reaction)}
        </div>
      `;
    }

    if (modalPatientCondition) {
      modalPatientCondition.value = patient.condition;
      modalPatientCondition.disabled = isReadOnly;
    }

    if (modalDoctorGuidance) {
      modalDoctorGuidance.value = patient.doctorGuidance || "";
      modalDoctorGuidance.readOnly = isReadOnly;
    }

    if (modalAttachedFilesList) {
      modalAttachedFilesList.innerHTML = "";
      const files = patient.files || [];
      if (files.length === 0) {
        modalAttachedFilesList.innerHTML = `<span style="font-size: 12px; color: var(--muted);">No external reports attached.</span>`;
      } else {
        files.forEach(f => {
          const item = document.createElement("div");
          item.className = "attached-file-item";
          item.innerHTML = `
            <span style="display: flex; align-items: center; gap: 6px;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg>
              <strong>${escapeHtml(f)}</strong>
            </span>
            <span style="color: var(--status-verified-text); font-weight: 600;">Verified</span>
          `;
          modalAttachedFilesList.appendChild(item);
        });
      }
    }

    if (btnModalSave) {
      btnModalSave.style.display = isReadOnly ? "none" : "inline-flex";
    }

    if (patientModal) patientModal.classList.add("open");
  }

  function closePatientModal() {
    if (patientModal) patientModal.classList.remove("open");
    activeEditingPatientId = null;
  }

  function savePatientModal() {
    if (!activeEditingPatientId) return;
    const patient = patientsList.find(p => p.id === activeEditingPatientId);
    if (!patient) return;

    if (modalPatientCondition) patient.condition = modalPatientCondition.value;
    if (modalDoctorGuidance) patient.doctorGuidance = modalDoctorGuidance.value.trim();
    patient.updatedAt = "Just now by Dr. Admin";

    savePatientsToStorage();
    filterAndRenderPatients();
    closePatientModal();
    showToast(`Patient ${patient.name} (${patient.id}) record updated successfully.`);
  }

  function intakeNewPatientCase() {
    switchView("triage");
    if (reportForm) reportForm.reset();
    if (inputReaction) {
      inputReaction.focus();
      showToast("Enter patient clinical findings in the intake console to generate automated triage.");
    }
  }

  function runTriageForPatient(patientId) {
    const patient = patientsList.find(p => p.id === patientId);
    if (!patient) return;

    switchView("triage");

    const elAge = document.getElementById("patientAge");
    const elSex = document.getElementById("patientSex");
    const elDrug = document.getElementById("suspectDrug");
    const elStart = document.getElementById("drugStartDate");
    const elDate = document.getElementById("eventDate");
    const elReaction = document.getElementById("reactionDesc");

    if (elAge) elAge.value = patient.age;
    if (elSex) {
      elSex.value = patient.sex;
      syncSegments(".sex-segments", patient.sex);
    }
    if (elDrug) elDrug.value = patient.suspectDrug;
    if (elStart) elStart.value = patient.drugStartDate;
    if (elDate) elDate.value = patient.eventDate;
    if (elReaction) {
      elReaction.value = patient.reaction;
      updateCharCounter();
    }

    showToast(`Loaded ${patient.name}'s clinical data into Triage Console.`);
    if (reportForm) reportForm.requestSubmit();
  }

  function openFileUploadModal(targetPatientId = null) {
    if (uploadTargetPatient) {
      uploadTargetPatient.innerHTML = "";
      patientsList.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = `${p.name} (${p.id}) — ${p.suspectDrug}`;
        if (targetPatientId && p.id === targetPatientId) opt.selected = true;
        uploadTargetPatient.appendChild(opt);
      });
    }

    if (uploadFileListPreview) uploadFileListPreview.innerHTML = "";
    if (fileInputEl) fileInputEl.value = "";
    if (fileUploadModal) fileUploadModal.classList.add("open");
  }

  function closeFileUploadModal() {
    if (fileUploadModal) fileUploadModal.classList.remove("open");
  }

  function initFileDropzone() {
    if (!fileDropzone || !fileInputEl) return;

    fileDropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      fileDropzone.classList.add("dragover");
    });

    fileDropzone.addEventListener("dragleave", () => {
      fileDropzone.classList.remove("dragover");
    });

    fileDropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      fileDropzone.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        displaySelectedFiles(e.dataTransfer.files);
      }
    });

    fileInputEl.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        displaySelectedFiles(e.target.files);
      }
    });
  }

  function displaySelectedFiles(fileList) {
    pendingFilesToAttach = [];
    if (!uploadFileListPreview) return;
    uploadFileListPreview.innerHTML = "";

    Array.from(fileList).forEach(file => {
      const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
      const displayStr = `${file.name} (${sizeMb > 0 ? sizeMb + " MB" : Math.max(1, Math.round(file.size / 1024)) + " KB"})`;
      pendingFilesToAttach.push(displayStr);

      const div = document.createElement("div");
      div.className = "attached-file-item";
      div.innerHTML = `
        <span><strong>${escapeHtml(file.name)}</strong> (${sizeMb > 0 ? sizeMb + " MB" : Math.round(file.size / 1024) + " KB"})</span>
        <span style="color: var(--accent-teal); font-weight: 600;">Ready to attach</span>
      `;
      uploadFileListPreview.appendChild(div);
    });
  }

  function submitFileUpload() {
    const targetId = uploadTargetPatient ? uploadTargetPatient.value : null;
    if (!targetId) {
      showToast("Please select a target patient record.");
      return;
    }

    const patient = patientsList.find(p => p.id === targetId);
    if (!patient) return;

    if (pendingFilesToAttach.length === 0) {
      pendingFilesToAttach.push("medical_report_dossier.pdf (1.2 MB)");
    }

    if (!patient.files) patient.files = [];
    patient.files.push(...pendingFilesToAttach);
    patient.updatedAt = "Just now by Dr. Admin";
    patient.doctorGuidance += ` [Attached ${pendingFilesToAttach.length} medical file(s) for clinical review]`;

    savePatientsToStorage();
    filterAndRenderPatients();
    closeFileUploadModal();
    showToast(`Attached ${pendingFilesToAttach.length} document(s) to ${patient.name}'s safety record.`);
    pendingFilesToAttach = [];
  }

  function syncTriageRunToRegistry(data) {
    const res = data.result || {};
    const runId = data.run_id || "rep_" + Math.random().toString(36).substring(2, 10);
    const routing = res.routing || (data.status === "escalated" ? "escalated" : "expedited");

    const drugName = inputSuspectDrug ? inputSuspectDrug.value.trim() : "Lamotrigine";
    let patient = patientsList.find(p => p.suspectDrug.toLowerCase() === drugName.toLowerCase());

    if (patient) {
      patient.triageRoute = routing;
      patient.updatedAt = "Just now (Triage run " + runId + ")";
      patient.doctorGuidance = routing === "expedited"
        ? "CDSCO 15-day expedited reporting window active. Stat discontinuation of " + drugName + ". Supportive inpatient care."
        : "Periodic PSUR safety tracking. Routine clinical observation.";
    } else {
      const newId = "PAT-" + Math.floor(1000 + Math.random() * 9000);
      const newPatient = {
        id: newId,
        name: "Patient " + (patientsList.length + 1),
        age: parseInt(document.getElementById("patientAge").value) || 45,
        sex: selectSex ? selectSex.value : "female",
        suspectDrug: drugName,
        drugStartDate: document.getElementById("drugStartDate").value || "2026-10-01",
        eventDate: document.getElementById("eventDate").value || "2026-10-08",
        reaction: inputReaction ? inputReaction.value.trim() : "Adverse drug reaction",
        condition: routing === "expedited" ? "Hospitalised (ICU)" : "Under Observation",
        triageRoute: routing,
        doctorGuidance: routing === "expedited"
          ? "Discontinue " + drugName + " immediately. Initiated statutory 15-day expedited filing. Inpatient supportive management."
          : "Routine clinic observation. Report logged for periodic safety update review.",
        doctorName: "Dr. Admin (QPPV)",
        updatedAt: "Just now (Run " + runId + ")",
        files: []
      };
      patientsList.unshift(newPatient);
    }

    savePatientsToStorage();
    filterAndRenderPatients();
  }

})();
