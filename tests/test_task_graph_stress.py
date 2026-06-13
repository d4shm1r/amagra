"""
Stress tests for task_graph.py — no LLM required.

Five test layers:
  1. State machine — legal and illegal transitions
  2. Dependency graphs — topologies: linear, fan-out, fan-in, deep chains, cycles
  3. Crash recovery — reset_running() restores consistent state
  4. Idempotency — repeated operations don't corrupt state
  5. Adversarial verification — _verify() rejects bad agent outputs

Run with:  python3 -m pytest tests/test_task_graph_stress.py -v
       or:  python3 tests/test_task_graph_stress.py
"""

import os
import random
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import infrastructure.task_graph as tg
from infrastructure.executor import _verify, _classify_failure

# ── Test DB isolation ─────────────────────────────────────────
# Use a throw-away DB so tests never touch the live tasks.db.

_TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_tasks.db")

_orig_db = tg.DB_PATH
tg.DB_PATH = _TEST_DB


def setup():
    """Reset test DB before each test."""
    if os.path.exists(_TEST_DB):
        os.remove(_TEST_DB)
    tg.init_db()


def teardown():
    """Remove test DB after each test."""
    if os.path.exists(_TEST_DB):
        os.remove(_TEST_DB)


def _make_step(sid, agent="python_dev", prompt="do the thing", depends_on=None):
    return {
        "id":         sid,
        "agent":      agent,
        "prompt":     prompt,
        "depends_on": depends_on or [],
    }


def _raw_status(graph_id=None, step_id=None, *, graph_id_for_step=None):
    """Read status directly from DB to bypass any caching."""
    conn = sqlite3.connect(_TEST_DB)
    if step_id is not None:
        row = conn.execute(
            "SELECT status FROM task_steps WHERE graph_id=? AND step_id=?",
            (graph_id_for_step, step_id)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT status FROM task_graphs WHERE id=?", (graph_id,)
        ).fetchone()
    conn.close()
    return row[0] if row else None


def _force_status(graph_id, step_id, status):
    """Bypass enforcement — directly set step status in DB (for crash simulation)."""
    conn = sqlite3.connect(_TEST_DB)
    conn.execute(
        "UPDATE task_steps SET status=? WHERE graph_id=? AND step_id=?",
        (status, graph_id, step_id)
    )
    conn.commit()
    conn.close()


def _force_graph_status(graph_id, status):
    conn = sqlite3.connect(_TEST_DB)
    conn.execute("UPDATE task_graphs SET status=? WHERE id=?", (status, graph_id))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# LAYER 1: State Machine Stress Tests
# ═══════════════════════════════════════════════════════════════

STEP_TRANSITION_MATRIX = [
    # (from_status, to_fn, expected_allowed)
    ("pending",   "running",   True),
    ("running",   "completed", True),
    ("running",   "failed",    True),
    # Illegal paths
    ("completed", "running",   False),
    ("completed", "failed",    False),
    ("failed",    "running",   False),
    ("failed",    "completed", False),
    ("pending",   "completed", False),
    ("pending",   "failed",    False),
]

GRAPH_TRANSITION_MATRIX = [
    # (from_status, to_status, expected_allowed)
    ("pending",   "running",   True),
    ("running",   "completed", True),
    ("running",   "failed",    True),
    ("running",   "paused",    True),
    ("paused",    "running",   True),
    # Illegal
    ("completed", "running",   False),
    ("completed", "pending",   False),
    ("completed", "failed",    False),
    ("failed",    "running",   False),
    ("failed",    "completed", False),
]


def test_step_transition_matrix():
    """Every cell in the step transition matrix must match the enforcement logic."""
    passed = failed_cases = 0

    for from_status, to_status, should_pass in STEP_TRANSITION_MATRIX:
        setup()
        g_id = tg.create_graph("transition test", [_make_step("s1")])
        _force_status(g_id, "s1", from_status)

        try:
            if to_status == "running":
                tg.mark_step_running(g_id, "s1", {})
            elif to_status == "completed":
                tg.mark_step_completed(g_id, "s1", {})
            elif to_status == "failed":
                tg.mark_step_failed(g_id, "s1", "error", "agent_error")
            succeeded = True
        except tg.TransitionError:
            succeeded = False

        ok = (succeeded == should_pass)
        mark = "✓" if ok else "✗"
        allow = "allowed" if should_pass else "illegal"
        print(f"  {mark} step {from_status!r:12} → {to_status!r:12}  ({allow})")
        if ok:
            passed += 1
        else:
            failed_cases += 1

    teardown()
    assert failed_cases == 0, f"{failed_cases} step transition(s) behaved incorrectly"
    print(f"  → {passed}/{passed + failed_cases} step transitions correct")


def test_graph_transition_matrix():
    """Every cell in the graph transition matrix must match enforcement logic."""
    passed = failed_cases = 0

    for from_status, to_status, should_pass in GRAPH_TRANSITION_MATRIX:
        setup()
        g_id = tg.create_graph("graph transition test", [_make_step("s1")])
        _force_graph_status(g_id, from_status)

        try:
            tg.update_graph_status(g_id, to_status)
            succeeded = True
        except tg.TransitionError:
            succeeded = False

        ok = (succeeded == should_pass)
        mark = "✓" if ok else "✗"
        allow = "allowed" if should_pass else "illegal"
        print(f"  {mark} graph {from_status!r:12} → {to_status!r:12}  ({allow})")
        if ok:
            passed += 1
        else:
            failed_cases += 1

    teardown()
    assert failed_cases == 0, f"{failed_cases} graph transition(s) behaved incorrectly"
    print(f"  → {passed}/{passed + failed_cases} graph transitions correct")


def test_retry_reopens_failed_step():
    """retry_step() is the only legal path from failed → pending."""
    setup()
    g_id = tg.create_graph("retry test", [_make_step("s1")])
    tg.mark_step_running(g_id, "s1", {})
    tg.mark_step_failed(g_id, "s1", "oops", "agent_error")
    _force_graph_status(g_id, "failed")

    assert _raw_status(graph_id=g_id) == "failed"
    assert _raw_status(graph_id_for_step=g_id, step_id="s1") == "failed"

    result = tg.retry_step(g_id, "s1")
    assert result is True, "retry_step should return True for a failed step"
    assert _raw_status(graph_id_for_step=g_id, step_id="s1") == "pending"
    assert _raw_status(graph_id=g_id) == "pending"
    teardown()
    print("  ✓ retry_step: failed → pending works")


def test_retry_on_non_failed_step_returns_false():
    """retry_step() on a pending or completed step must return False."""
    setup()
    g_id = tg.create_graph("retry guard", [_make_step("s1"), _make_step("s2")])
    result = tg.retry_step(g_id, "s1")
    assert result is False, "retry_step on pending step must return False"

    tg.mark_step_running(g_id, "s1", {})
    tg.mark_step_completed(g_id, "s1", {})
    result = tg.retry_step(g_id, "s1")
    assert result is False, "retry_step on completed step must return False"
    teardown()
    print("  ✓ retry_step: non-failed step returns False")


# ═══════════════════════════════════════════════════════════════
# LAYER 2: Dependency Graph Stress Tests
# ═══════════════════════════════════════════════════════════════

def test_linear_chain():
    """A → B → C: steps run in strict order, no skipping."""
    setup()
    g_id = tg.create_graph("linear chain", [
        _make_step("A"),
        _make_step("B", depends_on=["A"]),
        _make_step("C", depends_on=["B"]),
    ])

    # Only A should be ready initially
    step = tg.next_pending_step(g_id)
    assert step["step_id"] == "A"
    tg.mark_step_running(g_id, "A", {})
    assert tg.next_pending_step(g_id) is None  # B blocked on A
    tg.mark_step_completed(g_id, "A", {})

    step = tg.next_pending_step(g_id)
    assert step["step_id"] == "B"
    tg.mark_step_running(g_id, "B", {})
    assert tg.next_pending_step(g_id) is None  # C blocked on B
    tg.mark_step_completed(g_id, "B", {})

    step = tg.next_pending_step(g_id)
    assert step["step_id"] == "C"
    tg.mark_step_running(g_id, "C", {})
    tg.mark_step_completed(g_id, "C", {})

    assert tg.next_pending_step(g_id) is None
    assert tg.is_graph_complete(g_id)
    teardown()
    print("  ✓ linear chain A → B → C: correct order")


def test_fan_out():
    """A fans out to B, C, D — all three are ready after A completes."""
    setup()
    g_id = tg.create_graph("fan-out", [
        _make_step("A"),
        _make_step("B", depends_on=["A"]),
        _make_step("C", depends_on=["A"]),
        _make_step("D", depends_on=["A"]),
    ])

    # Run A
    assert tg.next_pending_step(g_id)["step_id"] == "A"
    tg.mark_step_running(g_id, "A", {})
    tg.mark_step_completed(g_id, "A", {})

    # All three should now be available (in insertion order)
    ready = set()
    for _ in range(3):
        step = tg.next_pending_step(g_id)
        assert step is not None, "Expected a ready step"
        ready.add(step["step_id"])
        tg.mark_step_running(g_id, step["step_id"], {})
        tg.mark_step_completed(g_id, step["step_id"], {})

    assert ready == {"B", "C", "D"}, f"Fan-out produced {ready}"
    assert tg.is_graph_complete(g_id)
    teardown()
    print("  ✓ fan-out: B, C, D all available after A")


def test_fan_in():
    """B and C must both complete before D runs."""
    setup()
    g_id = tg.create_graph("fan-in", [
        _make_step("B"),
        _make_step("C"),
        _make_step("D", depends_on=["B", "C"]),
    ])

    # Run B
    step = tg.next_pending_step(g_id)
    assert step["step_id"] == "B"
    tg.mark_step_running(g_id, "B", {})
    tg.mark_step_completed(g_id, "B", {})

    # D still blocked — C not done
    step = tg.next_pending_step(g_id)
    assert step["step_id"] == "C", f"Expected C but got {step['step_id']}"
    tg.mark_step_running(g_id, "C", {})

    # D still blocked — C running, not completed
    next_s = tg.next_pending_step(g_id)
    assert next_s is None, f"D should be blocked but got {next_s}"

    tg.mark_step_completed(g_id, "C", {})

    # Now D is unblocked
    step = tg.next_pending_step(g_id)
    assert step is not None and step["step_id"] == "D"
    tg.mark_step_running(g_id, "D", {})
    tg.mark_step_completed(g_id, "D", {})

    assert tg.is_graph_complete(g_id)
    teardown()
    print("  ✓ fan-in: D blocked until both B and C complete")


def test_diamond():
    """A → B, A → C, B+C → D (diamond shape)."""
    setup()
    g_id = tg.create_graph("diamond", [
        _make_step("A"),
        _make_step("B", depends_on=["A"]),
        _make_step("C", depends_on=["A"]),
        _make_step("D", depends_on=["B", "C"]),
    ])

    tg.mark_step_running(g_id, "A", {})
    tg.mark_step_completed(g_id, "A", {})

    # B and C ready, D blocked
    for sid in ["B", "C"]:
        step = tg.next_pending_step(g_id)
        assert step["step_id"] == sid
        tg.mark_step_running(g_id, sid, {})
        tg.mark_step_completed(g_id, sid, {})

    step = tg.next_pending_step(g_id)
    assert step["step_id"] == "D"
    tg.mark_step_running(g_id, "D", {})
    tg.mark_step_completed(g_id, "D", {})

    assert tg.is_graph_complete(g_id)
    teardown()
    print("  ✓ diamond: A → B, C → D correct")


def test_deep_chain(n=50):
    """Linear chain of N steps: each depends on the previous."""
    setup()
    ids   = [f"step_{i:03d}" for i in range(n)]
    steps = [_make_step(ids[0])]
    for i in range(1, n):
        steps.append(_make_step(ids[i], depends_on=[ids[i - 1]]))

    g_id = tg.create_graph(f"deep chain {n}", steps)

    execution_order = []
    for _ in range(n):
        step = tg.next_pending_step(g_id)
        assert step is not None, f"Expected a step, got None at position {len(execution_order)}"
        execution_order.append(step["step_id"])
        tg.mark_step_running(g_id, step["step_id"], {})
        tg.mark_step_completed(g_id, step["step_id"], {})

    assert execution_order == ids, "Execution order violated dependency order"
    assert tg.is_graph_complete(g_id)
    teardown()
    print(f"  ✓ deep chain ({n} steps): correct execution order")


def test_cycle_rejected():
    """A graph with a cycle must be rejected at creation."""
    setup()
    # Direct cycle: A → B → A (B depends on A, but A's depends_on would need to include B
    # which appears after A, so the forward-reference check catches it)
    try:
        tg.create_graph("cycle", [
            _make_step("A", depends_on=["C"]),  # forward ref to C
            _make_step("B", depends_on=["A"]),
            _make_step("C", depends_on=["B"]),
        ])
        assert False, "Cycle should have been rejected"
    except ValueError as e:
        assert "not declared before" in str(e)
    teardown()
    print("  ✓ cycle (forward reference) rejected at create_graph")


def test_self_dependency_rejected():
    """A step that depends on itself must be rejected."""
    setup()
    try:
        tg.create_graph("self dep", [_make_step("A", depends_on=["A"])])
        assert False, "Self-dependency should have been rejected"
    except ValueError:
        pass
    teardown()
    print("  ✓ self-dependency rejected")


def test_unknown_dependency_rejected():
    """A step depending on a non-existent step must be rejected."""
    setup()
    try:
        tg.create_graph("bad dep", [
            _make_step("A"),
            _make_step("B", depends_on=["X"]),  # X never declared
        ])
        assert False, "Unknown dependency should have been rejected"
    except ValueError as e:
        assert "not declared before" in str(e)
    teardown()
    print("  ✓ unknown dependency rejected")


# ═══════════════════════════════════════════════════════════════
# LAYER 3: Crash Recovery Tests
# ═══════════════════════════════════════════════════════════════

def test_crash_during_step1():
    """Crash with step 1 running: after reset, all steps are pending."""
    setup()
    g_id = tg.create_graph("crash-1", [
        _make_step("A"),
        _make_step("B", depends_on=["A"]),
        _make_step("C", depends_on=["B"]),
    ])

    # Simulate crash: A was started but process died
    _force_status(g_id, "A", "running")
    _force_graph_status(g_id, "running")

    # restart — reset_running() called on import
    tg.reset_running()

    assert _raw_status(graph_id=g_id) == "pending"
    assert _raw_status(graph_id_for_step=g_id, step_id="A") == "pending"
    assert _raw_status(graph_id_for_step=g_id, step_id="B") == "pending"
    assert _raw_status(graph_id_for_step=g_id, step_id="C") == "pending"
    teardown()
    print("  ✓ crash during step 1: all steps reset to pending")


def test_crash_during_step3():
    """Crash with steps A, B completed and C running: A, B stay completed, C resets."""
    setup()
    g_id = tg.create_graph("crash-3", [
        _make_step("A"),
        _make_step("B", depends_on=["A"]),
        _make_step("C", depends_on=["B"]),
    ])

    # Execute A and B normally
    tg.mark_step_running(g_id, "A", {})
    tg.mark_step_completed(g_id, "A", {})
    tg.mark_step_running(g_id, "B", {})
    tg.mark_step_completed(g_id, "B", {})

    # Crash during C
    _force_status(g_id, "C", "running")
    _force_graph_status(g_id, "running")

    tg.reset_running()

    assert _raw_status(graph_id_for_step=g_id, step_id="A") == "completed"
    assert _raw_status(graph_id_for_step=g_id, step_id="B") == "completed"
    assert _raw_status(graph_id_for_step=g_id, step_id="C") == "pending"
    assert _raw_status(graph_id=g_id) == "pending"
    teardown()
    print("  ✓ crash during step 3: completed steps preserved, running reset")


def test_crash_idempotent():
    """reset_running() is safe to call multiple times in a row."""
    setup()
    g_id = tg.create_graph("multi-crash", [_make_step("A")])
    _force_status(g_id, "A", "running")
    _force_graph_status(g_id, "running")

    for _ in range(5):
        tg.reset_running()

    assert _raw_status(graph_id_for_step=g_id, step_id="A") == "pending"
    teardown()
    print("  ✓ reset_running() idempotent across multiple calls")


def test_crash_does_not_reset_completed():
    """reset_running() must not touch completed or failed steps."""
    setup()
    g_id = tg.create_graph("completed-crash", [
        _make_step("A"),
        _make_step("B"),
    ])

    tg.mark_step_running(g_id, "A", {})
    tg.mark_step_completed(g_id, "A", {})
    tg.mark_step_running(g_id, "B", {})
    tg.mark_step_failed(g_id, "B", "oops", "agent_error")
    _force_graph_status(g_id, "failed")

    tg.reset_running()  # nothing running at this point

    assert _raw_status(graph_id_for_step=g_id, step_id="A") == "completed"
    assert _raw_status(graph_id_for_step=g_id, step_id="B") == "failed"
    teardown()
    print("  ✓ reset_running() leaves completed/failed steps alone")


# ═══════════════════════════════════════════════════════════════
# LAYER 4: Idempotency Tests
# ═══════════════════════════════════════════════════════════════

def test_next_pending_step_stable_after_complete():
    """next_pending_step on a fully completed graph returns None every time."""
    setup()
    g_id = tg.create_graph("idem-complete", [_make_step("A")])
    tg.mark_step_running(g_id, "A", {})
    tg.mark_step_completed(g_id, "A", {})

    for _ in range(10):
        assert tg.next_pending_step(g_id) is None

    assert tg.is_graph_complete(g_id)
    teardown()
    print("  ✓ next_pending_step returns None consistently on completed graph")


def test_is_graph_complete_stable():
    """is_graph_complete is stable across repeated reads."""
    setup()
    g_id = tg.create_graph("idem-stable", [
        _make_step("A"),
        _make_step("B", depends_on=["A"]),
    ])
    tg.mark_step_running(g_id, "A", {})
    tg.mark_step_completed(g_id, "A", {})

    # B not done — should consistently be not complete
    for _ in range(5):
        assert not tg.is_graph_complete(g_id)

    tg.mark_step_running(g_id, "B", {})
    tg.mark_step_completed(g_id, "B", {})

    for _ in range(5):
        assert tg.is_graph_complete(g_id)
    teardown()
    print("  ✓ is_graph_complete stable before and after completion")


def test_mark_running_twice_raises():
    """Running a step that is already running must raise TransitionError."""
    setup()
    g_id = tg.create_graph("double-run", [_make_step("A")])
    tg.mark_step_running(g_id, "A", {})

    try:
        tg.mark_step_running(g_id, "A", {})  # already running
        assert False, "Should have raised TransitionError"
    except tg.TransitionError:
        pass
    teardown()
    print("  ✓ double mark_step_running raises TransitionError")


def test_complete_twice_raises():
    """Completing an already-completed step must raise TransitionError."""
    setup()
    g_id = tg.create_graph("double-complete", [_make_step("A")])
    tg.mark_step_running(g_id, "A", {})
    tg.mark_step_completed(g_id, "A", {})

    try:
        tg.mark_step_completed(g_id, "A", {})
        assert False, "Should have raised TransitionError"
    except tg.TransitionError:
        pass
    teardown()
    print("  ✓ double mark_step_completed raises TransitionError")


def test_create_graph_validation():
    """Validate all error paths in create_graph."""
    setup()
    # Empty goal
    try:
        tg.create_graph("", [_make_step("A")])
        assert False
    except ValueError:
        pass

    # Empty steps
    try:
        tg.create_graph("goal", [])
        assert False
    except ValueError:
        pass

    # Invalid agent
    try:
        tg.create_graph("goal", [_make_step("A", agent="made_up_agent")])
        assert False
    except ValueError:
        pass

    # Empty prompt
    try:
        tg.create_graph("goal", [{"id": "A", "agent": "python_dev", "prompt": ""}])
        assert False
    except ValueError:
        pass

    # Duplicate step ID
    try:
        tg.create_graph("goal", [_make_step("A"), _make_step("A")])
        assert False
    except ValueError:
        pass

    teardown()
    print("  ✓ create_graph rejects all invalid inputs")


# ═══════════════════════════════════════════════════════════════
# LAYER 5: Adversarial Verification Tests
# ═══════════════════════════════════════════════════════════════

ADVERSARIAL_CASES = [
    # (description, step_prompt, response, expect_pass)
    ("empty string",           "analyze this code",           "",                       False),
    ("whitespace only",        "analyze this code",           "   \n\t  ",              False),
    ("single word",            "analyze this code",           "done",                   False),
    ("7-word response",        "analyze this code",           "This is the analysis done here.", False),
    ("i cannot refusal",       "build the feature",           "I cannot perform this task without more context.", False),
    ("i'm unable refusal",     "implement auth",              "I'm unable to help with this particular request.", False),
    ("i don't know refusal",   "explain async",               "I don't know how to approach this specific topic.", False),
    ("code block missing",     "implement a sort function",   "Sure, here is how to sort a list: first you iterate, then compare.", False),
    ("code block missing 2",   "write code for auth",         "Authentication requires a token check mechanism in your system.", False),
    ("code block present",     "implement a sort function",   "Here is the implementation:\n```python\ndef sort(arr): return sorted(arr)\n```\nThis is efficient.", True),
    ("def present",            "build a function",            "Here you go:\ndef greet(name): return f'Hello {name}' — use it like this.", True),
    ("non-code task passes",   "explain what DNS is",         "DNS is the Domain Name System. It translates domain names to IP addresses. Resolvers query authoritative servers.", True),
    ("normal response",        "summarize this article",      "The article discusses three main points. First, the economic impact of AI. Second, the regulatory challenges. Third, the ethical considerations involved.", True),
]


def test_adversarial_verification():
    """_verify() must catch all adversarial outputs."""
    failures = 0
    for desc, prompt, response, expect_pass in ADVERSARIAL_CASES:
        step = {"step_id": "test", "agent": "python_dev", "prompt": prompt}
        passed, reason = _verify(step, response)
        ok = (passed == expect_pass)
        mark = "✓" if ok else "✗"
        outcome = "PASS" if passed else f"FAIL: {reason}"
        print(f"  {mark} {desc!r:40} → {outcome}")
        if not ok:
            failures += 1

    assert failures == 0, f"{failures} adversarial case(s) not handled correctly"


def test_failure_classifier():
    """_classify_failure maps known patterns to the correct taxonomy."""
    cases = [
        ("empty response",                        "empty_response"),
        ("response too short (3 words)",          "trivial_response"),
        ("response starts with failure phrase",   "refusal"),
        ("prompt requested code but no code block found", "code_missing"),
        ("coordinator returned no content",       "agent_error"),
        ("connection timed out",                  "timeout"),
        ("completely unknown error xyz",          "agent_error"),
    ]
    failures = 0
    for msg, expected in cases:
        got = _classify_failure(msg)
        ok = (got == expected)
        mark = "✓" if ok else "✗"
        print(f"  {mark} {msg!r:50} → {got}")
        if not ok:
            failures += 1
    assert failures == 0, f"{failures} classification(s) wrong"


# ═══════════════════════════════════════════════════════════════
# RANDOM GRAPH GENERATOR + PROPERTY-BASED TESTS
# ═══════════════════════════════════════════════════════════════

def generate_valid_dag(n: int, max_deps: int = 3, seed: int = None) -> list:
    """
    Generate a valid DAG with n nodes.
    Each node may depend on up to max_deps randomly chosen earlier nodes.
    By construction (only backward edges), cycles are impossible.
    """
    rng = random.Random(seed)
    steps = []
    for i in range(n):
        sid  = f"step_{i:04d}"
        deps = []
        if i > 0:
            k = min(i, max_deps)
            n_deps = rng.randint(0, k)
            if n_deps > 0:
                # Sample from strictly earlier steps to guarantee acyclicity
                deps = [f"step_{j:04d}" for j in rng.sample(range(i), n_deps)]
        steps.append({
            "id":         sid,
            "agent":      rng.choice(list(tg.VALID_AGENTS)),
            "prompt":     f"Task for step {i}",
            "depends_on": deps,
        })
    return steps


def _simulate_dag_execution(g_id: int) -> list:
    """
    Execute a graph against the DB (no LLM) by immediately completing each step.
    Returns the list of step IDs in execution order.
    """
    order = []
    while True:
        step = tg.next_pending_step(g_id)
        if not step:
            break
        sid = step["step_id"]
        tg.mark_step_running(g_id, sid, {})
        tg.mark_step_completed(g_id, sid, {})
        order.append(sid)
    return order


def _topological_order(steps: list) -> list:
    """Compute one valid topological order (Kahn's algorithm)."""
    deps   = {s["id"]: set(s["depends_on"]) for s in steps}
    order  = []
    ready  = [s["id"] for s in steps if not deps[s["id"]]]
    while ready:
        node = ready.pop(0)
        order.append(node)
        for s in steps:
            if node in deps[s["id"]]:
                deps[s["id"]].discard(node)
                if not deps[s["id"]]:
                    ready.append(s["id"])
    return order


def test_random_dag_execution(n_graphs=20, max_nodes=15):
    """
    Property-based test: for N random DAGs, verify:
      1. Each step executed exactly once
      2. No step ran before its dependencies were completed
      3. Final graph status is complete
    """
    setup()
    failures = 0
    for trial in range(n_graphs):
        n_nodes = random.randint(3, max_nodes)
        steps   = generate_valid_dag(n_nodes, max_deps=3, seed=trial * 7)
        g_id    = tg.create_graph(f"random-trial-{trial}", steps)

        order       = _simulate_dag_execution(g_id)
        step_ids    = [s["id"] for s in steps]
        dep_map     = {s["id"]: set(s["depends_on"]) for s in steps}
        completed_so_far = set()
        ok = True

        # Every step executed exactly once
        if sorted(order) != sorted(step_ids):
            print(f"  ✗ trial {trial}: not all steps executed — got {len(order)}, expected {n_nodes}")
            ok = False

        # Dependencies satisfied at time of execution
        for sid in order:
            unsatisfied = dep_map[sid] - completed_so_far
            if unsatisfied:
                print(f"  ✗ trial {trial}: step {sid} ran before {unsatisfied}")
                ok = False
            completed_so_far.add(sid)

        if not tg.is_graph_complete(g_id):
            print(f"  ✗ trial {trial}: graph not complete after all steps ran")
            ok = False

        if ok:
            pass  # silent on success to keep output clean
        else:
            failures += 1

    teardown()
    assert failures == 0, f"{failures}/{n_graphs} random DAG trials failed"
    print(f"  ✓ {n_graphs} random DAGs ({max_nodes} nodes max): all passed")


def test_large_dag(n_nodes=100):
    """Generate and fully execute a 100-node DAG — stress test correctness at scale."""
    setup()
    steps = generate_valid_dag(n_nodes, max_deps=4, seed=42)
    g_id  = tg.create_graph(f"large-dag-{n_nodes}", steps)

    t0    = time.time()
    order = _simulate_dag_execution(g_id)
    dur   = time.time() - t0

    assert len(order) == n_nodes, f"Expected {n_nodes} steps, got {len(order)}"
    assert tg.is_graph_complete(g_id)

    # Verify dependency ordering
    dep_map          = {s["id"]: set(s["depends_on"]) for s in steps}
    completed_so_far = set()
    for sid in order:
        assert dep_map[sid].issubset(completed_so_far), \
            f"Step {sid} ran before deps {dep_map[sid] - completed_so_far}"
        completed_so_far.add(sid)

    teardown()
    print(f"  ✓ {n_nodes}-node DAG executed correctly in {dur*1000:.1f}ms")


# ═══════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════

def run_all():
    tests = [
        # Layer 1: State machine
        ("1. Step transition matrix",          test_step_transition_matrix),
        ("1. Graph transition matrix",         test_graph_transition_matrix),
        ("1. Retry reopens failed step",       test_retry_reopens_failed_step),
        ("1. Retry on non-failed returns False", test_retry_on_non_failed_step_returns_false),
        # Layer 2: Dependency graphs
        ("2. Linear chain",                    test_linear_chain),
        ("2. Fan-out",                         test_fan_out),
        ("2. Fan-in",                          test_fan_in),
        ("2. Diamond",                         test_diamond),
        ("2. Deep chain (50 steps)",           test_deep_chain),
        ("2. Cycle rejected",                  test_cycle_rejected),
        ("2. Self-dependency rejected",        test_self_dependency_rejected),
        ("2. Unknown dependency rejected",     test_unknown_dependency_rejected),
        # Layer 3: Crash recovery
        ("3. Crash during step 1",             test_crash_during_step1),
        ("3. Crash during step 3",             test_crash_during_step3),
        ("3. reset_running idempotent",        test_crash_idempotent),
        ("3. Crash leaves completed alone",    test_crash_does_not_reset_completed),
        # Layer 4: Idempotency
        ("4. next_pending stable after complete", test_next_pending_step_stable_after_complete),
        ("4. is_graph_complete stable",        test_is_graph_complete_stable),
        ("4. Double mark_step_running raises", test_mark_running_twice_raises),
        ("4. Double mark_step_completed raises", test_complete_twice_raises),
        ("4. create_graph validation",         test_create_graph_validation),
        # Layer 5: Adversarial verification
        ("5. Adversarial _verify()",           test_adversarial_verification),
        ("5. Failure classifier",              test_failure_classifier),
        # Property-based
        ("P. Random DAG execution (20 graphs)", test_random_dag_execution),
        ("P. Large DAG (100 nodes)",           test_large_dag),
    ]

    passed = failed = 0
    for name, fn in tests:
        print(f"\n[{name}]")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ERROR: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'═'*60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed+failed} tests")
    if failed:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    run_all()
