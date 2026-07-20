"""
End-to-end proof for #186: a `compute`-shaped query is executed in the real
run_python sandbox and the model answers from the computed output — not from a
free-handed guess.

Increment 1 (tools/agent_runtime.py) only proved the *steering* preamble is
injected. This closes the gap it left open: with AMAGRA_AGENT_TOOLS=1 +
AMAGRA_SANDBOX=1, drive the actual tool loop with a scripted model that emits a
run_python call, let the REAL sandbox run it, and assert the loop returns the
exact enumeration the evaluator's model failed to produce.

The model is scripted (no LLM) but the sandbox is real, so this exercises the
whole compute→execute path. Skips cleanly on a host where the sandbox can't run.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.agent_runtime as ar
import tools.catalog as catalog
import tools.sandbox as sbx

# The task the evaluator's model free-handed instead of computing.
_TASK = "Compute the first 12 terms of a1=1, a2=2, a_n=a_{n-1}+a_{n-2}. Do not guess."
_FIB12 = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]

_FIB_CODE = (
    "a, b = 1, 2\n"
    "seq = [a, b]\n"
    "for _ in range(10):\n"
    "    a, b = b, a + b\n"
    "    seq.append(b)\n"
    "print(seq[:12])"
)


def _sandbox_runs() -> bool:
    """True only if run_python actually executes here (else skip, don't fail).

    Restores AMAGRA_SANDBOX so this collection-time probe never leaks the enabled
    flag into other test modules.
    """
    prior = os.environ.get("AMAGRA_SANDBOX")
    try:
        os.environ["AMAGRA_SANDBOX"] = "1"
        out = sbx.run_python("print(2+2)", timeout=sbx.DEFAULT_TIMEOUT)
        return out.get("exit_code") == 0 and "4" in out.get("stdout", "")
    except Exception:
        return False
    finally:
        if prior is None:
            os.environ.pop("AMAGRA_SANDBOX", None)
        else:
            os.environ["AMAGRA_SANDBOX"] = prior


def _model_that_computes():
    """A scripted model: turn 1 emits a run_python call; turn 2 answers using the
    observation the sandbox handed back."""
    calls = {"n": 0}

    def invoke(transcript):
        calls["n"] += 1
        if calls["n"] == 1:
            return "I'll compute it.\n```tool\n" + json.dumps(
                {"tool": "run_python", "args": {"code": _FIB_CODE}}
            ) + "\n```"
        # Turn 2+: the last user turn holds "Observation from run_python: {...}".
        obs = transcript[-1][1]
        return f"The first 12 terms are {obs.split('Observation', 1)[-1]}"

    return invoke


@pytest.mark.skipif(not _sandbox_runs(), reason="run_python sandbox unavailable on this host")
def test_compute_query_is_executed_and_answered_from_real_output(monkeypatch):
    monkeypatch.setenv("AMAGRA_AGENT_TOOLS", "1")
    monkeypatch.setenv("AMAGRA_SANDBOX", "1")

    # Sanity: the steering precondition holds — run_python is really offered.
    assert "run_python" in catalog.available_tools()

    answer = ar.run_with_tools("PERSONA", _TASK, invoke=_model_that_computes())

    # The loop returned an answer built from the sandbox's real stdout, and that
    # stdout is the correctly computed sequence.
    assert answer is not None
    assert str(_FIB12) in answer


@pytest.mark.skipif(not _sandbox_runs(), reason="run_python sandbox unavailable on this host")
def test_directive_steers_to_run_python_when_sandbox_live(monkeypatch):
    # With the sandbox live, the compute directive is what leads the model to
    # run_python — assert the preamble builder injects it behind the persona.
    monkeypatch.setenv("AMAGRA_SANDBOX", "1")
    preamble = ar._augment_for_compute(_TASK, "PERSONA", catalog.available_tools())
    assert preamble.startswith("PERSONA")
    assert "run_python" in preamble
