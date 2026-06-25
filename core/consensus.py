"""
core/consensus.py — turn N model answers to the same prompt into a trust verdict.

The cross-model debugger (routes/debug_prompt.py) shows answers side by side.
This is the accountability layer on top: it measures how much the models *agree*,
names the dissenter when one diverges, and picks the most representative answer —
so the result reads as "consensus: …" or "models disagree, here's where", never a
bare pick.

Everything here is deterministic and inspectable: the full pairwise cosine matrix
travels with the verdict, so the judgement is never a black box. Thresholds are
heuristic (answers to one prompt share vocabulary, so baseline similarity runs
high — these are calibrated for that) and tunable; the raw numbers always ship
alongside the label.

The embedder is injected (`analyze(texts, embed_fn)`) so the math is unit-testable
without a model; in production `embed_fn` is nomic-embed-text via Ollama.
"""
from __future__ import annotations

import numpy as np

# Verdict thresholds on the mean off-diagonal cosine similarity (0..1).
CONSENSUS_THRESHOLD = 0.82
PARTIAL_THRESHOLD = 0.68
# A candidate is flagged a dissenter when its mean similarity to the others falls
# this far below the overall agreement score (only meaningful with >= 3 answers).
DISSENT_MARGIN = 0.08


def _cosine_matrix(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = vecs / norms
    return np.clip(unit @ unit.T, -1.0, 1.0)


def analyze(texts: list[str], embed_fn) -> dict:
    """Compute the agreement structure over `texts`.

    `embed_fn(text) -> list[float]` is injected. Returns a dict whose `matrix`
    and `per_candidate` are indexed by the ORIGINAL position in `texts` (empty /
    failed slots carry `None`), so a UI can line them up with the candidate list.

    Fewer than two non-empty texts → verdict "single" (nothing to compare).
    """
    clean = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
    if len(clean) < 2:
        return {
            "n": len(clean),
            "agreement_score": None,
            "verdict": "single",
            "matrix": [],
            "per_candidate": [None] * len(texts),
            "representative_index": clean[0][0] if clean else None,
            "dissenters": [],
        }

    idx = [i for i, _ in clean]
    vecs = np.array([embed_fn(t) for _, t in clean], dtype=np.float32)
    M = _cosine_matrix(vecs)
    n = len(idx)

    off = M.astype(np.float64).copy()
    np.fill_diagonal(off, np.nan)
    per = np.nanmean(off, axis=1)          # each answer's mean sim to the OTHERS
    agreement = float(np.nanmean(off))     # overall off-diagonal mean

    representative_index = idx[int(np.argmax(per))]   # centroid = most representative
    dissenters = [
        idx[k] for k in range(n)
        if n >= 3 and per[k] < agreement - DISSENT_MARGIN
    ]

    if agreement >= CONSENSUS_THRESHOLD:
        verdict = "consensus"
    elif agreement >= PARTIAL_THRESHOLD:
        verdict = "partial"
    else:
        verdict = "divergent"

    # Re-expand to original positions (failed/empty slots stay None).
    full = [[None] * len(texts) for _ in texts]
    per_full: list = [None] * len(texts)
    for a in range(n):
        per_full[idx[a]] = round(float(per[a]), 4)
        for b in range(n):
            full[idx[a]][idx[b]] = round(float(M[a][b]), 4)

    return {
        "n": n,
        "agreement_score": round(agreement, 4),
        "verdict": verdict,
        "matrix": full,
        "per_candidate": per_full,
        "representative_index": representative_index,
        "dissenters": dissenters,
    }


def summarize(analysis: dict) -> str:
    """One-line, human-readable gloss of a verdict (for logs / memory mirrors)."""
    v = analysis.get("verdict")
    score = analysis.get("agreement_score")
    if v == "single":
        return "Only one answer — nothing to compare."
    if v == "consensus":
        return f"Strong consensus ({score:.0%} agreement)."
    if v == "partial":
        d = analysis.get("dissenters") or []
        tail = f"; {len(d)} dissenter(s)" if d else ""
        return f"Partial agreement ({score:.0%}){tail}."
    return f"Models diverge ({score:.0%} agreement) — answers materially differ."
