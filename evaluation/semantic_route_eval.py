"""
semantic_route_eval.py — does semantic routing close the keyword-free gap?

CONTEXT
-------
`adversarial_eval.py` (scaled to 91 held-out, keyword-free prompts on 2026-07-03)
revealed a structural failure: the keyword-only fast path scores 30.8% on hard
prompts, and 81% of every misroute falls into `knowledge_learning`. Root cause:
`detect_domain` is purely keyword-based, so a prompt with no trigger keyword gets
domain="general" (conf 0.0) and `signal_route` dumps it into the
`knowledge_learning` fallthrough. That bucket is effectively "unrecognised".

Any *lexical* patch would just be more keywords tuned to the adversarial set —
which would burn the held-out set (the circularity trap the adversarial module
warns about). The architecturally honest fix is SEMANTIC: route by nearest-
neighbour in embedding space to labelled EXEMPLARS drawn from the TRAINING
distribution (`training.auto_train.PROMPTS`), never from the adversarial set. The
adversarial prompts therefore stay genuinely held-out — this is a fair
generalisation test.

STRATEGIES COMPARED (on the 91-prompt adversarial set)
------------------------------------------------------
  keyword       — production `signal_route` (baseline; the 30.8% number)
  semantic_k1   — pure 1-NN cosine to training exemplars
  semantic_k5   — 5-NN cosine, majority vote (ties → nearest)
  hybrid_fix    — the proposed production change: run `signal_route`; ONLY when it
                  returns the `knowledge_learning` fallthrough, replace that with
                  the semantic k-NN answer. Confident keyword routes and the
                  factual/terse fast paths are left untouched.

Requires Ollama with an embedding model (nomic-embed-text). Embeddings are cached
to the scratchpad so re-runs are instant.

Run:
    PYTHONPATH=. python3 evaluation/semantic_route_eval.py
    PYTHONPATH=. python3 evaluation/semantic_route_eval.py --k 5
"""

import os
import sys
import json
import math
import hashlib
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.ablation_eval import signal_route          # keyword baseline
from evaluation.adversarial_eval import PROMPTS as ADV_PROMPTS
from training.auto_train import PROMPTS as TRAIN_PROMPTS    # labelled exemplars
from providers.ollama import OllamaEmbeddingProvider

_CACHE = os.path.join(
    os.environ.get("SEMANTIC_EVAL_CACHE", "/tmp"), "semantic_route_embcache.json"
)


# ── embedding + cache ──────────────────────────────────────────────────────
def _load_cache() -> dict:
    try:
        with open(_CACHE) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    try:
        with open(_CACHE, "w") as fh:
            json.dump(cache, fh)
    except OSError:
        pass


def _key(model: str, text: str) -> str:
    return hashlib.sha1(f"{model}\x00{text}".encode()).hexdigest()


def embed_all(texts: list[str], provider, cache: dict) -> list[list[float]]:
    """Embed each text, using (and updating) the on-disk cache. Prints progress."""
    model = provider.model_id
    out, misses = [], 0
    for i, t in enumerate(texts):
        k = _key(model, t)
        vec = cache.get(k)
        if vec is None:
            vec = provider.embed(t)
            cache[k] = vec
            misses += 1
            if misses % 20 == 0:
                print(f"    embedded {misses} new (of {len(texts)})…", flush=True)
        out.append(vec)
    if misses:
        _save_cache(cache)
        print(f"    embedded {misses} new vectors ({len(texts) - misses} cache hits)")
    else:
        print(f"    all {len(texts)} vectors from cache")
    return out


# ── cosine + k-NN ──────────────────────────────────────────────────────────
def _norm(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _cos_presorted(a: list[float], b: list[float]) -> float:
    """Dot product of two already-unit-normalised vectors == cosine similarity."""
    return sum(x * y for x, y in zip(a, b))


def knn_route(qvec, ex_vecs, ex_labels, k: int) -> str:
    sims = sorted(
        ((_cos_presorted(qvec, ev), lab) for ev, lab in zip(ex_vecs, ex_labels)),
        key=lambda t: -t[0],
    )
    top = sims[:k]
    if k == 1:
        return top[0][1]
    votes: dict = {}
    for rank, (_, lab) in enumerate(top):
        # rank-weighted vote so ties break toward the nearer exemplar
        votes[lab] = votes.get(lab, 0.0) + 1.0 / (rank + 1)
    return max(votes.items(), key=lambda kv: kv[1])[0]


# ── scoring ────────────────────────────────────────────────────────────────
def score(name: str, route_fn) -> dict:
    correct, sink, misses = 0, 0, []
    for pid, expected, category, prompt in ADV_PROMPTS:
        got = route_fn(pid, expected, category, prompt)
        if got == expected:
            correct += 1
        else:
            misses.append((expected, got))
            if got == "knowledge_learning":
                sink += 1
    n = len(ADV_PROMPTS)
    return {
        "name": name, "correct": correct, "n": n,
        "acc": correct / n, "sink": sink, "n_miss": len(misses),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5, help="k for the semantic_kN row")
    args = ap.parse_args()

    print("=" * 66)
    print("  Semantic routing prototype — closing the keyword-free gap")
    print(f"  Held-out prompts: {len(ADV_PROMPTS)}   Exemplars: {len(TRAIN_PROMPTS)}")
    print("=" * 66)

    # Backend selectable so this eval can compare embed providers apples-to-apples.
    # AGENTIC_EMBED_BACKEND=onnx uses the local ONNX model; default stays Ollama.
    if os.getenv("AGENTIC_EMBED_BACKEND", "ollama").lower() == "onnx":
        from providers.onnx_embed import ONNXEmbeddingProvider
        provider = ONNXEmbeddingProvider()
    else:
        provider = OllamaEmbeddingProvider()
    print(f"  Embed backend: {provider.model_id}")
    cache = _load_cache()

    ex_labels = [p[1] for p in TRAIN_PROMPTS]     # field[1] is already the agent
    print("\n  Embedding training exemplars…")
    ex_vecs = [_norm(v) for v in embed_all([p[3] for p in TRAIN_PROMPTS], provider, cache)]

    print("  Embedding held-out prompts…")
    adv_texts = [p[3] for p in ADV_PROMPTS]
    adv_vecs = {p[0]: _norm(v)
                for p, v in zip(ADV_PROMPTS, embed_all(adv_texts, provider, cache))}

    def sem(k):
        return lambda pid, exp, cat, prompt: knn_route(adv_vecs[pid], ex_vecs, ex_labels, k)

    def hybrid(pid, exp, cat, prompt):
        kw = signal_route(prompt)
        if kw == "knowledge_learning":            # only override the fallthrough sink
            return knn_route(adv_vecs[pid], ex_vecs, ex_labels, args.k)
        return kw

    rows = [
        score("keyword (baseline)", lambda pid, e, c, p: signal_route(p)),
        score("semantic_k1",        sem(1)),
        score(f"semantic_k{args.k}", sem(args.k)),
        score("hybrid_fix",         hybrid),
    ]

    print("\n  Strategy               Acc     Correct   KL-sink/miss")
    print("  " + "-" * 54)
    base = rows[0]["acc"]
    for r in rows:
        delta = r["acc"] - base
        d = "        " if r["name"].startswith("keyword") else f"  ({delta:+.1%})"
        sinkpct = f"{r['sink']}/{r['n_miss']}" if r["n_miss"] else "0/0"
        print(f"  {r['name']:20s}  {r['acc']:5.1%}  {r['correct']:3d}/{r['n']}"
              f"   {sinkpct:>7s}{d}")

    print("\n  Read:")
    print("  • keyword = today's production fast path (the honest 30.8%).")
    print("  • hybrid_fix = minimal proposed change: semantic k-NN replaces ONLY the")
    print("    knowledge_learning fallthrough; confident keyword routes untouched.")
    print("  • Exemplars are from the TRAINING set, so the adversarial set stays")
    print("    held-out — this is a generalisation number, not a fit.")
    print("\n  Caveat: nomic-embed-text adds ~one embed call per unrouted query on the")
    print("  hot path. Measure latency before shipping; cache exemplars once at boot.")


if __name__ == "__main__":
    main()
