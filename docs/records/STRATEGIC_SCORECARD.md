# Amagra — Strategic Scorecard

A control surface for the orchestration-layer roadmap, not a vision list. Ten
strategic directions, each with current maturity, the code that already exists,
what's missing, the dependency that gates it, and a measurable "done when".

The thesis this scorecard encodes: **Amagra is becoming less an agent framework
and more a decision system for agents.** The next gains are not more agents,
tools, or bigger models — they are *knowing which strategy is worth using,
knowing when a decision was bad, remembering what worked, and spending
computation where it has the highest expected return.*

**Updated:** 2026-07-21 · **Scale:** 0–100% maturity · **Weighted overall ≈ 50%**

The distribution matters more than the average: the project is strongest exactly
where strategic value is highest (verification, adaptive compute, self-improving
router, decision-quality measurement) and thinnest in the *decision-theoretic*
layer (expected-value engine, strategy memory, counterfactual wiring).

---

## The loop we are building toward

```
        current                          target
   Observe                          Observe
     ↓                                 ↓
   Route                            Predict strategy outcomes
     ↓                                 ↓
   Execute                          Choose strategy (expected value)
     ↓                                 ↓
   Verify                           Execute
                                      ↓
                                    Verify
                                      ↓
                                    Update strategy knowledge
```

The missing layer is not autonomy. It is a **policy layer**.

---

## The central object: Strategy Record

Today route, reflection, memory, tools, model tier, and outcome exist as
separate signals. The unifying abstraction that would let every subsystem speak
the same language:

```python
StrategyRecord(
    task_class = "debugging_python",
    strategy   = ["python_dev", "tool", "verification"],  # the composed path
    cost       = 4200,      # tokens / compute proxy
    latency_ms = 8200,
    success    = True,
    regret     = 0.12,
)
```

Once this exists:
- **Decision Quality** consumes it (scores the decision).
- **Strategy Memory** aggregates it (what works for task_class T).
- **Counterfactual** compares it (chosen vs alternative).
- **EV Engine** predicts with it (P(success)×value − cost − latency).

Building this record type is the highest-leverage single piece of plumbing on
the roadmap — it is the join key for directions 1, 2, 3, and 10.

---

## 1. Decision Intelligence Layer (expected-value strategy selection)

**Status: 🟠 50%**

**Existing**
- **[decision/strategy_selector.py](../../decision/strategy_selector.py) — `StrategySelector`: EV = value·P(success) − latency_penalty − cost_penalty over strategy-memory stats. Beta-shrinkage on P(success) (lucky 1/1 → ~0.67) + abstention (returns None to keep the current router when evidence is thin). `rank`/`select` are the decision-time queries. Demonstrated: python/code ranks python_dev (EV 0.45, 47s) over pipeline+reflect:light (EV 0.20, 104s).**
- Strategy memory supplying the estimates — [decision/strategy_memory.py](../../decision/strategy_memory.py) (#2)
- Confidence + calibration (ECE) — [decision/weights.py](../../decision/weights.py), [calibration_report.py](../../workbench/evaluation/calibration_report.py)
- Regret signal + escalation gate + `model_tier` ladder — [coordinator.py](../../orchestration/coordinator.py)

**Missing**
- The **router calling `select()`** at decision time (engine built; not wired into routing)
- **Calibration** of the heuristic weights/budgets (LATENCY_WEIGHT, budgets, prior)
- **Validation** that it beats the baseline on held-out tasks — needs ≥min_attempts of data per class, which today's sparse runs don't have (selector correctly abstains everywhere so far)

**Depends on:** ✅ Strategy Memory (#2) · exploration data to reach min_attempts per class

**Done when:** the router selects a strategy using predicted utility and beats the current signal/rule baseline on a held-out task set.

---

## 2. Strategy Memory ("what worked before")

**Status: 🟢 60%**

**Existing**
- **[decision/strategy_memory.py](../../decision/strategy_memory.py) — `StrategyRecord` + `StrategyMemory`: task_class → strategy → {attempts, success_rate, avg_cost, avg_latency}, ranked cheapest-successful-first. `ingest_run_log()` (idempotent) backfills from the run log; `stats_for`/`best_for` query it. Demonstrated end-to-end (real ingest shows e.g. python/code: python_dev 47s vs pipeline+reflect:light 104s — a 2× cost gap for the same class).**
- Episodic memory records outcome (performance, regret, action, complexity) — [memory_core/db.py](../../memory_core/db.py)
- Decision records with provenance (explicit vs derived) — [decision/model_choices.py](../../decision/model_choices.py)

**Missing**
- The router calling `best_for(task_class)` **at decision time** (query exists; not yet wired into routing)
- Multiple strategies per class from real traffic — natural runs pick one strategy each, so `best_for` is only meaningful once exploration (forced or reflection-ROI-driven) populates alternatives

**Depends on:** ✅ Strategy Record (done) · exploration data (reflection ROI / forced A/B) to fill alternatives

**Done when:** the router reads ranked strategies for a task class before deciding and it beats the current baseline on held-out tasks.

**Note:** built as an aggregation/query layer over the run log — not a new subsystem, as scoped. `best_for` is the query the EV engine (#1) consumes.

---

## 3. Counterfactual Evaluation Engine ⭐

**Status: 🟠 40%**

**Existing**
- [cognition/counterfactual.py](../../cognition/counterfactual.py) — `simulate_alternative`, `compare_agents` (mechanical A/B)
- Regret computed and stored; [cognition/failure_miner.py](../../cognition/failure_miner.py)

**Missing**
- Statistical validity (self-described as needing 400+ sessions)
- **Wiring**: counterfactual output currently flows nowhere — it must feed Strategy Memory so failed decisions become training data

**Depends on:** Strategy Memory (#2) as the sink · Strategy Record

**Done when:** each chosen decision produces an estimated regret vs alternatives that is written to strategy memory and measurably improves routing on held-out tasks.

---

## 4. Self-Improving Router

**Status: 🟢 65%**

**Existing**
- [orchestration/learned_router.py](../../orchestration/learned_router.py) — LogisticRegression on trace features, auto-retrains, runs alongside signal routing, wins on strong disagreement
- `routing_accuracy` measured; [workbench/evaluation/semantic_route_eval.py](../../workbench/evaluation/semantic_route_eval.py)

**Missing**
- Online closed-loop update (currently batch retrain on trace JSONL)
- Regret-driven policy adjustment (vs pure supervised retrain)

**Depends on:** Counterfactual (#3) for regret signal (to move from supervised → policy improvement)

**Done when:** router policy updates from observed regret without a manual retrain trigger, and drift ("class X over-routed to Y") self-corrects.

---

## 5. Multi-Agent Specialization (measured strengths)

**Status: 🟡 40%**

**Existing**
- 7 domain agents — [agents/](../../agents/)
- Per-agent evaluation — [workbench/evaluation/specialization_eval.py](../../workbench/evaluation/specialization_eval.py); skill graph; deep pipeline for compound queries — [cognition/deep_pipeline.py](../../cognition/deep_pipeline.py)

**Missing**
- Role pipeline (research → plan → execute → verify) vs today's capability-destination agents
- Per-agent capability scorecard (GSM8K/HumanEval/citation-accuracy) that **drives routing**

**Depends on:** Strategy Record (to attribute outcomes to agent roles)

**Done when:** each agent carries a measured strength profile and routing cites it as evidence.

---

## 6. Verification as a First-Class System

**Status: 🟢 70%**

**Existing**
- [cognition/step_verifier.py](../../cognition/step_verifier.py), critic gate (regenerates on low score) — coordinator
- [cognition/dual_trajectory.py](../../cognition/dual_trajectory.py) (A/B + critic), [cognition/self_consistency.py](../../cognition/self_consistency.py), contradiction check
- Code execution/testing — [tools/sandbox.py](../../tools/sandbox.py)

**Missing**
- A unified generate→verify→measure-confidence→repair controller (the pieces exist but aren't one orchestrated subsystem)

**Depends on:** nothing hard — mostly consolidation

**Done when:** verification type + repair are selected by policy per task, and verification outcomes feed Strategy Record.

---

## 7. Adaptive Compute Budget ⭐

**Status: 🟢 65%**

**Existing**
- `model_tier` (fast/standard/reasoning) and `reflect_level` (none/light/full)
- Vote-margin **escalation gate** (~30% of volume captures ~90% of errors) — coordinator; [workbench/evaluation/escalation_gate_eval.py](../../workbench/evaluation/escalation_gate_eval.py)

**Missing**
- Formal accuracy-per-token accounting steering the ladder (heading there via capability ROI)

**Depends on:** capability ROI from Decision Quality (#10)

**Done when:** compute tier is chosen to maximize accuracy-per-token on held-out tasks, with unnecessary-computation rate tracked.

---

## 8. Agent Simulation / Sandbox

**Status: 🟡 30%**

**Existing**
- Real resource-limited code execution — [tools/sandbox.py](../../tools/sandbox.py)

**Missing**
- Plan → simulate → estimate-failure → execute for **actions/workflows** (sandbox today is for code snippets, not action simulation)

**Depends on:** verification (#6), strategy memory (#2) for failure estimates

**Done when:** risky actions are dry-run/simulated with a failure estimate before execution.

---

## 9. Personal Knowledge OS

**Status: 🟡 40%**

**Existing**
- User profile personalizes prompts — [core/user_profile.py](../../core/user_profile.py)
- Multi-type memory (document/reflection/episodic/decision), quality×relevance×freshness ranking, FAISS backend

**Missing**
- Structured, evolving projects / lessons / workflows layer

**Depends on:** Strategy Memory (#2) as the machine-facing analogue

**Done when:** memory surfaces "last time we solved X we did Y" for projects/workflows, not just semantic recall.

---

## 10. Decision Quality Benchmark ⭐

**Status: 🟢 70%**  ·  *Eval Layer v0.1 shipped (commit `54eeb33`)*

**Existing**
- 7-dimension decision scorer — [workbench/evaluation/decision_quality.py](../../workbench/evaluation/decision_quality.py)
- Live evidence pipeline (run-log observations; `AgentState` schema fix)
- Controlled reflection on/off A/B (capability ROI) — [workbench/evaluation/reflection_delta.py](../../workbench/evaluation/reflection_delta.py)
- Decision regret ✅ · routing calibration/ECE ✅ · capability ROI ✅

**Missing**
- Strategy-success **prediction** metric
- Systematic unnecessary-computation rate
- A **hard/failing** prompt set (current reflection verdict is ceiling-bound: OFF already 8/8)

**Depends on:** hard reflection stress set (populates real ROI, not ceiling data)

**Done when:** the benchmark reports capability ROI per task class on a set that includes cases the base model fails, and the numbers are stable enough to gate routing decisions.

---

## Priority path (dependency-ordered)

The order is forced by dependencies, not preference — each item produces the
input the next one consumes.

### Now
1. ✅ This scorecard (control surface)
2. **Reflection stress dataset** — a prompt set with cases reflection *can* rescue (self-contradiction, multi-step reasoning, false premise, revision, knowledge uncertainty). Purpose: generate strategy-performance data, not just re-answer "does reflection work". Feeds #2 and #10.
3. **Strategy Record + narrow Strategy Memory (#2)** — task_class → strategy → {success, cost, latency}. The join key for everything downstream.

### Next
4. **Wire Counterfactual → Strategy Memory (#3)** — failed decisions become training data.
5. **Expected-Value strategy selector (#1)** — only meaningful once #2/#3 supply real historical estimates; without them EV is a guess.

### Later
6. External agent benchmarks (GAIA/τ-bench, as delta vs bare model)
7. More autonomous / sandboxed execution (#8)
8. Personal Knowledge OS expansion (#9)

---

## Maturity summary

| # | Direction | Maturity |
|---|-----------|:--------:|
| 6 | Verification first-class | 🟢 70% |
| 10 | Decision Quality benchmark | 🟢 70% |
| 4 | Self-improving router | 🟢 65% |
| 7 | Adaptive compute budget | 🟢 65% |
| 3 | Counterfactual engine | 🟠 40% |
| 5 | Multi-agent specialization | 🟡 40% |
| 9 | Personal Knowledge OS | 🟡 40% |
| 2 | Strategy memory | 🟡 35% |
| 1 | Decision intelligence layer | 🟡 30% |
| 8 | Agent simulation / sandbox | 🟡 30% |

Related: [SCORECARD.md](SCORECARD.md) (capability scorecard) · [METRICS_ROADMAP.md](METRICS_ROADMAP.md)
