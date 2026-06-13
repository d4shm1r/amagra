"""
step_verifier.py — Per-step verification for the planning layer (Phase 34)

Checks each PlanStep's output against its success_criteria before
proceeding to dependent steps.

Design goals:
  - Fast: heuristic-only path < 1ms (no LLM call)
  - Actionable: recommendation is one of continue|retry|replan|abort
  - Calibrated: uncertainty from the PlanStep informs the pass threshold
    (high-uncertainty steps need stronger evidence to pass)
  - Transparent: all verdicts are logged to step_verify.db

Heuristic scoring (four dimensions, each 0–1):
  length_score    — response is long enough given the criteria
  criteria_score  — keywords from success_criteria appear in response
  error_score     — absence of failure signals (I cannot, error:, etc.)
  artifact_score  — code block present if the step requires code

  raw_score = 0.20 × length + 0.35 × criteria + 0.30 × error + 0.15 × artifact

Pass threshold:
  threshold = 0.55 + 0.15 × step.uncertainty
  (uncertain steps need more evidence to be trusted)

Recommendation logic:
  raw_score ≥ threshold        → continue
  raw_score ≥ threshold - 0.15 → retry (borderline, try again)
  raw_score < threshold - 0.15 → replan (step clearly failed)
  uncertainty > 0.80           → replan (step was too uncertain to trust)

Integration:
    from cognition.step_verifier import verify_step, StepVerification
    from orchestration.planner import PlanStep

    v = verify_step(step, agent_response, retries_remaining=1)
    if v.recommendation == "abort":
        break
    elif v.recommendation == "replan":
        plan = plan_query(remaining_query, ...)   # replan from this step
    elif v.recommendation == "retry":
        # re-run the step once
        ...
"""

import re
import os
import sqlite3
from dataclasses import dataclass, field
from typing import List, Optional

_DB_PATH   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "logs", "step_verify.db")
_DB_INITED = False

# ── Failure signal vocabulary ─────────────────────────────────
_ERROR_SIGNALS = frozenset([
    "i cannot", "i can't", "i'm unable", "unable to",
    "not possible", "i don't know", "i do not know",
    "no information", "not sure", "unfortunately",
    "[error:", "error:", "exception:", "traceback",
    "i apologize", "i'm sorry", "sorry, but",
])

# ── Code-producing agents ─────────────────────────────────────
_CODE_AGENTS = frozenset(["python_dev", "dotnet_dev"])

# ── Score weights ─────────────────────────────────────────────
_W_LENGTH   = 0.20
_W_CRITERIA = 0.35
_W_ERROR    = 0.30
_W_ARTIFACT = 0.15

# ── Base pass threshold + uncertainty adjustment ──────────────
_THRESH_BASE        = 0.55   # minimum score to pass
_THRESH_UNCERT_MULT = 0.15   # added per unit of step uncertainty


# ── Data model ────────────────────────────────────────────────

@dataclass
class StepVerification:
    step_id:          str
    passed:           bool
    raw_score:        float
    threshold:        float
    recommendation:   str               # continue | retry | replan | abort
    issues:           List[str]         = field(default_factory=list)
    # Score breakdown
    length_score:     float = 0.0
    criteria_score:   float = 0.0
    error_score:      float = 0.0
    artifact_score:   float = 0.0

    def __str__(self) -> str:
        return (
            f"step={self.step_id} passed={self.passed} "
            f"score={self.raw_score:.3f}/thresh={self.threshold:.3f} "
            f"→ {self.recommendation}"
            + (f"  issues={self.issues}" if self.issues else "")
        )


# ── DB persistence ────────────────────────────────────────────

def _ensure_db():
    global _DB_INITED
    if _DB_INITED:
        return
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    con = sqlite3.connect(_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS step_verify_log (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            ts               TEXT    DEFAULT CURRENT_TIMESTAMP,
            step_id          TEXT,
            agent            TEXT,
            uncertainty      REAL,
            raw_score        REAL,
            threshold        REAL,
            passed           INTEGER,
            recommendation   TEXT,
            length_score     REAL,
            criteria_score   REAL,
            error_score      REAL,
            artifact_score   REAL,
            issues           TEXT
        )
    """)
    con.execute("PRAGMA journal_mode=WAL")
    con.commit()
    con.close()
    _DB_INITED = True


def _log_verify(v: StepVerification, agent: str, uncertainty: float) -> None:
    try:
        _ensure_db()
        con = sqlite3.connect(_DB_PATH, timeout=3)
        con.execute(
            """INSERT INTO step_verify_log
               (step_id, agent, uncertainty, raw_score, threshold, passed,
                recommendation, length_score, criteria_score, error_score,
                artifact_score, issues)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (v.step_id, agent, uncertainty, v.raw_score, v.threshold,
             int(v.passed), v.recommendation,
             v.length_score, v.criteria_score, v.error_score, v.artifact_score,
             "; ".join(v.issues)),
        )
        con.commit()
        con.close()
    except Exception as e:
        print(f"[step_verifier] log error: {e}")


# ── Scoring helpers ───────────────────────────────────────────

def _length_score(response: str, success_criteria: str) -> tuple[float, list]:
    """
    Minimum expected length is proportional to criteria complexity.
    Short criteria (factual) → short response OK.
    Multi-word criteria → longer response expected.
    """
    issues = []
    n_words_resp  = len(response.split())
    n_words_crit  = len(success_criteria.split())
    min_words     = max(20, n_words_crit * 8)   # heuristic

    if n_words_resp >= min_words:
        score = 1.0
    elif n_words_resp >= min_words * 0.5:
        score = 0.5
        issues.append(f"response short ({n_words_resp} words, min ~{min_words})")
    else:
        score = 0.0
        issues.append(f"response too short ({n_words_resp} words, min ~{min_words})")
    return score, issues


def _criteria_score(response: str, success_criteria: str) -> tuple[float, list]:
    """
    Keyword presence from the success_criteria string.
    Filters stop words. Partial matches (stem match) count half.
    """
    stops = {"a", "an", "the", "and", "or", "is", "are", "was", "were",
             "be", "been", "has", "have", "had", "do", "does", "did",
             "to", "of", "in", "for", "on", "with", "as", "by",
             "that", "this", "it", "its", "at", "from", "up"}
    issues  = []
    words   = [w.strip(".,;:").lower() for w in success_criteria.split()]
    kws     = [w for w in words if len(w) > 3 and w not in stops]

    if not kws:
        return 1.0, []   # no keywords to check — give full credit

    resp_lower = response.lower()
    matches    = sum(1 for kw in kws if kw in resp_lower)
    # Partial: stem match (first 5 chars)
    partials   = sum(0.5 for kw in kws
                     if kw not in resp_lower
                     and kw[:5] in resp_lower
                     and len(kw) >= 5)
    score      = min(1.0, (matches + partials) / len(kws))

    if score < 0.5:
        missing = [kw for kw in kws if kw not in resp_lower][:3]
        issues.append(f"criteria keywords missing: {missing}")
    return round(score, 3), issues


def _error_score(response: str) -> tuple[float, list]:
    """
    Returns 1.0 if no error signals present, 0.0 if response is mainly an apology/error.
    Code blocks are stripped before checking — "raise HTTPException" is not a failure.
    """
    clean      = re.sub(r"```.*?```", "", response, flags=re.DOTALL)
    resp_lower = clean.lower()
    hits       = [s for s in _ERROR_SIGNALS if s in resp_lower]
    if not hits:
        return 1.0, []
    if len(hits) >= 3:
        return 0.0, [f"multiple failure signals: {hits[:3]}"]
    return 0.4, [f"failure signal present: {hits[0]}"]


def _artifact_score(response: str, step_description: str, agent: str) -> tuple[float, list]:
    """
    If the step description implies code output AND the agent is a code agent,
    check for a code block.  Otherwise full credit.
    """
    if agent not in _CODE_AGENTS:
        return 1.0, []

    code_intent = re.search(
        r"\b(implement|write|create|build|code|develop|generate|program)\b",
        step_description, re.IGNORECASE
    )
    if not code_intent:
        return 1.0, []

    has_code = bool(re.search(r"```", response))
    if has_code:
        return 1.0, []
    return 0.3, ["step requires code output but no code block found"]


# ── Main verifier ─────────────────────────────────────────────

def verify_step(
    step,                          # PlanStep
    response: str,
    retries_remaining: int = 1,
    log: bool = True,
) -> StepVerification:
    """
    Verify a plan step's output against its success_criteria.

    Parameters
    ----------
    step               : PlanStep (needs .step_id, .description,
                         .success_criteria, .uncertainty, .agent)
    response           : the agent's raw text response for this step
    retries_remaining  : how many retries are still available
    log                : persist to step_verify.db

    Returns
    -------
    StepVerification with recommendation in
    {continue, retry, replan, abort}
    """
    issues: List[str] = []

    # ── Score each dimension ──────────────────────────────────
    l_score,  l_issues  = _length_score(response, step.success_criteria)
    cr_score, cr_issues = _criteria_score(response, step.success_criteria)
    e_score,  e_issues  = _error_score(response)
    a_score,  a_issues  = _artifact_score(response, step.description, step.agent)

    issues.extend(l_issues + cr_issues + e_issues + a_issues)

    raw = (
        _W_LENGTH   * l_score
        + _W_CRITERIA * cr_score
        + _W_ERROR    * e_score
        + _W_ARTIFACT * a_score
    )
    raw = round(min(1.0, max(0.0, raw)), 4)

    # ── Adaptive threshold ────────────────────────────────────
    # Higher step uncertainty → require stronger evidence to proceed.
    threshold = round(
        min(0.85, _THRESH_BASE + _THRESH_UNCERT_MULT * step.uncertainty),
        4,
    )

    passed = raw >= threshold

    # ── Recommendation ────────────────────────────────────────
    if passed:
        recommendation = "continue"
    elif raw >= threshold - 0.15 and retries_remaining > 0:
        recommendation = "retry"
    elif step.uncertainty > 0.80:
        # Step was too uncertain to trust even with retries
        recommendation = "replan"
    elif retries_remaining <= 0:
        recommendation = "replan"
    else:
        recommendation = "retry"

    # Abort if error signals dominate AND no retries remain
    if e_score == 0.0 and retries_remaining <= 0:
        recommendation = "abort"

    v = StepVerification(
        step_id        = step.step_id,
        passed         = passed,
        raw_score      = raw,
        threshold      = threshold,
        recommendation = recommendation,
        issues         = issues,
        length_score   = l_score,
        criteria_score = cr_score,
        error_score    = e_score,
        artifact_score = a_score,
    )

    if log:
        _log_verify(v, step.agent, step.uncertainty)

    return v


# ── Aggregate stats ───────────────────────────────────────────

def verify_stats(n: int = 200) -> dict:
    """Recent verification outcomes for dashboard display."""
    try:
        _ensure_db()
        con  = sqlite3.connect(_DB_PATH, timeout=3)
        rows = con.execute(
            "SELECT passed, recommendation, raw_score, agent "
            "FROM step_verify_log ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        con.close()
    except Exception:
        return {}

    if not rows:
        return {}

    total     = len(rows)
    passed    = sum(1 for r in rows if r[0])
    recs: dict = {}
    scores    = [r[2] for r in rows]
    for r in rows:
        recs[r[1]] = recs.get(r[1], 0) + 1

    return {
        "n":           total,
        "pass_rate":   round(passed / total, 2),
        "mean_score":  round(sum(scores) / len(scores), 3),
        "by_recommendation": {k: round(v/total, 2) for k, v in recs.items()},
    }


# ── CLI test ─────────────────────────────────────────────────

if __name__ == "__main__":
    from orchestration.planner import PlanStep

    print("=" * 65)
    print("  step_verifier.py — heuristic verification tests")
    print("=" * 65)

    def make_step(sid, desc, agent, criteria, uncertainty):
        return PlanStep(
            step_id=sid, description=desc, agent=agent,
            success_criteria=criteria, uncertainty=uncertainty,
        )

    CASES = [
        # (step, response, retries, label)
        (
            make_step("step_1", "Implement FastAPI endpoint with auth",
                      "python_dev", "Endpoint working with JWT", 0.4),
            """Here is a FastAPI endpoint with JWT authentication:

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import jwt

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/protected")
async def protected_route(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, "secret", algorithms=["HS256"])
        return {"user": payload["sub"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
```

This endpoint validates JWT tokens using the OAuth2 scheme.""",
            1,
            "Good code response with code block",
        ),
        (
            make_step("step_2", "Implement database schema",
                      "python_dev", "Schema defined with tables", 0.4),
            "I cannot help with that request as it involves database design.",
            0,
            "Failure signal, no retries",
        ),
        (
            make_step("step_3", "Explain the architecture",
                      "knowledge_learning", "Architecture clearly defined", 0.25),
            "The architecture uses a layered approach with FastAPI serving as the API layer, "
            "connected to a PostgreSQL database through SQLAlchemy ORM. "
            "The system uses JWT for authentication and has separate layers for "
            "routing, business logic, and data access.",
            1,
            "Good explanation (no code required)",
        ),
        (
            make_step("step_4", "Write pytest tests for the endpoint",
                      "python_dev", "Test suite passes", 0.35),
            "You should test your endpoint by sending HTTP requests to it.",
            1,
            "Too short, no code block, misses criteria",
        ),
        (
            make_step("step_5", "Research multi-agent coordination",
                      "ai_ml", "Key patterns identified", 0.75),
            "Multi-agent coordination involves several patterns. "
            "The key patterns identified include: (1) hierarchical delegation where "
            "a planner assigns tasks to specialists, (2) peer-to-peer negotiation "
            "where agents bid for tasks, and (3) blackboard systems where agents "
            "share a common knowledge store. These patterns are identified in "
            "recent literature on autonomous systems.",
            1,
            "High-uncertainty research step, reasonable response",
        ),
    ]

    print()
    for step, response, retries, label in CASES:
        v = verify_step(step, response, retries_remaining=retries, log=False)
        print(f"  [{label}]")
        print(f"    {v}")
        print(f"    scores: length={v.length_score:.2f} criteria={v.criteria_score:.2f} "
              f"error={v.error_score:.2f} artifact={v.artifact_score:.2f}")
        print()
