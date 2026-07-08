"""
ONNX embedding provider — local, dependency-light, no network round-trip.

WHY
---
`evaluation/semantic_latency_bench.py` showed the semantic router's cost is ~90%
Ollama embed round-trip (28ms mean / 42ms p99) and ~10% cosine scan (3ms). The
round-trip is also the reason `orchestration/semantic_fallback.py` is OFF by
default: if Ollama is down the route dies. A local ONNX sentence-embedding model
runs on CPU in ~2-5ms with zero external process, which is what lets the fallback
be flipped always-on.

This provider is a drop-in `EmbeddingProvider` (same contract as
`OllamaEmbeddingProvider`): `.model_id`, `.embed(text)`, `.dimensions()`. Select
it in the semantic router with `AGENTIC_EMBED_BACKEND=onnx`.

DEPENDENCIES (optional — imported lazily so nothing breaks if absent)
--------------------------------------------------------------------
    pip install onnxruntime tokenizers

MODEL (not vendored — fetch once, ~130MB)
-----------------------------------------
A sentence-embedding model exported to ONNX. Recommended: BAAI/bge-small-en-v1.5
(384-dim, CLS pooling). The Xenova mirror ships the files this loader expects:

    huggingface-cli download Xenova/bge-small-en-v1.5 \
        onnx/model.onnx tokenizer.json --local-dir ~/.cache/amagra/bge-small

Then point the provider at the directory holding model.onnx + tokenizer.json:

    export AGENTIC_ONNX_EMBED_DIR=~/.cache/amagra/bge-small/onnx   # model.onnx here
    # tokenizer.json is looked up in that dir OR its parent.

Env knobs:
    AGENTIC_ONNX_EMBED_DIR    directory containing model.onnx
                              (default: ~/.cache/amagra/bge-small/onnx)
    AGENTIC_ONNX_EMBED_ID     model_id / namespace tag         (default: bge-small-en-v1.5-onnx)
    AGENTIC_ONNX_POOL         cls | mean                       (default: cls — correct for BGE)
    AGENTIC_ONNX_MAXLEN       tokenizer truncation length      (default: 512)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers.base import EmbeddingProvider

# Conventional local cache path — matches the `huggingface-cli download ... --local-dir
# ~/.cache/amagra/bge-small` command in this module's header. Used when neither the
# constructor arg nor AGENTIC_ONNX_EMBED_DIR is set, so a user who followed the docs
# gets auto-detection with no env var. Absent → _ensure_loaded raises cleanly.
_DEFAULT_ONNX_DIR = os.path.join(
    os.path.expanduser("~"), ".cache", "amagra", "bge-small", "onnx"
)


class ONNXEmbeddingProvider(EmbeddingProvider):
    """Local ONNX text-embedding provider. CPU, no network."""

    def __init__(
        self,
        model_dir: str | None = None,
        model_id: str | None = None,
        pooling: str | None = None,
        max_len: int | None = None,
    ):
        self._dir     = model_dir or os.environ.get("AGENTIC_ONNX_EMBED_DIR") or _DEFAULT_ONNX_DIR
        self._id      = model_id  or os.environ.get("AGENTIC_ONNX_EMBED_ID", "bge-small-en-v1.5-onnx")
        self._pool    = (pooling  or os.environ.get("AGENTIC_ONNX_POOL", "cls")).lower()
        self._max_len = int(max_len or os.environ.get("AGENTIC_ONNX_MAXLEN", "512"))
        self._session = None
        self._tok = None
        self._dim = None
        self._input_names: set[str] = set()

    # ── lazy load ──────────────────────────────────────────────────────────
    def _ensure_loaded(self) -> None:
        if self._session is not None:
            return
        if not self._dir:
            raise RuntimeError(
                "AGENTIC_ONNX_EMBED_DIR is unset — point it at a directory "
                "containing model.onnx (see providers/onnx_embed.py header)."
            )
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise RuntimeError(
                f"ONNX embedding backend needs 'onnxruntime' and 'tokenizers' "
                f"({exc}). Install: pip install onnxruntime tokenizers"
            ) from exc

        model_path = os.path.join(self._dir, "model.onnx")
        if not os.path.exists(model_path):
            raise RuntimeError(f"model.onnx not found in {self._dir!r}")

        # tokenizer.json may live alongside model.onnx or one level up (HF layout).
        tok_path = None
        for cand in (self._dir, os.path.dirname(self._dir.rstrip("/"))):
            p = os.path.join(cand, "tokenizer.json")
            if os.path.exists(p):
                tok_path = p
                break
        if tok_path is None:
            raise RuntimeError(f"tokenizer.json not found near {self._dir!r}")

        self._tok = Tokenizer.from_file(tok_path)
        self._tok.enable_truncation(max_length=self._max_len)

        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.environ.get("AGENTIC_ONNX_THREADS", "1"))
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = ort.InferenceSession(
            model_path, sess_options=so, providers=["CPUExecutionProvider"]
        )
        self._input_names = {i.name for i in self._session.get_inputs()}

    # ── EmbeddingProvider contract ─────────────────────────────────────────
    @property
    def model_id(self) -> str:
        return self._id

    def embed(self, text: str) -> list[float]:
        self._ensure_loaded()
        import numpy as np

        enc = self._tok.encode(text)
        ids  = np.asarray([enc.ids], dtype=np.int64)
        mask = np.asarray([enc.attention_mask], dtype=np.int64)

        feeds = {}
        if "input_ids" in self._input_names:
            feeds["input_ids"] = ids
        if "attention_mask" in self._input_names:
            feeds["attention_mask"] = mask
        if "token_type_ids" in self._input_names:
            feeds["token_type_ids"] = np.zeros_like(ids)

        # First output is the token-level last_hidden_state: [1, seq, dim].
        last_hidden = self._session.run(None, feeds)[0]

        if self._pool == "mean":
            m = mask[0][:, None].astype(last_hidden.dtype)   # [seq, 1]
            summed = (last_hidden[0] * m).sum(axis=0)
            vec = summed / max(m.sum(), 1e-9)
        else:  # cls — BGE default
            vec = last_hidden[0][0]

        vec = vec.astype("float32")
        norm = float(np.linalg.norm(vec)) or 1.0
        vec = vec / norm
        if self._dim is None:
            self._dim = int(vec.shape[0])
        return vec.tolist()

    async def aembed(self, text: str) -> list[float]:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self.embed, text)

    def dimensions(self) -> int:
        if self._dim is not None:
            return self._dim
        # Known default before first embed; corrected after the first call.
        return {"bge-small-en-v1.5-onnx": 384}.get(self._id, 384)


if __name__ == "__main__":
    import time

    p = ONNXEmbeddingProvider()
    try:
        t0 = time.time()
        v = p.embed("My script silently stops halfway through a big loop.")
        dt = 1000 * (time.time() - t0)
        print(f"ok  model_id={p.model_id}  dim={len(v)}  first-embed={dt:.0f}ms (incl. load)")
        # warm timing
        ts = []
        for q in ["hello world", "how do I index a postgres table", "what is TLS"]:
            t = time.time()
            p.embed(q)
            ts.append(1000 * (time.time() - t))
        print(f"warm embed: {[f'{x:.1f}ms' for x in ts]}")
    except Exception as exc:
        print(f"[onnx_embed] not runnable here: {exc}")
