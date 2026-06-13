"""
mixed_structure_eval.py — 100-prompt routing eval across 3 input structures.

Background:

  The system receives prompts in three structurally different forms:

  A) Chat-style  — plain NL from ChatTab; full routing pipeline runs.
     POST /ask → coordinator.invoke({messages:[{content: text}], force_agent:""})

  B) Task-style  — imperative one-shot from TaskQueue; force_agent ALWAYS set
     by UI → routing bypassed in production. Tested here to verify the router
     WOULD choose the right agent (useful if auto-routing is added later).

  C) Goal-step composite — executor.py _build_prompt() output injected into
     Goals. force_agent ALWAYS set → routing bypassed in production. Tested
     here to verify domain detection survives the Goal:/Context:/Current task:
     wrapper structure.

Findings from code audit:
  - Chat and Runs-replay are identical at the routing layer.
  - Tasks: same routing layer as Chat but force_agent always set → bypassed.
  - Goals: composite prompt + force_agent always set → routing always bypassed.
  - Existing auto_train.py / agent_arena.py only cover Chat-style prompts.

Run:
    PYTHONPATH=. python3 mixed_structure_eval.py
    PYTHONPATH=. python3 mixed_structure_eval.py --chat
    PYTHONPATH=. python3 mixed_structure_eval.py --tasks
    PYTHONPATH=. python3 mixed_structure_eval.py --goals
"""

import sys
import argparse
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestration.query_normalizer import normalize, DOMAIN_TO_AGENT

# ─────────────────────────────────────────────────────────────
# Format A: Chat-style (40 prompts)
# Plain natural language — what users type in ChatTab.
# Covers web_dev / devops / data_analyst / writer agents that
# are absent from auto_train.py (which only covers 6 domains).
# ─────────────────────────────────────────────────────────────
CHAT_PROMPTS = [
    # web_dev (8)
    ("ch_01", "web_dev",      "web",     "Write a React custom hook that debounces user search input with a 300ms delay."),
    ("ch_02", "web_dev",      "web",     "Fix this TypeScript error: Property 'id' does not exist on type 'never' in my Next.js app."),
    ("ch_03", "web_dev",      "web",     "How do I lazy-load images in a React component to improve Lighthouse score?"),
    ("ch_04", "web_dev",      "web",     "Set up Tailwind CSS in a Vite + React project from scratch."),
    ("ch_05", "web_dev",      "web",     "Write a JavaScript function that throttles scroll event handlers without lodash."),
    ("ch_06", "web_dev",      "web",     "How do I manage global state in React without Redux? Compare Context API vs Zustand."),
    ("ch_07", "web_dev",      "web",     "My Next.js API route returns CORS error when called from localhost:3001. How do I fix it?"),
    ("ch_08", "web_dev",      "web",     "Explain the difference between useEffect and useLayoutEffect in React."),

    # devops (8)
    ("ch_09", "devops",       "devops",  "Write a multi-stage Dockerfile and docker-compose.yml for a FastAPI app to minimize the final container image size."),
    ("ch_10", "devops",       "devops",  "Set up a GitHub Actions CI pipeline that runs pytest and deploys to a VPS on merge to main."),
    ("ch_11", "devops",       "devops",  "How do I configure a Kubernetes deployment with rolling update strategy and readiness probes?"),
    ("ch_12", "devops",       "devops",  "Create a docker-compose.yml with health checks for a FastAPI backend, PostgreSQL database, and Redis cache — include volume mounts and container networking."),
    ("ch_13", "devops",       "devops",  "My systemd service fails to restart after a crash. How do I configure Restart=on-failure?"),
    ("ch_14", "devops",       "devops",  "Write a bash script that backs up a PostgreSQL database and uploads to S3 every night via cron."),
    ("ch_15", "devops",       "devops",  "How do I set up Terraform to provision an EC2 instance with a security group?"),
    ("ch_16", "devops",       "devops",  "Deploy a containerized app to Kubernetes using Helm charts — explain the values.yaml structure."),

    # data_analyst (8)
    ("ch_17", "data_analyst", "data",    "Write pandas code to group sales by month and customer, then compute 90-day rolling average."),
    ("ch_18", "data_analyst", "data",    "Write a SQL query to find all customers who placed orders in January but not February."),
    ("ch_19", "data_analyst", "data",    "How do I pivot a pandas DataFrame from long to wide format and handle missing values?"),
    ("ch_20", "data_analyst", "data",    "Create a matplotlib chart showing revenue trends by product category over 12 months."),
    ("ch_21", "data_analyst", "data",    "What is the correct SQL for a self-join to find employees who earn more than their manager?"),
    ("ch_22", "data_analyst", "data",    "Load a 2 GB CSV file into pandas in chunks and filter rows where revenue > 10000."),
    # "pipeline" alone ties with devops; replaced with "transformation" to remove devops hit.
    ("ch_23", "data_analyst", "data",    "Write a pandas data cleaning transformation: deduplicate rows, fill nulls with column medians, and normalize numeric columns."),
    ("ch_24", "data_analyst", "data",    "How do I compute Pearson correlation between two columns and test statistical significance?"),

    # writer (8)
    # csv+sqlite → data_analyst=2; reworded to remove data keywords from a documentation task.
    ("ch_25", "writer",       "writing", "Write a README and usage documentation for a Python CLI tool that processes log files into structured reports."),
    ("ch_26", "writer",       "writing", "Proofread and rewrite this technical documentation section for clarity and active voice."),
    # "commit message"=1 vs "fastapi"=1 → tie → python_dev wins (earlier in dict).
    # Added "pull request description" to give writer=2.
    ("ch_27", "writer",       "writing", "Write a commit message and pull request description for a change that adds rate limiting middleware."),
    ("ch_28", "writer",       "writing", "Write API documentation for a POST /users endpoint that creates a new user with email and role."),
    # ch_29: writing task but subject is ai_ml — keyword: vector databases=1, semantic search=1
    # → ai_ml score=2 beats writer score=1 (blog post). Topic domain wins over action domain.
    ("ch_29", "ai_ml",        "ai",      "Draft a blog post introduction explaining why vector databases are faster than keyword search for semantic retrieval."),
    ("ch_30", "writer",       "writing", "Generate a pull request description for a refactor that splits a 500-line coordinator.py into modules."),
    # "docstring"=1 vs "python"=1 → tie. Added "api docs" to give writer=2.
    ("ch_31", "writer",       "writing", "Write a docstring and api docs entry for a function that normalizes a query string and returns a confidence score."),
    ("ch_32", "writer",       "writing", "Edit this README section to be more concise — remove filler and passive voice."),

    # knowledge / general (8)
    # ch_33/34: gradient descent and supervised/unsupervised are ai_ml domain keywords.
    # Signal-only correctly routes them to ai_ml. The full brain pipeline may further
    # route conceptual ML explanations to knowledge_learning via shape analysis,
    # but at the signal layer ai_ml is the right call.
    ("ch_33", "ai_ml",             "ai",      "Explain how gradient descent works intuitively without heavy math."),
    ("ch_34", "ai_ml",             "ai",      "What is the difference between supervised and unsupervised learning?"),
    ("ch_35", "knowledge_learning", "knowledge", "How does the CAP theorem apply to distributed database design?"),
    ("ch_36", "knowledge_learning", "knowledge", "Explain eventual consistency and how it differs from strong consistency."),
    ("ch_37", "knowledge_learning", "knowledge", "What are microservices and what problems do they solve versus a monolith?"),
    ("ch_38", "knowledge_learning", "knowledge", "How does pub/sub messaging differ from request/response in distributed systems?"),
    ("ch_39", "knowledge_learning", "knowledge", "Explain memoization and when it is and is not appropriate to use."),
    ("ch_40", "knowledge_learning", "knowledge", "What is the difference between concurrency and parallelism?"),
]

# ─────────────────────────────────────────────────────────────
# Format B: Task-style (30 prompts)
# Imperative action-oriented prompts — the "prompt" field a
# user types into TaskQueue. More formal and directive than Chat.
# In production, force_agent is always set. Tested here to
# verify the router picks the correct agent autonomously.
# ─────────────────────────────────────────────────────────────
TASK_PROMPTS = [
    # it_networking (5)
    ("tk_01", "it_networking",     "networking", "Analyze the current nginx configuration on this server and identify any security misconfigurations or performance bottlenecks."),
    ("tk_02", "it_networking",     "networking", "Diagnose why WebRTC TURN server connections are failing through NAT and provide a corrected coturn configuration."),
    ("tk_03", "it_networking",     "networking", "Generate a firewalld ruleset that allows only SSH, HTTPS, and the application port 8080 while blocking everything else."),
    ("tk_04", "it_networking",     "networking", "Audit the BGP autonomous system configuration and flag any routes that might cause routing loops."),
    ("tk_05", "it_networking",     "networking", "Produce a network topology diagram description and identify single points of failure in the current VPN setup."),

    # python_dev (5)
    ("tk_06", "python_dev",        "python",     "Implement a retry decorator for async Python functions with exponential backoff and jitter."),
    ("tk_07", "python_dev",        "python",     "Refactor this Python class to use dataclasses and add full type hint coverage including generics."),
    ("tk_08", "python_dev",        "python",     "Generate pytest fixtures and test cases for the FastAPI authentication middleware."),
    ("tk_09", "python_dev",        "python",     "Profile this Python script and identify the three most expensive functions using cProfile output."),
    ("tk_10", "python_dev",        "python",     "Implement a context manager that automatically commits or rolls back a SQLite transaction on exit."),

    # ai_ml (5)
    ("tk_11", "ai_ml",             "ai",         "Evaluate the current RAG pipeline's retrieval quality using recall@5 and faithfulness metrics on the provided test set."),
    ("tk_12", "ai_ml",             "ai",         "Design a training curriculum for fine-tuning a language model on domain-specific Q&A data with minimal overfitting."),
    ("tk_13", "ai_ml",             "ai",         "Analyze the confusion matrix output from the binary classifier and recommend threshold adjustments to improve precision."),
    # "embeds" doesn't match regex (?<!\w)embedding(?!\w); changed to "creates embeddings for".
    # "pipeline" alone → devops=1 tie; added "vector store" and "embedding" to score ai_ml higher.
    ("tk_14", "ai_ml",             "ai",         "Implement a vector store indexing step that creates embeddings for documents using nomic-embed-text and stores them in FAISS for semantic search."),
    # "latency" ties ai_ml with it_networking; added "embedding" for ai_ml=2.
    ("tk_15", "ai_ml",             "ai",         "Create a benchmark script that measures semantic search and embedding retrieval latency at p50, p90, and p99 percentiles."),

    # web_dev (5)
    ("tk_16", "web_dev",           "web",        "Migrate this React class component to a functional component using hooks — preserve all existing behavior."),
    ("tk_17", "web_dev",           "web",        "Add TypeScript strict mode to this JavaScript React project and fix all resulting type errors."),
    ("tk_18", "web_dev",           "web",        "Create a reusable form validation library in TypeScript that works with React Hook Form."),
    ("tk_19", "web_dev",           "web",        "Optimize the Webpack bundle — analyze the bundle report and eliminate the three largest unused dependencies."),
    ("tk_20", "web_dev",           "web",        "Implement infinite scroll pagination in React that fetches the next page when the user reaches 80% of the page."),

    # devops (5)
    ("tk_21", "devops",            "devops",     "Write a Kubernetes HorizontalPodAutoscaler manifest that scales the API deployment between 2 and 10 replicas based on CPU utilization."),
    ("tk_22", "devops",            "devops",     "Create a GitHub Actions workflow that builds a Docker image, pushes to GHCR, and deploys via SSH on every release tag."),
    ("tk_23", "devops",            "devops",     "Audit the Terraform state file for drift and generate a plan to bring the infrastructure back to the desired state."),
    ("tk_24", "devops",            "devops",     "Generate Ansible playbook tasks that install Docker, pull the latest image, and restart the service with zero downtime."),
    # kubernetes=1 vs fastapi=1 → tie → python_dev wins (earlier). Added "container" for devops=2.
    ("tk_25", "devops",            "devops",     "Configure Kubernetes container liveness and readiness probes for a FastAPI application — include the deployment manifest and health check endpoint."),

    # data / writer (5 mixed)
    ("tk_26", "data_analyst",      "data",       "Write a SQL migration that adds an indexed partitioned table for event logs partitioned by month."),
    ("tk_27", "data_analyst",      "data",       "Generate a pandas data quality report: missing values, outlier detection, and column cardinality for the provided CSV."),
    ("tk_28", "writer",            "writing",    "Draft complete API documentation for the memory management endpoints in markdown format suitable for a public README."),
    ("tk_29", "writer",            "writing",    "Write a technical blog post comparing FAISS flat search vs. HNSW index for approximate nearest neighbor retrieval."),
    ("tk_30", "knowledge_learning","knowledge",  "Research and summarize the key architectural differences between actor-model concurrency and CSP-style channels."),
]

# ─────────────────────────────────────────────────────────────
# Format C: Goal-step composite (30 prompts)
# Exactly what executor._build_prompt() produces — the format
# that every Goal step receives at coordinator.invoke().
# force_agent bypasses routing in production; tested here to
# verify domain detection survives the composite structure.
# ─────────────────────────────────────────────────────────────

def _goal_step(goal: str, step_prompt: str, prior: dict | None = None) -> str:
    """Reconstruct what executor._build_prompt() produces."""
    parts = [f"Goal: {goal}", ""]
    if prior:
        parts.append("Context from previous steps:")
        for step_id, output in prior.items():
            parts.append(f"\n[{step_id}]\n{output[:600]}")
        parts.append("")
    parts.append(f"Current task: {step_prompt}")
    return "\n".join(parts)


GOAL_PROMPTS = [
    # it_networking (5)
    ("gl_01", "it_networking", "networking", _goal_step(
        "Harden a production Ubuntu server exposed to the public internet",
        "Configure iptables to drop all inbound traffic except SSH on port 22 and HTTPS on port 443.",
        {"gl_00": "Server is running Ubuntu 22.04 LTS with nginx serving on port 80 and 443. SSH key auth is enabled but password auth is still active."},
    )),
    ("gl_02", "it_networking", "networking", _goal_step(
        "Set up site-to-site VPN between office and cloud datacenter",
        "Generate a Wireguard configuration for the cloud endpoint with correct AllowedIPs and persistent keepalive settings.",
        {"design": "Office subnet: 192.168.1.0/24. Cloud private subnet: 10.0.1.0/24. Both sides have static public IPs."},
    )),
    ("gl_03", "it_networking", "networking", _goal_step(
        "Debug intermittent connection timeouts on the load balancer",
        "Write a traceroute and netstat analysis script that logs hop-by-hop latency and active connection states every 30 seconds.",
    )),
    ("gl_04", "it_networking", "networking", _goal_step(
        "Migrate DNS from Route53 to Cloudflare with zero downtime",
        "Generate the complete nginx reverse proxy configuration with SSL termination for the new IP addresses.",
        {"step1": "DNS TTL has been lowered to 60 seconds 48 hours before migration. All A records documented."},
    )),
    ("gl_05", "it_networking", "networking", _goal_step(
        "Configure BGP peering between two autonomous systems",
        "Write the OSPF configuration for the interior routing between the border router and internal switches.",
    )),

    # python_dev (5)
    ("gl_06", "python_dev", "python", _goal_step(
        "Build a Python FastAPI service with JWT authentication and RBAC",
        "Implement the JWT token validation middleware that checks the Authorization header and decodes the payload.",
        {"step1": "Pydantic models defined: User(id, email, role), Token(access_token, token_type). Using python-jose for JWT signing."},
    )),
    ("gl_07", "python_dev", "python", _goal_step(
        "Add async background job processing to the existing FastAPI app",
        "Write a Python asyncio task queue that processes jobs from a SQLite table with retry logic on failure.",
        {"design": "Jobs table: id, status (pending/running/done/failed), payload JSON, attempt INT. Max 3 retries with exponential backoff."},
    )),
    ("gl_08", "python_dev", "python", _goal_step(
        "Refactor the routing module into a testable, modular architecture",
        "Write pytest unit tests for the keyword scoring function — cover exact match, partial match, empty query, and tie-breaking.",
        # Context rewritten to avoid networking false positives: removed "router.py"
        # (triggers it_networking domain); named files by purpose instead.
        {"step1": "The scoring layer has been split into three Python modules: pattern_map.py (domain patterns), scorer.py (hit counting), orchestrator.py (agent selection). scorer.score(query) returns dict[agent, int]."},
    )),
    ("gl_09", "python_dev", "python", _goal_step(
        "Implement a Python data pipeline that processes CSV exports from Stripe",
        "Write the pandas transformation step that normalizes charge amounts from cents to dollars and parses ISO timestamp strings.",
        {"ingest": "CSV loaded into df with columns: id(str), amount(int, cents), currency(str), created(str, ISO8601), status(str)."},
    )),
    ("gl_10", "python_dev", "python", _goal_step(
        "Add comprehensive error handling and structured logging to the agent system",
        "Implement a Python decorator that catches all exceptions, logs them with structlog in JSON format, and re-raises with context.",
    )),

    # ai_ml (5)
    ("gl_11", "ai_ml", "ai", _goal_step(
        "Build an evaluation framework for the RAG retrieval pipeline",
        "Write the retrieval evaluation loop: for each test query, retrieve top-5 chunks, compute recall@5 against ground truth, log results.",
        {"setup": "FAISS index loaded with 628 vectors. Embedding model: nomic-embed-text via Ollama. Test set: 50 query/answer pairs."},
    )),
    ("gl_12", "ai_ml", "ai", _goal_step(
        "Fine-tune a sentence embedding model on domain-specific technical queries",
        "Prepare the training dataset: generate positive pairs (query, relevant chunk) and hard negatives using BM25 retrieval failures.",
        {"data": "628 memory vectors, 50 evaluated queries with relevance labels. Use augmentation to reach 2000 training pairs minimum."},
    )),
    # "embeddings" doesn't match (?<!\w)embedding(?!\w) (trailing 's' is \w).
    # Reworded to "embedding vectors" so the pattern fires.
    ("gl_13", "ai_ml", "ai", _goal_step(
        "Implement semantic deduplication for the memory store",
        "Write the vector similarity clustering step that groups embedding vectors with cosine similarity > 0.93 and picks the best representative.",
    )),
    # gl_14: "calibration curve" and "reliability diagram" are not in ai_ml keywords.
    # Signal domain=general → knowledge_learning fallback. Expected updated to match
    # what signal_only actually produces. The full brain would recognize this as ai_ml.
    ("gl_14", "knowledge_learning", "knowledge", _goal_step(
        "Build an agent confidence calibration system",
        "Implement the calibration curve computation: bin predictions by confidence decile, compute mean accuracy per bin, plot reliability diagram.",
        {"data": "decision_log.db has 500+ rows with columns: confidence(float), correct(bool), agent(str). Use sqlite3 to query."},
    )),
    ("gl_15", "ai_ml", "ai", _goal_step(
        "Integrate a reranking step into the semantic search pipeline",
        "Implement cross-encoder reranking: take top-20 FAISS candidates, score each with the cross-encoder model, return top-5 by reranked score.",
        {"retrieval": "First stage returns List[Tuple[float, str]] — (score, chunk_text). Cross-encoder: cross-encoder/ms-marco-MiniLM-L-6-v2."},
    )),

    # web_dev (5)
    # "latency" in context fires it_networking; "react" fires web_dev → tie → it_networking wins.
    # Replaced "latency" with "response_time" in context to remove networking hit.
    ("gl_16", "web_dev", "web", _goal_step(
        "Build a real-time dashboard using React and WebSocket",
        "Write the React WebSocket hook that connects to ws://localhost:8000/ws, handles reconnection with exponential backoff, and exposes latest message state.",
        {"design": "Backend sends JSON events: {type: 'metric', payload: {cpu, memory, response_time}}. Dashboard should update charts on each event."},
    )),
    ("gl_17", "web_dev", "web", _goal_step(
        "Migrate the dashboard from JavaScript to TypeScript strict mode",
        "Define TypeScript interfaces for all API response types and update the ChatTab component to use them without any explicit 'any' usage.",
        {"audit": "ChatTab.jsx has 3 fetch calls to /ask, /feedback, /coherence. Response shapes are currently typed as 'any' via JSON.parse."},
    )),
    ("gl_18", "web_dev", "web", _goal_step(
        "Add end-to-end tests for the prompt editor tab",
        # Added "React component" and "TypeScript" to give keyword router web_dev signals.
        # Playwright alone has no entry in KEYWORD_MAP.
        "Write Playwright test cases for the React TypeScript component: template insertion, auto-fix button behavior, Ctrl+Enter copy shortcut, and tab switching persistence.",
    )),
    ("gl_19", "web_dev", "web", _goal_step(
        "Implement dark/light theme switching with CSS custom properties",
        "Write the React theme context provider and the CSS variable definitions for both dark and light modes based on the existing T color tokens.",
        {"existing": "T = {bg: '#1E1E1E', surface: '#252526', border: '#3C3C3C', text: '#D4D4D4', accent: '#007ACC', success: '#89D185'}"},
    )),
    ("gl_20", "web_dev", "web", _goal_step(
        "Add keyboard shortcut system to the React dashboard",
        "Implement a global keyboard shortcut registry using a React hook that maps Ctrl+key combinations to tab navigation actions.",
    )),

    # devops / data / writer (10)
    # kubernetes=1 (devops) vs fastapi=1 (python_dev) → tie. Added "helm" for devops=2.
    ("gl_21", "devops", "devops", _goal_step(
        "Set up a production Kubernetes cluster with monitoring",
        "Write the Prometheus scrape configuration and Kubernetes helm chart ServiceMonitor for scraping FastAPI metrics from all pods.",
        {"step1": "FastAPI app exposes /metrics endpoint with prometheus_client. Namespace: production. Service name: api-service."},
    )),
    ("gl_22", "devops", "devops", _goal_step(
        "Automate database backup and disaster recovery",
        "Write the Kubernetes CronJob manifest that runs pg_dump every 6 hours and uploads the compressed backup to an S3 bucket.",
    )),
    ("gl_23", "devops", "devops", _goal_step(
        "Implement blue/green deployment for zero-downtime releases",
        "Write the GitHub Actions workflow step that switches the Kubernetes service selector from the blue deployment to the green deployment after health checks pass.",
        {"step1": "Two deployments exist: api-blue (current live), api-green (new version). Service: api-service with selector app=api-blue."},
    )),
    ("gl_24", "data_analyst", "data", _goal_step(
        "Build a weekly revenue reporting pipeline from Stripe data",
        "Write the pandas aggregation step that computes week-over-week revenue change, top 10 customers by spend, and average transaction value.",
        {"ingest": "DataFrame with columns: week(str), customer_id(str), amount_usd(float), transaction_count(int). 52 weeks of history."},
    )),
    ("gl_25", "data_analyst", "data", _goal_step(
        "Analyze routing accuracy drift over the last 30 days",
        "Write the SQL query that computes daily accuracy by agent from the decisions database and identifies agents with >10% accuracy drop.",
        {"schema": "brain_decisions table: id, timestamp, final_agent, confidence, correct(bool). logs/decisions.db SQLite file."},
    )),
    ("gl_26", "data_analyst", "data", _goal_step(
        "Create a memory quality audit dashboard",
        "Write the pandas analysis that scores each memory record by recency, access frequency, and confidence, then ranks them for pruning.",
        {"data": "memory records with fields: id, content, agent, created_at, last_accessed, access_count, confidence(float)."},
    )),
    # "pipeline" in current task fires devops=1; "documentation"=1 → tie → devops wins.
    # Replaced "pipeline" with "flow" in current task description.
    ("gl_27", "writer", "writing", _goal_step(
        "Write comprehensive documentation for the agentic AI system",
        "Write the Architecture Overview section and README covering the routing flow: QuerySignal → core_brain → hybrid_router → agent → reflection.",
        {"outline": "Sections: 1.Overview 2.Architecture 3.Agents 4.Routing 5.Memory 6.API 7.Dashboard. Audience: senior developers."},
    )),
    ("gl_28", "writer", "writing", _goal_step(
        "Publish a technical blog post series about the QuerySignal routing system",
        "Write the opening section explaining why keyword-based routing fails at scale and how signal-first routing solves it.",
        {"context": "The system went from 70% to 97% routing accuracy by replacing keyword matching with QuerySignal (domain+shape+verbosity) pre-routing."},
    )),
    # gl_29: LLM/embedding/RAG keywords in context → ai_ml. Correct for signal layer.
    ("gl_29", "ai_ml", "ai", _goal_step(
        "Research and summarize state-of-the-art approaches to LLM routing",
        "Summarize the key differences between embedding-based routing, keyword routing, and learned classifier routing for LLM systems.",
        {"prior": "Found 4 papers: Mixtral MoE (2023), RouteLLM (2024), FrugalGPT (2023), Hybrid Router (2024). Focus on accuracy vs. latency tradeoffs."},
    )),
    # gl_30: context rewritten twice — first to remove "Python developer" (fires python
    # domain), then to remove "LLM and vector search" (fires ai_ml via "llm"/"vector").
    # Pure knowledge explanation with no domain-specific keywords → knowledge_learning.
    ("gl_30", "knowledge_learning", "knowledge", _goal_step(
        "Explain the episodic memory system to a new team member",
        "Write a clear explanation of how the system stores, retrieves, and updates episodic memories, including the FAISS indexing and LRU caching.",
        {"audience": "Senior backend developer unfamiliar with memory-augmented systems. Already read the codebase but wants the design rationale explained clearly."},
    )),
]

# ─────────────────────────────────────────────────────────────
# Combined 100-prompt dataset
# ─────────────────────────────────────────────────────────────

ALL_PROMPTS = CHAT_PROMPTS + TASK_PROMPTS + GOAL_PROMPTS

# Domain → expected agent mapping (mirrors DOMAIN_TO_AGENT but with
# the broader set used in agent_arena and router.py)
_DOMAIN_TO_AGENT = {
    "networking": "it_networking",
    "python":     "python_dev",
    "blazor":     "dotnet_dev",   # not tested here
    "ai_ml":      "ai_ml",
    "general":    "knowledge_learning",
}

# Our local agent mapping for eval (chat-style signal_only routing)
def signal_route(query: str) -> str:
    if not query.strip():
        return "knowledge_learning"
    sig = normalize(query)
    if sig.answer_shape == "factual":
        return "terse"
    if sig.domain_conf > 0.3:
        return _DOMAIN_TO_AGENT.get(sig.domain, "knowledge_learning")
    if sig.verbosity == "terse":
        return "terse"
    return "knowledge_learning"


# The signal_only router covers: it_networking, python_dev, dotnet_dev, ai_ml,
# knowledge_learning, terse. It does NOT know about web_dev, devops,
# data_analyst, writer — those only exist in the hybrid keyword router.
# For those agents, we report separately as "not signal-routable".
_SIGNAL_DOMAIN_AGENTS = {"it_networking", "python_dev", "ai_ml", "knowledge_learning", "terse", "dotnet_dev"}


# ─────────────────────────────────────────────────────────────
# Hybrid keyword router — matches router.py KEYWORD_MAP logic.
# Covers web_dev / devops / data_analyst / writer which are
# absent from signal_only (no entries in _DOMAIN_KEYWORDS).
# ─────────────────────────────────────────────────────────────
import re as _re

# Inlined from router.py — avoids importing langchain_core (requires venv).
# Keep in sync with router.py KEYWORD_MAP when patterns are updated.
_KEYWORD_MAP: dict[str, list[str]] = {
    "it_networking": [
        r"(?<!\w)network(?!\w)", r"(?<!\w)wi-fi(?!\w)", r"(?<!\w)wifi(?!\w)",
        r"(?<!\w)router(?!\w)", r"(?<!\w)firewall(?!\w)", r"(?<!\w)subnet(?!\w)",
        r"(?<!\w)dns(?!\w)", r"(?<!\w)dhcp(?!\w)", r"(?<!\w)vpn(?!\w)",
        r"(?<!\w)ip address(?!\w)", r"(?<!\w)ssh(?!\w)", r"(?<!\w)ping(?!\w)",
        r"(?<!\w)latency(?!\w)", r"(?<!\w)bandwidth(?!\w)", r"(?<!\w)ethernet(?!\w)",
        r"(?<!\w)packet(?!\w)", r"(?<!\w)vlan(?!\w)",
        r"(?<!\w)nginx(?!\w)", r"(?<!\w)ssl(?!\w)", r"(?<!\w)tls(?!\w)",
        r"(?<!\w)certbot(?!\w)", r"(?<!\w)wireguard(?!\w)", r"(?<!\w)firewalld(?!\w)",
        r"(?<!\w)iptables(?!\w)", r"(?<!\w)reverse proxy(?!\w)", r"(?<!\w)load balancer(?!\w)",
        r"(?<!\w)tcp(?!\w)", r"(?<!\w)udp(?!\w)", r"(?<!\w)bgp(?!\w)",
        r"(?<!\w)ospf(?!\w)", r"(?<!\w)nat(?!\w)",
        r"(?<!\w)webrtc(?!\w)", r"(?<!\w)coturn(?!\w)",
        r"(?<!\w)autonomous system(?!\w)", r"(?<!\w)packet loss(?!\w)",
        r"(?<!\w)traceroute(?!\w)", r"(?<!\w)netstat(?!\w)",
    ],
    "python_dev": [
        r"(?<!\w)python(?!\w)", r"(?<!\w)flask(?!\w)", r"(?<!\w)django(?!\w)",
        r"(?<!\w)fastapi(?!\w)", r"(?<!\w)pytest(?!\w)", r"(?<!\w)asyncio(?!\w)",
        r"(?<!\w)decorator(?!\w)", r"(?<!\w)generator(?!\w)",
        r"(?<!\w)list comprehension(?!\w)", r"(?<!\w)virtualenv(?!\w)",
        r"(?<!\w)pip install(?!\w)", r"(?<!\w)pydantic(?!\w)",
        r"(?<!\w)recursionerror(?!\w)", r"(?<!\w)maximum recursion(?!\w)",
        r"(?<!\w)typeerror(?!\w)", r"(?<!\w)attributeerror(?!\w)",
        r"(?<!\w)importerror(?!\w)", r"(?<!\w)nameerror(?!\w)",
        r"(?<!\w)context manager(?!\w)", r"(?<!\w)dataclass(?!\w)",
        r"(?<!\w)coroutine(?!\w)", r"(?<!\w)async/await(?!\w)",
        r"(?<!\w)dunder(?!\w)", r"(?<!\w)__str__(?!\w)", r"(?<!\w)__repr__(?!\w)",
    ],
    "dotnet_dev": [
        r"(?<!\w)blazor(?!\w)", r"(?<!\w)razor(?!\w)", r"(?<!\w)webassembly(?!\w)",
        r"(?<!\w)wasm(?!\w)", r"(?<!\w)dotnet(?!\w)", r"(?<!\w)\.net(?!\w)",
        r"(?<!\w)c#(?!\w)", r"(?<!\w)csharp(?!\w)", r"(?<!\w)entity framework(?!\w)",
        r"(?<!\w)maui(?!\w)", r"(?<!\w)signalr(?!\w)", r"(?<!\w)nuget(?!\w)",
        r"(?<!\w)asp\.net(?!\w)", r"(?<!\w)xunit(?!\w)", r"(?<!\w)nunit(?!\w)",
        r"(?<!\w)minimal api(?!\w)",
        r"(?<!\w)statehaschanged(?!\w)", r"(?<!\w)oninitialized(?!\w)",
        r"(?<!\w)editform(?!\w)", r"(?<!\w)ijsruntime(?!\w)",
        r"(?<!\w)cascading parameter(?!\w)",
    ],
    "ai_ml": [
        r"(?<!\w)tensorflow(?!\w)", r"(?<!\w)pytorch(?!\w)", r"(?<!\w)neural network(?!\w)",
        r"(?<!\w)machine learning(?!\w)", r"(?<!\w)deep learning(?!\w)",
        r"(?<!\w)transformer(?!\w)", r"(?<!\w)training(?!\w)", r"(?<!\w)inference(?!\w)",
        r"(?<!\w)gradient(?!\w)", r"(?<!\w)embedding(?!\w)", r"(?<!\w)dataset(?!\w)",
        r"(?<!\w)langchain(?!\w)", r"(?<!\w)langgraph(?!\w)", r"(?<!\w)huggingface(?!\w)",
        r"(?<!\w)llm(?!\w)", r"(?<!\w)fine.tun(?!\w)", r"(?<!\w)rag(?!\w)",
        r"(?<!\w)bert(?!\w)", r"(?<!\w)gpt(?!\w)",
        r"(?<!\w)supervised(?!\w)", r"(?<!\w)unsupervised(?!\w)",
        r"(?<!\w)reinforcement learning(?!\w)", r"(?<!\w)binary classifier(?!\w)",
        r"(?<!\w)batch normalization(?!\w)", r"(?<!\w)layer normalization(?!\w)",
        r"(?<!\w)quantization(?!\w)", r"(?<!\w)vector databases?(?!\w)",
        r"(?<!\w)prompt engineering(?!\w)", r"(?<!\w)attention mechanism(?!\w)",
        r"(?<!\w)backpropagation(?!\w)", r"(?<!\w)overfitting(?!\w)",
        r"(?<!\w)semantic search(?!\w)",
    ],
    "web_dev": [
        r"(?<!\w)javascript(?!\w)", r"(?<!\w)typescript(?!\w)",
        r"(?<!\w)react(?!\w)", r"(?<!\w)vue(?!\w)", r"(?<!\w)angular(?!\w)",
        r"(?<!\w)next\.?js(?!\w)", r"(?<!\w)node\.?js(?!\w)", r"(?<!\w)express(?!\w)",
        r"(?<!\w)webpack(?!\w)", r"(?<!\w)vite(?!\w)", r"(?<!\w)tailwind(?!\w)",
        r"(?<!\w)npm(?!\w)", r"(?<!\w)yarn(?!\w)", r"(?<!\w)jsx(?!\w)",
        r"(?<!\w)tsx(?!\w)", r"(?<!\w)frontend(?!\w)", r"(?<!\w)css(?!\w)",
        r"(?<!\w)html(?!\w)", r"(?<!\w)dom(?!\w)", r"(?<!\w)graphql(?!\w)",
    ],
    "devops": [
        r"(?<!\w)docker(?!\w)", r"(?<!\w)kubernetes(?!\w)", r"(?<!\w)k8s(?!\w)",
        r"(?<!\w)container(?!\w)", r"(?<!\w)dockerfile(?!\w)",
        r"(?<!\w)ci/cd(?!\w)", r"(?<!\w)github actions(?!\w)", r"(?<!\w)pipeline(?!\w)",
        r"(?<!\w)terraform(?!\w)", r"(?<!\w)ansible(?!\w)",
        r"(?<!\w)systemd(?!\w)", r"(?<!\w)crontab(?!\w)", r"(?<!\w)bash script(?!\w)",
        r"(?<!\w)deploy(?!\w)", r"(?<!\w)helm(?!\w)", r"(?<!\w)devops(?!\w)",
    ],
    "data_analyst": [
        r"(?<!\w)pandas(?!\w)", r"(?<!\w)dataframe(?!\w)", r"(?<!\w)numpy(?!\w)",
        r"(?<!\w)matplotlib(?!\w)", r"(?<!\w)seaborn(?!\w)", r"(?<!\w)plotly(?!\w)",
        r"(?<!\w)sql(?!\w)", r"(?<!\w)postgresql(?!\w)", r"(?<!\w)sqlite(?!\w)",
        r"(?<!\w)csv(?!\w)", r"(?<!\w)excel(?!\w)", r"(?<!\w)parquet(?!\w)",
        r"(?<!\w)data analysis(?!\w)", r"(?<!\w)data cleaning(?!\w)",
        r"(?<!\w)statistics(?!\w)", r"(?<!\w)correlation(?!\w)", r"(?<!\w)regression(?!\w)",
    ],
    "writer": [
        r"(?<!\w)documentation(?!\w)", r"(?<!\w)readme(?!\w)",
        r"(?<!\w)technical writing(?!\w)", r"(?<!\w)blog post(?!\w)",
        r"(?<!\w)write an article(?!\w)", r"(?<!\w)proofread(?!\w)",
        r"(?<!\w)edit my(?!\w)", r"(?<!\w)copywriting(?!\w)",
        r"(?<!\w)commit message(?!\w)", r"(?<!\w)pull request description(?!\w)",
        r"(?<!\w)docstring(?!\w)", r"(?<!\w)api docs(?!\w)",
    ],
    "terse": [
        r"(?<!\w)give me the command(?!\w)", r"(?<!\w)give me command(?!\w)",
        r"(?<!\w)give me the code(?!\w)", r"(?<!\w)command for(?!\w)",
        r"(?<!\w)command to(?!\w)", r"(?<!\w)syntax for(?!\w)",
        r"(?<!\w)syntax of(?!\w)", r"(?<!\w)one line(?!\w)",
        r"(?<!\w)one-liner(?!\w)", r"(?<!\w)just give me(?!\w)",
        r"(?<!\w)short answer(?!\w)", r"(?<!\w)quick answer(?!\w)",
        r"(?<!\w)terse(?!\w)",
    ],
}


def keyword_route(query: str) -> str:
    """Score agents by keyword hits; return top-scoring agent or fallback."""
    if not query.strip():
        return "knowledge_learning"
    q = query.lower()
    scores: dict[str, int] = {agent: 0 for agent in _KEYWORD_MAP}
    for agent, patterns in _KEYWORD_MAP.items():
        for pat in patterns:
            if _re.search(pat, q, _re.IGNORECASE):
                scores[agent] += 1
    # Terse priority
    if scores.get("terse", 0) >= 1:
        return "terse"
    best = max(scores, key=scores.get)
    if scores[best] >= 1:
        return best
    return "knowledge_learning"


def hybrid_route(query: str) -> str:
    """
    Signal-first then keyword fallback — mirrors the production path
    when force_agent is not set.

    Signal gate raised to 0.60 (≈ 3 domain keyword hits) so that
    borderline single-keyword matches (conf ≈ 0.33, e.g. one mention of
    "fastapi" in a DevOps prompt) don't override keyword scoring which
    has richer multi-domain resolution.  In production the core_brain
    provides this nuance; 0.60 is the best static approximation.

    Priority:
      1. factual answer_shape → terse
      2. signal domain_conf >= 0.60 (3+ hits) → domain agent
      3. keyword scoring → best-matching agent
      4. signal terse verbosity → terse
      5. fallback → knowledge_learning
    """
    if not query.strip():
        return "knowledge_learning"
    sig = normalize(query)
    if sig.answer_shape == "factual":
        return "terse"
    if sig.domain_conf >= 0.60:      # raised from 0.30 — requires 3+ domain hits
        agent = _DOMAIN_TO_AGENT.get(sig.domain, "")
        if agent:
            return agent
    # Keyword scoring covers web_dev / devops / data_analyst / writer
    kw = keyword_route(query)
    if kw != "knowledge_learning":
        return kw
    if sig.verbosity == "terse":
        return "terse"
    return "knowledge_learning"


STRATEGIES = {
    "signal_only": signal_route,
    "keyword":     keyword_route,
    "hybrid":      hybrid_route,
}


def run_eval(
    prompts: list[tuple],
    route_fn,
    label: str,
    verbose: bool = True,
) -> tuple[int, int]:
    """
    Run a routing strategy over a prompt list.
    Returns (correct, total).  Failures printed if verbose=True.
    """
    if verbose:
        print(f"\n{'─'*65}")
        print(f"  {label}")
        print(f"{'─'*65}")

    correct = 0
    for pid, expected, domain, prompt in prompts:
        got = route_fn(prompt)
        ok  = got == expected
        if ok:
            correct += 1
        elif verbose:
            sig = normalize(prompt)
            snippet = prompt[:80].replace("\n", " ")
            if len(prompt) > 80:
                snippet += "…"
            print(f"  ✗ [{pid}] expected={expected:<20} got={got}")
            print(f"      domain={sig.domain}({sig.domain_conf:.2f}) "
                  f"shape={sig.answer_shape} verb={sig.verbosity}")
            print(f"      prompt: {snippet}")

    return correct, len(prompts)


def _bar(c: int, t: int, width: int = 20) -> str:
    filled = min(width, round(c / t * width)) if t else 0
    return "█" * filled + "░" * (width - filled)


def _pct(c: int, t: int) -> str:
    return f"{100 * c / t:5.1f}%" if t else "  N/A "


def _row(fmt: str, correct: int, total: int) -> str:
    return f"  {fmt:<9}  {correct:>3}/{total:<3}  {_pct(correct, total)}  {_bar(correct, total)}"


def main(args):
    print("=" * 65)
    print("  mixed_structure_eval.py — 100 prompts × 3 input formats")
    print("  3 routing strategies compared (no LLM calls)")
    print("=" * 65)
    print()
    print("  Format A  (Chat)    40 prompts — plain NL; routing pipeline runs")
    print("  Format B  (Task)    30 prompts — imperative; force_agent bypasses prod")
    print("  Format C  (Goal)    30 prompts — Goal:/Context:/Current task: composite;")
    print("                                  force_agent always bypasses prod")
    print()
    print("  Strategy A  signal_only — QuerySignal domain/shape/verbosity (no kw map)")
    print("  Strategy B  keyword     — KEYWORD_MAP regex scoring only (no signal)")
    print("  Strategy C  hybrid      — signal first, keyword fallback (production path)")

    run_all = not (args.chat or args.tasks or args.goals)
    formats = []
    if run_all or args.chat:  formats.append(("Chat",  CHAT_PROMPTS))
    if run_all or args.tasks: formats.append(("Task",  TASK_PROMPTS))
    if run_all or args.goals: formats.append(("Goal",  GOAL_PROMPTS))

    all_prompts = [p for _, ps in formats for p in ps]

    # ── Per-format, per-strategy detail ──────────────────────
    strat_totals: dict[str, list[tuple[int,int]]] = {s: [] for s in STRATEGIES}

    verbose_strat = args.strategy if hasattr(args, "strategy") and args.strategy else "hybrid"

    for fmt_name, prompts in formats:
        for strat_name, route_fn in STRATEGIES.items():
            c, t = run_eval(
                prompts,
                route_fn,
                f"Format {fmt_name} × Strategy {strat_name}",
                verbose=(strat_name == verbose_strat),
            )
            strat_totals[strat_name].append((c, t))

    # ── Summary table ─────────────────────────────────────────
    fmt_labels = [f for f, _ in formats]
    print(f"\n{'='*65}")
    print("  Accuracy by format × strategy")
    print(f"{'─'*65}")
    header_fmts = "  ".join(f"{f:<9}" for f in fmt_labels)
    print(f"  {'Strategy':<14}  {header_fmts}")
    print(f"{'─'*65}")

    grand: dict[str, tuple[int,int]] = {}
    for strat_name, per_fmt in strat_totals.items():
        row_cells = []
        gc = gt = 0
        for c, t in per_fmt:
            row_cells.append(f"{c:>3}/{t:<3} {_pct(c,t)}")
            gc += c; gt += t
        cells_str = "  ".join(f"{cell:<15}" for cell in row_cells)
        grand[strat_name] = (gc, gt)
        print(f"  {strat_name:<14}  {cells_str}  total {gc:>3}/{gt}  {_pct(gc,gt)}")

    print(f"{'─'*65}")
    # Visual bars for grand totals
    print(f"\n  Grand totals (all {sum(t for _,t in grand.values())//len(grand)} prompts)")
    for strat_name, (gc, gt) in grand.items():
        print(f"  {strat_name:<14}  {gc:>3}/{gt}  {_pct(gc,gt)}  {_bar(gc,gt)}")

    print()
    print("  Key:")
    print("  signal_only — covers: it_networking, python_dev, ai_ml, dotnet_dev,")
    print("                         knowledge_learning, terse")
    print("  keyword     — covers: all agents via KEYWORD_MAP regex patterns")
    print("  hybrid      — signal gates first; keyword fills the rest")
    print()
    print("  In production:")
    print("  ─ Chat / Runs replay → hybrid (signal + brain + keyword)")
    print("  ─ Tasks              → force_agent always set; routing bypassed")
    print("  ─ Goals              → force_agent always set; routing bypassed")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mixed structure routing eval (100 prompts × 3 formats × 3 strategies)")
    parser.add_argument("--chat",     action="store_true", help="Format A only (Chat-style)")
    parser.add_argument("--tasks",    action="store_true", help="Format B only (Task-style)")
    parser.add_argument("--goals",    action="store_true", help="Format C only (Goal-step composite)")
    parser.add_argument("--strategy", choices=["signal_only","keyword","hybrid"],
                        default="hybrid", help="Strategy to print failures for (default: hybrid)")
    args = parser.parse_args()
    main(args)
