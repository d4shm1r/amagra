# Contributing to Amagra

Thanks for your interest in Amagra — the AI you can trust with long-term work. Issues and pull requests are welcome.

This guide covers local setup, the project's conventions, and how to add the most common contribution: a new specialist agent.

---

## Local setup

**With Docker (recommended):**

```bash
git clone https://github.com/d4shm1r/amagra && cd amagra
docker compose up
docker exec agentic-ollama ollama pull nomic-embed-text
docker exec agentic-ollama ollama pull phi4-mini
```

**Without Docker:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull nomic-embed-text && ollama pull phi4-mini
uvicorn api:app --host 0.0.0.0 --port 8000 &
cd ui && npm install && npm run dev
```

- API: http://localhost:8000 · docs at `/docs`
- UI: http://localhost:3000

You can reproduce the routing benchmark without Ollama:

```bash
PYTHONPATH=. python3 evaluation/ablation_eval.py
```

---

## Before you open a PR

The CI workflow runs **ruff**, **pytest**, and a **Docker build** on every push and PR. Run the first two locally so you don't round-trip on CI:

```bash
ruff check .
PYTHONPATH=. python3 -m pytest tests/ -q   # or: make test [PYTHON=path/to/your/venv/python]
```

- **Lint:** `ruff` is the source of truth (`ruff.toml`). `ruff check . --fix` autofixes most issues.
- **Tests:** the suite is currently **986 passing**. New behavior needs a test; bug fixes should add a regression test.
- **Match the surrounding code** — naming, comment density, and idiom. Don't reformat unrelated lines.

---

## Workflow

1. Branch off `main` (e.g. `feature/...`, `fix/...`, `docs/...`). Don't commit to `main` directly.
2. Keep each commit focused; write a clear message body explaining the *why*.
3. Open a PR against `main`. Fill in what changed and how you tested it.
4. Green CI (ruff + pytest + Docker) is required before merge.

---

## Adding a new agent

An agent is **data, not a pipeline**. You declare what makes it different; the shared
runner ([`agents/runner.py`](agents/runner.py)) does the rest — profile, memory recall,
probes, history trimming, the model call, and saving the answer. Adding one touches
**exactly two files**:

1. **`agents/<name>.py`** — a prompt, any tools it needs, and an `AgentSpec`. Use
   [`agents/python_dev.py`](agents/python_dev.py) as the reference:

   ```python
   SPEC = AgentSpec(
       name="python_dev",
       prompt=PYTHON_SYSTEM_PROMPT,      # may contain a {user_profile} slot
       memory_kind="code",               # how its memories are tagged
       probes=(                          # self-checks it runs when the task asks
           Probe(triggers=("environment", "packages", "installed", "version"),
                 label="PYTHON ENVIRONMENT",
                 run=lambda _task: check_python_env()),
       ),
   )
   python_agent = Agent(SPEC)
   ```

2. **`agents/registry.py`** — register it so routing, telemetry, and observability pick
   it up automatically. A boot assertion in the coordinator fails loudly if the two
   disagree.

Do **not** write your own message-building or memory code. If your agent genuinely needs
to opt out of part of the pipeline, that is a flag on the spec (`remembers`,
`uses_profile`, `uses_tools`, `max_messages`) or an `after` hook — see
[`agents/terse.py`](agents/terse.py) and [`agents/knowledge_learning.py`](agents/knowledge_learning.py),
the only two that are not uniform. Ten hand-written copies of the pipeline is exactly how
`knowledge_learning` came to ship a literal `{user_profile}` to the model for months.

Then add the agent's domain keywords to the signal router so `QuerySignal` can route to
it, and a couple of representative queries to the evaluation set
(`workbench/evaluation/`) so routing accuracy stays measured.

A registered agent automatically participates in routing, the skill graph, FAISS memory
retrieval, the critic gate, and the step verifier — you don't wire those up by hand.

---

## Reporting bugs & requesting features

- **Bugs:** open an issue with steps to reproduce, expected vs. actual behavior, and your environment (Docker vs. local, GPU/CPU, model).
- **Security issues:** please follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
- **Features:** check [docs/ROADMAP.md](docs/ROADMAP.md) first — many ideas are already planned and tracked there.

By contributing, you agree that your contributions are licensed under the project's [MIT License](LICENSE).
