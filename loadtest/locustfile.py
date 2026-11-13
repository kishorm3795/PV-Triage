"""loadtest/locustfile.py - Locust load testing with complete-run latency measurement.

Measures the complete submission-to-terminal-result lifecycle:
1. POST /v1/reports with a validated adverse event report payload.
2. Poll GET /v1/runs/{run_id} until terminal state (completed, escalated, or failed).
3. Record the total elapsed time (submission to terminal result) as a custom
   Locust metric: '[E2E] Complete Run (Submission to Result)'.

Meets Requirement D6 of Mini Project 14.
"""

from __future__ import annotations

import os
import random
import time
import uuid
from locust import HttpUser, between, task

# Configurable polling parameters
POLL_INTERVAL_S = float(os.getenv("LOADTEST_POLL_INTERVAL_S", "0.05"))
POLL_TIMEOUT_S = float(os.getenv("LOADTEST_POLL_TIMEOUT_S", "35.0"))
REPEAT_RATIO = float(os.getenv("LOADTEST_REPEAT_RATIO", "0.5"))  # Phase 6 repeat request mix ratio

# Representative valid adverse event payloads
SAMPLE_REPORTS = [
    {
        "suspect_drug": "Lamotrigine",
        "reporter_type": "physician",
        "patient_age": 42,
        "patient_sex": "female",
        "drug_start_date": "2024-01-01",
        "event_date": "2024-01-08",
        "reaction_description": "The patient's skin started peeling badly a week after starting the drug, and she was admitted to hospital.",
        "outcome": "recovering",
        "narrative": "Patient presented with erythema and epidermal detachment consistent with TEN/SJS requiring inpatient care.",
    },
    {
        "suspect_drug": "Lamotrigine",
        "reporter_type": "physician",
        "patient_age": 35,
        "patient_sex": "male",
        "drug_start_date": "2024-02-10",
        "event_date": "2024-02-18",
        "reaction_description": "Severe rash with mucocutaneous involvement and high fever following titration, resulting in hospitalization.",
        "outcome": "recovering",
        "narrative": "Patient developed generalized maculopapular rash progressing to mucosal ulceration.",
    },
    {
        "suspect_drug": "Lamotrigine",
        "reporter_type": "pharmacist",
        "patient_age": 28,
        "patient_sex": "female",
        "drug_start_date": "2024-03-01",
        "event_date": "2024-03-05",
        "reaction_description": "Mild transient somnolence and headache after morning dose. Patient did not require hospital care.",
        "outcome": "recovered",
        "narrative": "Mild expected central nervous system symptoms resolving spontaneously.",
    },
]


class PharmacovigilanceUser(HttpUser):
    """Simulates healthcare providers and safety reporters submitting AE reports."""

    # Think time between completed runs per simulated user
    wait_time = between(0.1, 0.5)

    @task
    def submit_and_track_report(self) -> None:
        """Submit a valid report and poll until final triage result is produced."""
        report_template = SAMPLE_REPORTS[int(time.time() * 1000) % len(SAMPLE_REPORTS)].copy()
        # Phase 6 repeat request mix: repeat identical report content vs unique case
        if random.random() >= REPEAT_RATIO:
            report_template["reaction_description"] = (
                f"{report_template['reaction_description']} [case {uuid.uuid4().hex[:6]}]"
            )

        report_id = f"rep_load_{uuid.uuid4().hex[:12]}"
        client_id = f"client_{uuid.uuid4().hex[:4]}"
        payload = {**report_template, "report_id": report_id}

        t_start = time.perf_counter()
        run_id = None
        error_msg = None
        response_bytes = 0

        # Step 1: Submit report to intake API
        with self.client.post(
            "/v1/reports",
            json=payload,
            headers={"X-Client-ID": client_id},
            name="POST /v1/reports",
            catch_response=True,
        ) as post_resp:
            if post_resp.status_code != 202:
                post_resp.failure(
                    f"Submission failed with HTTP {post_resp.status_code}: {post_resp.text}"
                )
                self._record_e2e_metric(
                    duration_ms=(time.perf_counter() - t_start) * 1000.0,
                    response_bytes=len(post_resp.content or b""),
                    exception=Exception(f"HTTP {post_resp.status_code}: {post_resp.text[:100]}"),
                )
                return

            try:
                body = post_resp.json()
                run_id = body.get("run_id")
                # Phase 6 Cache Hit: already completed immediately on intake
                if body.get("status") == "completed" and body.get("cached"):
                    self._record_e2e_metric(
                        duration_ms=(time.perf_counter() - t_start) * 1000.0,
                        response_bytes=len(post_resp.content or b""),
                        exception=None,
                    )
                    return
            except Exception as e:
                post_resp.failure(f"Malformed JSON response on submission: {e}")
                self._record_e2e_metric(
                    duration_ms=(time.perf_counter() - t_start) * 1000.0,
                    response_bytes=len(post_resp.content or b""),
                    exception=e,
                )
                return

        if not run_id:
            self._record_e2e_metric(
                duration_ms=(time.perf_counter() - t_start) * 1000.0,
                response_bytes=0,
                exception=Exception("Missing run_id in 202 response"),
            )
            return

        # Step 2: Poll GET /v1/runs/{run_id} until terminal status
        deadline = t_start + POLL_TIMEOUT_S
        terminal = False

        while time.perf_counter() < deadline:
            time.sleep(POLL_INTERVAL_S)

            with self.client.get(
                f"/v1/runs/{run_id}",
                name="GET /v1/runs/[id] [poll]",
                catch_response=True,
            ) as poll_resp:
                if poll_resp.status_code != 200:
                    poll_resp.failure(f"Poll error HTTP {poll_resp.status_code} for run {run_id}")
                    continue

                try:
                    data = poll_resp.json()
                    status = data.get("status")
                    if status in ("completed", "escalated", "failed"):
                        terminal = True
                        response_bytes = len(poll_resp.content or b"")
                        if status == "failed":
                            error_msg = data.get("error") or "Run marked failed in triage"
                        break
                except Exception as e:
                    poll_resp.failure(f"Poll JSON parsing failed: {e}")

        t_end = time.perf_counter()
        duration_ms = (t_end - t_start) * 1000.0

        if not terminal:
            error_msg = f"Run {run_id} did not reach terminal status within {POLL_TIMEOUT_S}s"

        exception_obj = Exception(error_msg) if error_msg else None
        self._record_e2e_metric(
            duration_ms=duration_ms,
            response_bytes=response_bytes,
            exception=exception_obj,
        )

    def _record_e2e_metric(
        self,
        duration_ms: float,
        response_bytes: int = 0,
        exception: Exception | None = None,
    ) -> None:
        """Fire custom Locust metric tracking complete submission-to-terminal-result latency."""
        self.environment.events.request.fire(
            request_type="E2E",
            name="[E2E] Complete Run (Submission to Result)",
            response_time=duration_ms,
            response_length=response_bytes,
            context={"user": self},
            exception=exception,
        )
