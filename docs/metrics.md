# Pharmacovigilance Triage Evaluation Metrics Specification

This document details the mathematical definition, implementation formulas, and evaluation methodology used by the PV-Triage evaluation harness (`eval/run.py` and `eval/metrics.py`). Conforming to the RAG Triad standard (TruLens equivalent), each metric enforces rigorous auditing of regulatory claims, statutory timelines, and citations.

---

## 1. Metric Definitions & Formulas

### 1.1 Groundedness
- **Definition:** The share of assessment claims and citations that are directly supported by evidence passages retrieved during the run.
- **Formula:**
  $$\text{Groundedness} = \begin{cases} 
  1.0 & \text{if run status is } \texttt{escalated} \text{ (honest escalation)} \\
  \frac{\sum_{c \in C} \mathbf{1}[c.\text{passage\_id} \in P_{\text{retrieved}} \land c.\text{quote} \subseteq \text{text}(c.\text{passage\_id})]}{|C|} & \text{if run status is } \texttt{completed} \text{ with citations } C \\
  0.0 & \text{if completed with empty citations } (|C| = 0)
  \end{cases}$$
- **Scoring Method:** **Deterministic**. Evaluated programmatically by checking presence of cited `passage_id` in the tool execution passage map and string containment of the quote in the retrieved passage text.
- **Judge Model:** None required (fully reproducible deterministic string/key resolution).

---

### 1.2 Context Relevance
- **Definition:** The degree of semantic alignment between the clinical query terms (suspect drug, adverse reaction, patient narrative) and the corpus passages retrieved by `search_corpus`.
- **Formula:**
  $$\text{Context Relevance} = \frac{1}{|P_{\text{retrieved}}|} \sum_{p \in P_{\text{retrieved}}} \min\left(1.0, 4 \cdot \text{Jaccard}(T_Q, T_p) + \text{Boost}(Q, p)\right)$$
  Where:
  - $T_Q$ is the token set of the clinical case query (drug + reaction description + narrative).
  - $T_p$ is the token set of the retrieved passage $p$.
  - $\text{Boost}(Q, p) = 0.15 \times \mathbf{1}[\text{key statutory/clinical term} \in Q \cap p]$ (e.g., `"hospitalization"`, `"fifteen"`, `"serious"`, `"rash"`).
- **Scoring Method:** **Deterministic Token & Term Overlap** (TruLens deterministic equivalent).
- **Judge Model:** Programmatic token overlap evaluator.

---

### 1.3 Faithfulness
- **Definition:** The agreement between the triage answer claims and the exact passages it cites. Ensures cited text is an exact verbatim substring of the underlying regulatory document without alteration, omission, or hallucinated claims.
- **Formula:**
  $$\text{Faithfulness} = \begin{cases}
  1.0 & \text{if run status is } \texttt{escalated} \\
  \frac{\sum_{c \in C} \mathbf{1}[c.\text{quote} \text{ is exact verbatim substring of } \text{text}(c.\text{passage\_id})]}{|C|} & \text{if completed with citations } C \\
  0.0 & \text{if } |C| = 0
  \end{cases}$$
- **Scoring Method:** **Deterministic**. Verifies verbatim substring presence of every cited quote in the underlying retrieved passage.
- **Judge Model:** Programmatic exact-string substring matcher.

---

### 1.4 Hallucination Rate
- **Definition:** The share of completed runs that contain at least one citation that does not resolve to retrieved text OR where a claim is asserted without evidence.
- **Formula:**
  $$\text{Hallucination Rate} = \frac{\sum_{r \in R_{\text{completed}}} \mathbf{1}\left[\exists c \in r.C : c.\text{passage\_id} \notin P_{\text{retrieved}} \lor c.\text{quote} \not\subseteq \text{text}(c.\text{passage\_id})\right]}{|R_{\text{completed}}|}$$
- **Scoring Method:** **Deterministic**. Catches fabricated passage IDs or hallucinated quotes.
- **Judge Model:** Programmatic AST / string comparator.

---

### 1.5 Routing Accuracy
- **Definition:** Accuracy of expedited, periodic, or non-reportable triage routing on answerable clinical scenarios.
- **Formula:**
  $$\text{Routing Accuracy} = \frac{\sum_{s \in S_{\text{answer}}} \mathbf{1}[r_s.\text{status} = \texttt{"completed"} \land r_s.\text{routing} = s.\text{expected\_routing}]}{|S_{\text{answer}}|}$$
- **Scoring Method:** **Deterministic** comparison against validated regulatory ground truth.

---

### 1.6 Correct-Escalation Rate
- **Definition:** Proportion of ambiguous, chronologically invalid, out-of-corpus, or adversarial scenarios that correctly escalate for qualified medical review.
- **Formula:**
  $$\text{Correct-Escalation Rate} = \frac{\sum_{s \in S_{\text{escalate}}} \mathbf{1}[r_s.\text{status} = \texttt{"escalated"}]}{|S_{\text{escalate}}|}$$
- **Scoring Method:** **Deterministic** enum check (`actual_status == "escalated"`).

---

## 2. Metric Classification & Attribution

| Metric | Evaluation Type | Judge Model | Execution Mode | Target Threshold |
| :--- | :--- | :--- | :--- | :--- |
| **Groundedness** | Deterministic | None (Substring & ID resolver) | In-process & Full API | $\ge 95\%$ |
| **Context Relevance** | Deterministic Token/Keyword | None (Jaccard + Statutory Boost) | In-process & Full API | $\ge 15\%$ |
| **Faithfulness** | Deterministic | None (Verbatim containment) | In-process & Full API | $100\%$ |
| **Hallucination Rate** | Deterministic | None (Unresolved citation detector) | In-process & Full API | $0.0\%$ |
| **Routing Accuracy** | Deterministic Ground Truth | None (Contract enum comparison) | In-process & Full API | $\ge 50\%$ |
| **Correct-Escalation Rate** | Deterministic Ground Truth | None (Contract enum comparison) | In-process & Full API | $\ge 80\%$ |
