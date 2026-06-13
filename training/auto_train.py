#!/usr/bin/env python3
"""
Auto-training and routing evaluation with 50 predefined prompts.

Phases:
  1. Memory seeding   — saves 50 domain knowledge snippets via nomic-embed-text
                         (fast, ~2 min, improves retrieval immediately)
  2. Routing eval     — runs 50 prompts through the full coordinator + phi4-mini
                         (slow, ~35-70 min, measures routing accuracy & response quality)

Results saved to: auto_train_results.json (resumable — skips already-completed prompts)

Usage:
  python3 auto_train.py                  # full run
  python3 auto_train.py --seed-only      # phase 1 only (fast)
  python3 auto_train.py --eval-only      # phase 2 only
  python3 auto_train.py --resume         # skip prompts already in results file
  python3 auto_train.py --report         # print report from existing results file

Run with the langgraph venv:
  PYTHONPATH=. \\
    python3 auto_train.py
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "auto_train_results.json")

# ── 50 Prompts ────────────────────────────────────────────────
# Format: (id, expected_agent, domain, prompt)
PROMPTS = [
    # ── IT Networking (10) ──────────────────────────────────────
    ("net_01", "it_networking", "networking",
     "How do I configure a static IP address on Ubuntu Server 22.04?"),
    ("net_02", "it_networking", "networking",
     "Why is nginx returning 502 Bad Gateway when I proxy to localhost:3000?"),
    ("net_03", "it_networking", "networking",
     "Explain the difference between TCP and UDP and when to use each."),
    ("net_04", "it_networking", "networking",
     "Set up a Wireguard VPN peer-to-peer tunnel between two remote Linux servers."),
    ("net_05", "it_networking", "networking",
     "My DNS changes are not propagating after 24 hours. What should I check?"),
    ("net_06", "it_networking", "networking",
     "Configure firewalld to allow only SSH on port 22 and HTTPS on port 443."),
    ("net_07", "it_networking", "networking",
     "What does a subnet mask of /24 mean and how many hosts does it support?"),
    ("net_08", "it_networking", "networking",
     "Set up Let's Encrypt SSL certificate renewal with nginx reverse proxy."),
    ("net_09", "it_networking", "networking",
     "What is BGP and how does autonomous system routing work?"),
    ("net_10", "it_networking", "networking",
     "Diagnose and fix intermittent packet loss between two VLANs on a managed switch."),

    # ── Python Dev (12) ─────────────────────────────────────────
    ("py_01", "python_dev", "python",
     "Write a FastAPI endpoint that accepts a JSON body with validation and returns a filtered list."),
    ("py_02", "python_dev", "python",
     "I am getting RecursionError: maximum recursion depth exceeded. How do I debug and fix this?"),
    ("py_03", "python_dev", "python",
     "Explain Python decorators and write a practical caching decorator example."),
    ("py_04", "python_dev", "python",
     "How do I correctly use async/await in Python for concurrent database queries?"),
    ("py_05", "python_dev", "python",
     "Write a Python class that implements a database connection pool with thread safety."),
    ("py_06", "python_dev", "python",
     "What is the difference between __str__ and __repr__ in Python?"),
    ("py_07", "python_dev", "python",
     "Debug: TypeError: 'NoneType' object is not subscriptable at line 47. What causes this?"),
    ("py_08", "python_dev", "python",
     "Write pytest unit tests for a function that calls an external REST API."),
    ("py_09", "python_dev", "python",
     "Implement a rate limiter in Python using a token bucket algorithm."),
    ("py_10", "python_dev", "python",
     "Explain Python context managers and implement one for automatic file locking."),
    ("py_11", "python_dev", "python",
     "Write a script to parse a large CSV file in chunks and compute per-column statistics."),
    ("py_12", "python_dev", "python",
     "How do dataclasses differ from regular classes and namedtuples in Python?"),

    # ── Blazor Dev (8) ──────────────────────────────────────────
    ("blz_01", "dotnet_dev", "dotnet",
     "Create a Blazor component that displays a sortable, paginated data table."),
    ("blz_02", "dotnet_dev", "dotnet",
     "How do I pass parameters between parent and child components in Blazor?"),
    ("blz_03", "dotnet_dev", "dotnet",
     "Implement form validation with custom error messages in a Blazor Server app."),
    ("blz_04", "dotnet_dev", "dotnet",
     "What is the difference between Blazor Server and Blazor WebAssembly?"),
    ("blz_05", "dotnet_dev", "dotnet",
     "How do I call a JavaScript function from C# in Blazor using IJSRuntime?"),
    ("blz_06", "dotnet_dev", "dotnet",
     "Implement cascading parameters to share state across a Blazor component tree."),
    ("blz_07", "dotnet_dev", "dotnet",
     "Set up state management in Blazor using a shared service with StateHasChanged."),
    ("blz_08", "dotnet_dev", "dotnet",
     "Create a Blazor component that auto-refreshes a data table every 30 seconds."),

    # ── AI / ML (8) ─────────────────────────────────────────────
    ("ai_01", "ai_ml", "ai_ml",
     "Explain how attention mechanisms work in the Transformer architecture."),
    ("ai_02", "ai_ml", "ai_ml",
     "What is the difference between supervised, unsupervised, and reinforcement learning?"),
    ("ai_03", "ai_ml", "ai_ml",
     "How do I evaluate a binary classifier beyond accuracy? List and explain key metrics."),
    ("ai_04", "ai_ml", "ai_ml",
     "What is overfitting and what techniques prevent it in deep learning?"),
    ("ai_05", "ai_ml", "ai_ml",
     "Explain gradient descent, learning rate, and why learning rate scheduling matters."),
    ("ai_06", "ai_ml", "ai_ml",
     "What are word embeddings and how are they trained? Compare Word2Vec and transformer embeddings."),
    ("ai_07", "ai_ml", "ai_ml",
     "How does Retrieval Augmented Generation (RAG) work and when should you use it?"),
    ("ai_08", "ai_ml", "ai_ml",
     "What is the difference between fine-tuning a model and using prompt engineering?"),

    # ── Knowledge / Learning (7) ────────────────────────────────
    ("kn_01", "knowledge_learning", "knowledge",
     "Explain the CAP theorem in distributed systems with a practical example."),
    ("kn_02", "knowledge_learning", "knowledge",
     "What are the SOLID principles? Explain each with a one-sentence summary."),
    ("kn_03", "knowledge_learning", "knowledge",
     "Explain Big O notation and give examples of O(1), O(n), O(n log n), O(n²)."),
    ("kn_04", "knowledge_learning", "knowledge",
     "What is eventual consistency and how does it differ from strong consistency?"),
    ("kn_05", "knowledge_learning", "knowledge",
     "Compare microservices vs monolithic architecture: trade-offs and when to use each."),
    ("kn_06", "knowledge_learning", "knowledge",
     "Explain dependency injection with a real-world code example."),
    ("kn_07", "knowledge_learning", "knowledge",
     "What is the difference between synchronous and asynchronous programming models?"),

    # ── Terse (5) ───────────────────────────────────────────────
    ("te_01", "terse", "terse",
     "What port does HTTPS use?"),
    ("te_02", "terse", "terse",
     "What does HTTP status 429 mean?"),
    ("te_03", "terse", "terse",
     "What is 2 to the power of 10?"),
    ("te_04", "terse", "terse",
     "What does SQL stand for?"),
    ("te_05", "terse", "terse",
     "What is the default port for PostgreSQL?"),

    # ── IT Networking batch 2 (10) ──────────────────────────────
    ("net_11", "it_networking", "networking",
     "Explain how OSPF routing protocol works and when to prefer it over BGP."),
    ("net_12", "it_networking", "networking",
     "Debug: SSH connection drops after exactly 30 seconds of inactivity. How do I fix keepalive?"),
    ("net_13", "it_networking", "networking",
     "What is the difference between the TCP/IP model and the OSI model layers?"),
    ("net_14", "it_networking", "networking",
     "Configure nginx as a round-robin load balancer across three upstream application servers."),
    ("net_15", "it_networking", "networking",
     "How does the TLS handshake work step by step when establishing an HTTPS connection?"),
    ("net_16", "it_networking", "networking",
     "My iptables DROP rule is not blocking traffic as expected. How do I debug the rule chain?"),
    ("net_17", "it_networking", "networking",
     "Create a VLAN on Ubuntu using ip commands and configure inter-VLAN routing with a bridge."),
    ("net_18", "it_networking", "networking",
     "What is NAT and how does MASQUERADE differ from SNAT in iptables?"),
    ("net_19", "it_networking", "networking",
     "What is the difference between UDP multicast and broadcast, and when should I use each?"),
    ("net_20", "it_networking", "networking",
     "Configure a Certbot post-renewal hook to automatically reload nginx after certificate renewal."),

    # ── Python Dev batch 2 (10) ─────────────────────────────────
    ("py_13", "python_dev", "python",
     "Write a Python asyncio web scraper that respects rate limits using asyncio.Semaphore."),
    ("py_14", "python_dev", "python",
     "Debug: AttributeError: 'NoneType' object has no attribute 'split' on line 23. What causes this?"),
    ("py_15", "python_dev", "python",
     "Implement a Python generator that streams a large JSON file line by line without loading it into memory."),
    ("py_16", "python_dev", "python",
     "How do I use Python multiprocessing Pool.map to parallelize CPU-bound image processing tasks?"),
    ("py_17", "python_dev", "python",
     "Write FastAPI middleware that logs request timing and injects a correlation ID into response headers."),
    ("py_18", "python_dev", "python",
     "Explain Python's GIL: what it is, when it limits performance, and when threads are still useful."),
    ("py_19", "python_dev", "python",
     "Create a Python dataclass with input validation and computed fields using __post_init__."),
    ("py_20", "python_dev", "python",
     "Debug: ImportError: cannot import name 'APIRouter' from 'fastapi'. What is wrong?"),
    ("py_21", "python_dev", "python",
     "Write a Python script using watchdog that monitors a directory and processes new files as they arrive."),
    ("py_22", "python_dev", "python",
     "How do generator expressions differ from list comprehensions in Python memory usage?"),

    # ── Blazor Dev batch 2 (8) ──────────────────────────────────
    ("blz_09", "dotnet_dev", "dotnet",
     "Create a Blazor component that handles file upload with a real-time progress bar using stream."),
    ("blz_10", "dotnet_dev", "dotnet",
     "How do I implement JWT bearer token authentication in a Blazor Server application?"),
    ("blz_11", "dotnet_dev", "dotnet",
     "Debug: StateHasChanged is called but the Blazor component UI does not update. What is wrong?"),
    ("blz_12", "dotnet_dev", "dotnet",
     "Write a Blazor EditForm with custom validation attributes and inline field-level error messages."),
    ("blz_13", "dotnet_dev", "dotnet",
     "How do I inject a scoped service into a Blazor component using the @inject directive?"),
    ("blz_14", "dotnet_dev", "dotnet",
     "Implement lazy loading of Blazor WebAssembly assemblies to reduce the initial download size."),
    ("blz_15", "dotnet_dev", "dotnet",
     "Create a real-time data dashboard in Blazor Server using SignalR and IJSRuntime chart interop."),
    ("blz_16", "dotnet_dev", "dotnet",
     "What is the Blazor component lifecycle and when does each lifecycle method fire?"),

    # ── AI / ML batch 2 (8) ─────────────────────────────────────
    ("ai_09", "ai_ml", "ai_ml",
     "Explain how BERT differs from GPT in architecture, pre-training objective, and use cases."),
    ("ai_10", "ai_ml", "ai_ml",
     "What is the vanishing gradient problem and how do ResNets with skip connections solve it?"),
    ("ai_11", "ai_ml", "ai_ml",
     "How do I choose between PyTorch and TensorFlow for a new deep learning research project?"),
    ("ai_12", "ai_ml", "ai_ml",
     "What is the difference between batch normalization and layer normalization in transformers?"),
    ("ai_13", "ai_ml", "ai_ml",
     "How does transfer learning work and what are the steps to fine-tune a pretrained HuggingFace model?"),
    ("ai_14", "ai_ml", "ai_ml",
     "How does the LangGraph StateGraph manage multi-step agent workflows and conditional edges?"),
    ("ai_15", "ai_ml", "ai_ml",
     "What is model quantization and when should I use INT8 versus FP16 for inference?"),
    ("ai_16", "ai_ml", "ai_ml",
     "Explain RLHF and how reinforcement learning from human feedback improves LLM alignment."),

    # ── Knowledge / Learning batch 2 (7) ────────────────────────
    ("kn_08", "knowledge_learning", "knowledge",
     "What is the difference between REST and GraphQL APIs and when should I use each?"),
    ("kn_09", "knowledge_learning", "knowledge",
     "Explain the Actor model of concurrency and how it differs from shared-memory threads."),
    ("kn_10", "knowledge_learning", "knowledge",
     "What are design patterns? Explain the Singleton, Observer, and Factory patterns with examples."),
    ("kn_11", "knowledge_learning", "knowledge",
     "What is event sourcing and how does it differ from traditional CRUD database storage?"),
    ("kn_12", "knowledge_learning", "knowledge",
     "What is the difference between horizontal scaling and vertical scaling for web services?"),
    ("kn_13", "knowledge_learning", "knowledge",
     "Explain immutability in programming and why it matters for concurrency safety and testability."),
    ("kn_14", "knowledge_learning", "knowledge",
     "What is a deadlock in concurrent systems and what strategies prevent it?"),

    # ── Terse batch 2 (7) ───────────────────────────────────────
    ("te_06", "terse", "terse",
     "What port does SSH use?"),
    ("te_07", "terse", "terse",
     "What does DNS stand for?"),
    ("te_08", "terse", "terse",
     "What is the default port for Redis?"),
    ("te_09", "terse", "terse",
     "What does HTTP status 404 mean?"),
    ("te_10", "terse", "terse",
     "What is 2 to the power of 16?"),
    ("te_11", "terse", "terse",
     "What port does FTP use?"),
    ("te_12", "terse", "terse",
     "What does YAML stand for?"),

    # ── Web Dev (10) ─────────────────────────────────────────────
    ("web_01", "web_dev", "web",
     "How do I implement React useEffect to fetch data on component mount without an infinite loop?"),
    ("web_02", "web_dev", "web",
     "Why is my CSS flexbox not centering items vertically? Show me the correct properties."),
    ("web_03", "web_dev", "web",
     "Write a TypeScript React component for a controlled form input with validation."),
    ("web_04", "web_dev", "web",
     "Explain the difference between React useState and useReducer and when to use each."),
    ("web_05", "web_dev", "web",
     "How do I set up Webpack to split code and lazy-load route components in a React app?"),
    ("web_06", "web_dev", "web",
     "Debug: my React component re-renders on every parent render even with identical props."),
    ("web_07", "web_dev", "web",
     "Write a Vue 3 Composition API component that watches a reactive object and debounces API calls."),
    ("web_08", "web_dev", "web",
     "How do I implement a CSS grid layout with responsive breakpoints without a framework?"),
    ("web_09", "web_dev", "web",
     "What is the difference between JavaScript event bubbling and event capturing?"),
    ("web_10", "web_dev", "web",
     "Implement a React custom hook that syncs state with localStorage and handles SSR."),

    # ── DevOps (10) ──────────────────────────────────────────────
    ("ops_01", "devops", "devops",
     "Write a GitHub Actions workflow that runs tests, builds a Docker image, and pushes to GHCR."),
    ("ops_02", "devops", "devops",
     "My Docker container exits immediately with code 1. How do I debug and find the root cause?"),
    ("ops_03", "devops", "devops",
     "Write a Dockerfile for a Python FastAPI app that minimizes image size using multi-stage builds."),
    ("ops_04", "devops", "devops",
     "How do I configure Kubernetes resource requests and limits to prevent OOM kills in production?"),
    ("ops_05", "devops", "devops",
     "Set up a CI/CD pipeline in GitLab CI that deploys to a staging Kubernetes cluster on merge."),
    ("ops_06", "devops", "devops",
     "Explain Helm chart structure and write a values.yaml override for environment-specific config."),
    ("ops_07", "devops", "devops",
     "How do I write a Terraform module for an AWS S3 bucket with versioning and lifecycle rules?"),
    ("ops_08", "devops", "devops",
     "Debug: Kubernetes pod is stuck in CrashLoopBackOff. Walk me through diagnosing this."),
    ("ops_09", "devops", "devops",
     "Configure Prometheus and Grafana to alert when API latency exceeds 2s for 5 minutes."),
    ("ops_10", "devops", "devops",
     "What is the difference between a Kubernetes Deployment and a StatefulSet?"),

    # ── Data Analyst (10) ────────────────────────────────────────
    ("dat_01", "data_analyst", "data",
     "Write a pandas query to find the top 5 customers by revenue grouped by region in a DataFrame."),
    ("dat_02", "data_analyst", "data",
     "How do I join two DataFrames in pandas on multiple columns and handle NaN in the result?"),
    ("dat_03", "data_analyst", "data",
     "Write a SQL query to calculate a 7-day rolling average of daily sales grouped by product."),
    ("dat_04", "data_analyst", "data",
     "Explain the difference between INNER JOIN, LEFT JOIN, and FULL OUTER JOIN in SQL."),
    ("dat_05", "data_analyst", "data",
     "How do I use matplotlib to create a multi-panel chart comparing three time series on the same axes?"),
    ("dat_06", "data_analyst", "data",
     "Debug: my pandas groupby aggregation is returning unexpected NaN values. What causes this?"),
    ("dat_07", "python_dev", "python",
     "Write a Python script to load a CSV into a SQLite database and run aggregation queries."),
    ("dat_08", "data_analyst", "data",
     "How do I detect and handle outliers in a numeric column using pandas and scipy?"),
    ("dat_09", "data_analyst", "data",
     "Write an SQL window function to rank users by their total spend within each subscription tier."),
    ("dat_10", "data_analyst", "data",
     "How do I pivot a pandas DataFrame from long to wide format and aggregate duplicate values?"),

    # ── Writer (8) ───────────────────────────────────────────────
    ("wrt_01", "writer", "writing",
     "Write a technical blog post introduction about FAISS vector search for a developer audience."),
    ("wrt_02", "writer", "writing",
     "Rewrite this paragraph to be clearer and more concise for a non-technical business audience."),
    ("wrt_03", "writer", "writing",
     "Draft a changelog entry for a v1.2 release that fixes authentication and adds dark mode."),
    ("wrt_04", "writer", "writing",
     "Write a README section explaining how to configure environment variables with good examples."),
    ("wrt_05", "writer", "writing",
     "Help me edit this documentation section: it is too dense and developers skip it entirely."),
    ("wrt_06", "writer", "writing",
     "Write a short LinkedIn post announcing an open-source project launch targeting developers."),
    ("wrt_07", "writer", "writing",
     "Draft a professional email to a client explaining a two-week delay due to unexpected complexity."),
    ("wrt_08", "python_dev", "python",
     "Write an API reference docstring for a Python function that handles paginated database queries."),
]

assert len(PROMPTS) == 138, f"Expected 138 prompts, got {len(PROMPTS)}"  # noqa

# ── Memory seed corpus ────────────────────────────────────────
# High-quality domain knowledge to seed retrieval BEFORE routing eval.
# Format: (agent, mem_type, quality, content)
SEED_MEMORIES = [
    # Networking
    ("it_networking", "code",    0.90, "Ubuntu static IP: edit /etc/netplan/01-netcfg.yaml, set dhcp4: no, addresses: [192.168.1.100/24], gateway4: 192.168.1.1, apply with netplan apply"),
    ("it_networking", "failure", 0.85, "nginx 502 Bad Gateway caused by upstream application not listening on configured port — check app is running and proxy_pass port matches"),
    ("it_networking", "lesson",  0.80, "TCP provides reliable ordered delivery with handshakes and retransmission; UDP is connectionless and faster but unreliable — use UDP for streaming/DNS, TCP for everything that must arrive"),
    ("it_networking", "code",    0.88, "Wireguard VPN peer config: [Interface] PrivateKey=..., Address=10.0.0.1/24; [Peer] PublicKey=..., AllowedIPs=10.0.0.2/32, Endpoint=remote.host:51820"),
    ("it_networking", "lesson",  0.78, "DNS propagation delay caused by TTL on old records — check TTL with dig, reduce before making changes, wait TTL seconds after change"),
    ("it_networking", "code",    0.85, "firewalld: firewall-cmd --permanent --add-service=ssh; firewall-cmd --permanent --add-service=https; firewall-cmd --permanent --remove-service=dhcpv6-client; firewall-cmd --reload"),
    ("it_networking", "lesson",  0.82, "/24 subnet = 255.255.255.0 mask, supports 254 hosts (256 - network - broadcast), CIDR notation counts the number of fixed bits in the network prefix"),
    ("it_networking", "code",    0.87, "Let's Encrypt with nginx: certbot --nginx -d example.com; certbot renews automatically via systemd timer; add ssl_certificate and ssl_certificate_key to nginx server block"),
    ("it_networking", "lesson",  0.79, "BGP is the exterior gateway protocol that routes traffic between autonomous systems (AS) on the internet; uses path vector routing; each ISP has an AS number"),
    ("it_networking", "failure", 0.83, "Inter-VLAN packet loss: check that trunk port allows both VLANs, verify no ACL blocks traffic, check that SVI (Layer 3 switch) or router-on-a-stick is configured"),
    # Python
    ("python_dev", "code",    0.92, "FastAPI with Pydantic validation: from fastapi import FastAPI; from pydantic import BaseModel; class Item(BaseModel): name: str; price: float; app = FastAPI(); @app.post('/items') async def create_item(item: Item): return item"),
    ("python_dev", "failure", 0.86, "RecursionError: maximum recursion depth exceeded — missing base case in recursive function; fix by adding explicit base condition or converting to iterative with explicit stack"),
    ("python_dev", "code",    0.89, "Python decorator example: def cache(func): store={}; def wrapper(*args): if args not in store: store[args]=func(*args); return store[args]; return wrapper"),
    ("python_dev", "lesson",  0.84, "Python async/await: mark IO-bound functions with async def, use await before coroutines, run with asyncio.run() or within existing event loop; never block inside async with time.sleep()"),
    ("python_dev", "code",    0.88, "Thread-safe connection pool: use threading.Semaphore to limit connections, threading.Lock to protect the pool list, __enter__/__exit__ for context manager usage"),
    ("python_dev", "lesson",  0.80, "__str__ returns human-readable string for end users; __repr__ returns unambiguous developer representation that ideally could recreate the object — repr is used in the REPL"),
    ("python_dev", "failure", 0.87, "TypeError: NoneType not subscriptable means a variable expected to be a list/dict is None — trace back where the value was set, likely a function that should return something but falls through without explicit return"),
    ("python_dev", "code",    0.90, "pytest with mocked API: from unittest.mock import patch; @patch('module.requests.get') def test_func(mock_get): mock_get.return_value.json.return_value = {'key': 'val'}; assert result == expected"),
    ("python_dev", "code",    0.85, "Token bucket rate limiter: maintain tokens count, refill at rate/second, decrement on each request, reject when tokens < 1; use threading.Lock for thread safety"),
    ("python_dev", "code",    0.86, "Context manager with __enter__/__exit__: class FileLock: def __enter__(self): acquire(); return self; def __exit__(self, *args): release(); or use @contextmanager decorator with try/finally"),
    ("python_dev", "lesson",  0.82, "CSV chunk processing: pd.read_csv('file.csv', chunksize=10000) returns iterator; for chunk in reader: process(chunk); avoids loading full file into memory for large datasets"),
    ("python_dev", "lesson",  0.80, "Python dataclasses vs namedtuple: dataclass is mutable by default, supports inheritance, default factories, and post_init; namedtuple is immutable, hashable, slightly less memory; dataclass preferred for most cases"),
    # Blazor
    ("dotnet_dev", "code",    0.88, "Blazor sortable table: use @onclick on <th> to toggle sort direction, maintain SortField and SortAscending properties, use LINQ OrderBy/OrderByDescending in getter"),
    ("dotnet_dev", "lesson",  0.82, "Blazor parameter passing: child declares [Parameter] public T Value { get; set; } and [Parameter] public EventCallback<T> ValueChanged { get; set; }; parent uses <Child @bind-Value='field' />"),
    ("dotnet_dev", "code",    0.87, "Blazor form validation: use <EditForm Model='model' OnValidSubmit='Submit'>, add <DataAnnotationsValidator/>, use [Required][StringLength] on model properties, <ValidationSummary/> for errors"),
    ("dotnet_dev", "lesson",  0.80, "Blazor Server runs C# on server, uses SignalR for DOM updates, supports full .NET; Blazor WASM runs in browser via WebAssembly, limited .NET APIs, larger initial download, no server needed"),
    ("dotnet_dev", "code",    0.85, "IJSRuntime JS call: @inject IJSRuntime JS; await JS.InvokeVoidAsync('functionName', arg1, arg2); for return value: var result = await JS.InvokeAsync<string>('funcName', args)"),
    ("dotnet_dev", "code",    0.84, "Cascading parameters: wrap with <CascadingValue Value='this'>@ChildContent</CascadingValue>; child uses [CascadingParameter] to receive the value without explicit prop drilling"),
    ("dotnet_dev", "lesson",  0.79, "Blazor state management: inject singleton AppState service, subscribe to StateChanged event in OnInitialized, call StateHasChanged() after mutation to trigger re-render"),
    ("dotnet_dev", "code",    0.83, "Auto-refresh component: use System.Timers.Timer in OnInitialized, fire InvokeAsync(StateHasChanged) in Elapsed handler, dispose timer in IDisposable.Dispose()"),
    # AI/ML
    ("ai_ml", "lesson",  0.88, "Transformer attention: Query, Key, Value matrices derived by multiplying input embeddings with learned weight matrices; attention score = softmax(QK^T/sqrt(d_k))V; allows each token to attend to all others"),
    ("ai_ml", "lesson",  0.85, "Supervised: labeled data maps input→output; Unsupervised: finds patterns without labels (clustering, dimensionality reduction); Reinforcement: agent learns by reward signal from environment"),
    ("ai_ml", "lesson",  0.87, "Binary classifier metrics beyond accuracy: Precision (TP/TP+FP), Recall (TP/TP+FN), F1 (harmonic mean), AUC-ROC (area under ROC curve), use F1 for imbalanced classes"),
    ("ai_ml", "lesson",  0.84, "Overfitting prevention: dropout layers, L1/L2 regularization, early stopping on validation loss, data augmentation, reduce model complexity, increase training data"),
    ("ai_ml", "lesson",  0.86, "Gradient descent: minimize loss by moving params in negative gradient direction; learning rate controls step size; too high=diverge, too low=slow; cosine/step/warmup schedules improve convergence"),
    ("ai_ml", "lesson",  0.83, "Word2Vec trains embeddings by predicting context words (skip-gram) or center word (CBOW); transformer embeddings are contextual (same word different vectors per context) and richer"),
    ("ai_ml", "lesson",  0.89, "RAG: retrieve relevant documents from a vector store based on query embedding, append as context to the LLM prompt, LLM generates answer grounded in retrieved documents — reduces hallucination"),
    ("ai_ml", "lesson",  0.85, "Fine-tuning updates model weights on domain-specific data (expensive, high ROI for specialized tasks); prompt engineering shapes model behavior without changing weights (cheap, less powerful)"),
    # Knowledge/Learning
    ("knowledge_learning", "lesson",  0.88, "CAP theorem: distributed system can guarantee at most 2 of: Consistency (all nodes same data), Availability (every request gets response), Partition tolerance (handles network splits) — partition tolerance is required in real networks"),
    ("knowledge_learning", "lesson",  0.86, "SOLID: Single Responsibility (one reason to change), Open/Closed (open for extension, closed for modification), Liskov Substitution (subtypes replaceable), Interface Segregation (no fat interfaces), Dependency Inversion (depend on abstractions)"),
    ("knowledge_learning", "lesson",  0.84, "Big O: O(1) hash lookup; O(log n) binary search; O(n) linear scan; O(n log n) merge sort; O(n²) bubble sort; O(2^n) recursive subsets — describes growth rate not absolute speed"),
    ("knowledge_learning", "lesson",  0.82, "Eventual consistency: all nodes will converge to same state given no new updates — used in DNS, Cassandra, DynamoDB; strong consistency ensures all reads see latest write — used in single-master SQL DBs"),
    ("knowledge_learning", "lesson",  0.85, "Microservices: independently deployable, technology agnostic, scales per service, high operational complexity; monolith: simpler to develop/debug, shared memory, harder to scale individual components — start monolith, extract services when needed"),
    ("knowledge_learning", "code",    0.83, "Dependency injection: class UserService(db: Database) — dependencies passed in constructor rather than instantiated inside; enables testability (inject mock), loose coupling, configurable behavior"),
    ("knowledge_learning", "lesson",  0.81, "Synchronous: each operation blocks the thread until complete; asynchronous: operations yield control while waiting for IO, allowing other work to proceed — async is essential for high-concurrency servers"),
    # Terse batch 1
    ("terse", "lesson",  0.90, "HTTPS uses TCP port 443"),
    ("terse", "lesson",  0.90, "HTTP 429 Too Many Requests — client has exceeded the rate limit; server may include Retry-After header"),
    ("terse", "lesson",  0.90, "2^10 = 1024"),
    ("terse", "lesson",  0.90, "SQL stands for Structured Query Language"),
    ("terse", "lesson",  0.90, "PostgreSQL default port is 5432"),
    # Networking batch 2
    ("it_networking", "lesson",  0.83, "OSPF is an interior gateway protocol using Dijkstra's SPF algorithm; best for single AS with many routers; BGP is for inter-AS routing on the internet"),
    ("it_networking", "code",    0.85, "SSH keepalive: in /etc/ssh/sshd_config set ClientAliveInterval 60 and ClientAliveCountMax 3; on client side add ServerAliveInterval 60 to ~/.ssh/config"),
    ("it_networking", "lesson",  0.80, "OSI has 7 layers (Physical, Data Link, Network, Transport, Session, Presentation, Application); TCP/IP collapses to 4 (Network Access, Internet, Transport, Application) — practical model used in implementation"),
    ("it_networking", "code",    0.86, "nginx load balancer: upstream backend { server 127.0.0.1:3001; server 127.0.0.1:3002; server 127.0.0.1:3003; } server { location / { proxy_pass http://backend; } }"),
    ("it_networking", "lesson",  0.85, "TLS handshake: ClientHello → ServerHello + Certificate → Client verifies cert + sends pre-master secret → both derive session keys → Finished messages exchanged → encrypted data begins"),
    ("it_networking", "failure", 0.84, "iptables debug: use iptables -L -v -n --line-numbers to see rule hit counters; add LOG target before DROP to trace packets; check rule order — first match wins"),
    ("it_networking", "code",    0.83, "VLAN on Ubuntu: ip link add link eth0 name eth0.10 type vlan id 10; ip addr add 192.168.10.1/24 dev eth0.10; ip link set eth0.10 up; for bridging add both to bridge with ip link"),
    ("it_networking", "lesson",  0.81, "NAT MASQUERADE dynamically uses the outbound interface IP (ideal for DHCP/PPP); SNAT uses a fixed IP you specify — use SNAT for servers with a static IP for performance"),
    ("it_networking", "lesson",  0.80, "UDP multicast sends to a group address (224.0.0.0/4), only subscribed receivers get packets; broadcast sends to 255.255.255.255, all hosts on segment receive — multicast preferred for efficiency"),
    ("it_networking", "code",    0.84, "Certbot deploy hook: create /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh with 'systemctl reload nginx'; chmod +x the file; certbot runs it automatically after successful renewal"),
    # Python batch 2
    ("python_dev", "code",    0.88, "asyncio rate-limited scraper: semaphore = asyncio.Semaphore(5); async with semaphore: async with session.get(url) as r: ...; limits concurrent requests without blocking the event loop"),
    ("python_dev", "failure", 0.86, "AttributeError NoneType has no attribute means upstream function returned None instead of expected object — add assert result is not None or check return paths for missing explicit return statements"),
    ("python_dev", "code",    0.87, "JSON streaming generator: with open('large.json') as f: for line in f: obj = json.loads(line.strip()); if obj: yield obj; requires newline-delimited JSON (NDJSON) format"),
    ("python_dev", "code",    0.87, "multiprocessing Pool: with Pool(cpu_count()) as pool: results = pool.map(process_fn, items); use starmap for multiple args; avoid shared state — each worker gets its own memory space"),
    ("python_dev", "code",    0.88, "FastAPI middleware: @app.middleware('http') async def timing(request, call_next): t=time.time(); r=await call_next(request); r.headers['X-Duration']=str(time.time()-t); return r"),
    ("python_dev", "lesson",  0.83, "GIL prevents true parallel threads for CPU-bound work; use multiprocessing for CPU parallelism; threads are still useful for IO-bound tasks where threads spend most time waiting"),
    ("python_dev", "code",    0.86, "dataclass with validation: @dataclass class Config: port: int = 8000; def __post_init__(self): if not 1 <= self.port <= 65535: raise ValueError(f'port {self.port} out of range')"),
    ("python_dev", "failure", 0.84, "ImportError cannot import name from fastapi — check fastapi version with pip show fastapi; APIRouter was added in v0.63.0; update with pip install --upgrade fastapi"),
    ("python_dev", "code",    0.86, "watchdog file watcher: from watchdog.observers import Observer; from watchdog.events import FileSystemEventHandler; class H(FileSystemEventHandler): def on_created(self, e): process(e.src_path)"),
    ("python_dev", "lesson",  0.82, "Generator expressions use lazy evaluation and O(1) memory; list comprehensions evaluate eagerly and hold all results in memory — use generator when you iterate once or for large datasets"),
    # Blazor batch 2
    ("dotnet_dev", "code",    0.87, "Blazor file upload with progress: use InputFile component, read stream in chunks, report progress via EventCallback<int>; for large files use IBrowserFile.OpenReadStream(maxAllowedSize)"),
    ("dotnet_dev", "code",    0.85, "Blazor JWT auth: add services.AddAuthentication(JwtBearer); in Blazor Server inject HttpContext; use [Authorize] on pages; store token in protected localStorage via IJSRuntime"),
    ("dotnet_dev", "failure", 0.84, "StateHasChanged not updating UI: call must be on UI thread — use await InvokeAsync(StateHasChanged) from background threads or Timer callbacks; common bug in async event handlers"),
    ("dotnet_dev", "code",    0.86, "Blazor custom validation: implement IValidatableObject on model or create ValidationAttribute subclass; use <ValidationMessage For='() => model.Field' /> for field-level display"),
    ("dotnet_dev", "lesson",  0.82, "@inject Directive: @inject IMyService MyService in the component; service registered in Program.cs with builder.Services.AddScoped<IMyService, MyService>(); lifetime must match component lifetime"),
    ("dotnet_dev", "code",    0.84, "Blazor lazy loading: in .csproj add <BlazorWebAssemblyLazyLoad Include='MyAssembly.dll'/>; in Router use OnNavigateAsync to call LazyAssemblyLoader.LoadAssembliesAsync before routing"),
    ("dotnet_dev", "code",    0.85, "Blazor SignalR dashboard: inject IHubContext<DashboardHub>; push updates via hub.Clients.All.SendAsync('Update', data); client-side use HubConnection and handle 'Update' event then StateHasChanged"),
    ("dotnet_dev", "lesson",  0.81, "Blazor lifecycle: SetParametersAsync → OnInitialized(Async) → OnParametersSet(Async) → OnAfterRender(Async); OnInitialized runs once; OnParametersSet runs on every re-render with new params"),
    # AI/ML batch 2
    ("ai_ml", "lesson",  0.87, "BERT: encoder-only, bidirectional, pre-trained with masked language modeling and next sentence prediction, best for classification/NER/QA; GPT: decoder-only, autoregressive, best for text generation"),
    ("ai_ml", "lesson",  0.86, "Vanishing gradient: gradients shrink exponentially through many layers, early layers learn slowly; ResNets add skip connections (x + F(x)) so gradient flows directly, enabling 100+ layer networks"),
    ("ai_ml", "lesson",  0.83, "PyTorch: Pythonic, dynamic graph, strong research community, easier debugging; TensorFlow: more production tooling (TFServing, TFLite), stronger mobile/edge support — both excellent, PyTorch preferred in research"),
    ("ai_ml", "lesson",  0.84, "Batch norm normalizes across the batch dimension (varies with batch size, bad for small batches/RNNs); Layer norm normalizes across the feature dimension (independent of batch size, preferred in transformers)"),
    ("ai_ml", "lesson",  0.87, "Transfer learning: load pretrained model, freeze early layers, replace final head for your task, fine-tune on domain data; HuggingFace: model = AutoModel.from_pretrained('bert-base'); trainer = Trainer(model, args, dataset)"),
    ("ai_ml", "lesson",  0.86, "LangGraph StateGraph: define nodes as functions taking/returning state dict, add_edge for unconditional flow, add_conditional_edges for routing based on state; compile() returns a runnable graph"),
    ("ai_ml", "lesson",  0.84, "Quantization reduces model size/speed: INT8 (8-bit integers) is 4x smaller than FP32, good for inference; FP16 (half precision) preserves more precision, better for fine-tuning; use INT8 for production inference"),
    ("ai_ml", "lesson",  0.86, "RLHF: 1) supervised fine-tune on demonstrations, 2) train reward model on human preference rankings, 3) optimize policy with PPO using reward model as reward signal — aligns model with human preferences"),
    # Knowledge/Learning batch 2
    ("knowledge_learning", "lesson",  0.85, "REST uses fixed endpoints with HTTP verbs, returns full resource; GraphQL uses single endpoint, client specifies exact fields needed — GraphQL reduces over-fetching, REST is simpler and more cacheable"),
    ("knowledge_learning", "lesson",  0.84, "Actor model: actors are isolated units that communicate only via messages, no shared state; each actor has a mailbox and processes one message at a time — eliminates lock contention, scales naturally"),
    ("knowledge_learning", "lesson",  0.85, "Singleton: one instance per app; Observer: objects subscribe to events from a subject; Factory: creates objects without specifying concrete class — all three are GoF patterns for managing object creation/communication"),
    ("knowledge_learning", "lesson",  0.83, "Event sourcing: store all state changes as immutable events rather than current state; replay events to reconstruct state; enables audit log, time travel, and CQRS separation of read/write models"),
    ("knowledge_learning", "lesson",  0.82, "Vertical scaling: add more CPU/RAM to one machine (limited by hardware ceiling, simpler); horizontal scaling: add more machines (theoretically unlimited, requires distributed design, load balancing)"),
    ("knowledge_learning", "lesson",  0.83, "Immutability: once created, object state never changes; thread-safe by default (no race conditions), easier to reason about, enables structural sharing; React state, functional programming, and Kafka messages are immutable"),
    ("knowledge_learning", "lesson",  0.84, "Deadlock requires 4 conditions: mutual exclusion, hold-and-wait, no preemption, circular wait; prevention: use lock ordering (always acquire A before B), timeouts, or lock-free data structures"),
    # Terse batch 2
    ("terse", "lesson",  0.90, "SSH uses TCP port 22"),
    ("terse", "lesson",  0.90, "DNS stands for Domain Name System"),
    ("terse", "lesson",  0.90, "Redis default port is 6379"),
    ("terse", "lesson",  0.90, "HTTP 404 Not Found — the requested resource does not exist on the server"),
    ("terse", "lesson",  0.90, "2^16 = 65536"),
    ("terse", "lesson",  0.90, "FTP uses TCP port 21 (control) and port 20 (data)"),
    ("terse", "lesson",  0.90, "YAML stands for YAML Ain't Markup Language"),
]

assert len(SEED_MEMORIES) == 100, f"Expected 100 seed memories, got {len(SEED_MEMORIES)}"


# ── Helpers ───────────────────────────────────────────────────

def _load_results() -> dict:
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return {"prompts": {}, "started": datetime.now(timezone.utc).isoformat()}


def _save_results(results: dict):
    results["updated"] = datetime.now(timezone.utc).isoformat()
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)


def _infer_mem_type(prompt: str, response: str) -> str:
    low = response.lower()
    if "```" in response or "def " in response or "class " in response:
        return "code"
    if any(w in low for w in ["error", "exception", "failed", "traceback", "bug"]):
        return "failure"
    return "lesson"


def _infer_quality(prompt: str, response: str, passed_verify: bool) -> float:
    if not passed_verify:
        return 0.45
    words = response.split()
    quality = 0.70
    if len(words) > 150:
        quality += 0.08
    if len(words) > 300:
        quality += 0.05
    if "```" in response:
        quality += 0.07
    return round(min(0.92, quality), 2)


# ── Phase 1: Memory Seeding ───────────────────────────────────

def phase_seed_memory():
    print("\n" + "═"*60)
    print("  Phase 1: Memory Seeding (nomic-embed-text)")
    print("═"*60)

    import memory_core.db as memory_db

    saved = failed = 0
    for i, (agent, mem_type, quality, content) in enumerate(SEED_MEMORIES, 1):
        domain = agent.replace("_", " ")
        print(f"  [{i:03d}/{len(SEED_MEMORIES)}] [{mem_type:10}] q={quality:.2f}  {content[:55]}...", end=" ", flush=True)
        t0 = time.time()
        ok = memory_db.save(agent, mem_type, content, quality=quality,
                            metadata={"source": "auto_train", "domain": agent})
        dur = time.time() - t0
        if ok:
            saved += 1
            print(f"✓ ({dur:.1f}s)")
        else:
            failed += 1
            print(f"✗ failed")

    print(f"\n  Seeded: {saved}/{len(SEED_MEMORIES)}  Failed: {failed}")
    return saved


# ── Phase 2: Routing Evaluation ───────────────────────────────

def _build_state(prompt: str):
    from langchain_core.messages import HumanMessage
    return {
        "messages":       [HumanMessage(content=prompt)],
        "active_agent":   "",
        "task":           prompt,
        "result":         "",
        "next_agent":     "",
        "memory":         {},
        "force_agent":    "",
        "brain_decision": {},
        "reflect":        False,
        "reflect_type":   "general",
    }


def phase_routing_eval(resume: bool = False):
    print("\n" + "═"*60)
    print("  Phase 2: Routing Evaluation (phi4-mini)")
    print(f"  Prompts: {len(PROMPTS)}  |  ~{len(PROMPTS)*41//60} min estimated (100-prompt suite)")
    print("═"*60)

    from orchestration.coordinator import coordinator
    import memory_core.db as memory_db
    from infrastructure.executor import _verify

    results = _load_results()
    already_done = set(results["prompts"].keys()) if resume else set()
    if already_done:
        print(f"  Resuming: {len(already_done)} already completed, {len(PROMPTS)-len(already_done)} remaining")
    results.setdefault("prompts", {})

    domain_stats = {}  # domain → {correct, total, verified}

    for i, (pid, expected_agent, domain, prompt) in enumerate(PROMPTS, 1):
        prefix = f"  [{i:03d}/{len(PROMPTS)}] {pid}"

        if resume and pid in already_done:
            print(f"{prefix}  (skip — done)")
            # Re-count for stats
            r = results["prompts"][pid]
            ds = domain_stats.setdefault(domain, {"correct": 0, "total": 0, "verified": 0})
            ds["total"] += 1
            if r.get("routing_correct"):
                ds["correct"] += 1
            if r.get("verify_passed"):
                ds["verified"] += 1
            continue

        print(f"{prefix}  [{expected_agent}]  {prompt[:50]}...", flush=True)
        t0 = time.time()

        try:
            state  = _build_state(prompt)
            result = coordinator.invoke(state)
            dur    = round(time.time() - t0, 1)

            actual_agent = result.get("active_agent", "unknown")
            response     = ""
            if result.get("messages"):
                response = result["messages"][-1].content
            elif result.get("result"):
                response = result["result"]

            brain_dec      = result.get("brain_decision", {}) or state.get("brain_decision", {})
            confidence     = brain_dec.get("confidence", 0.0) if isinstance(brain_dec, dict) else 0.0
            regret         = brain_dec.get("regret", 0.0)     if isinstance(brain_dec, dict) else 0.0

            routing_correct = (actual_agent == expected_agent)
            step_dict       = {"step_id": pid, "agent": actual_agent, "prompt": prompt}
            verify_passed, verify_reason = _verify(step_dict, response)

            mem_type = _infer_mem_type(prompt, response)
            quality  = _infer_quality(prompt, response, verify_passed)

            # Save to memory
            memory_db.save(
                agent_name=actual_agent,
                mem_type=mem_type,
                content=f"Q: {prompt}\nA: {response[:400]}",
                quality=quality,
                metadata={
                    "source":     "auto_train",
                    "domain":     domain,
                    "prompt_id":  pid,
                    "confidence": confidence,
                    "regret":     regret,
                },
            )

            entry = {
                "prompt":           prompt,
                "expected_agent":   expected_agent,
                "actual_agent":     actual_agent,
                "routing_correct":  routing_correct,
                "confidence":       confidence,
                "regret":           regret,
                "verify_passed":    verify_passed,
                "verify_reason":    verify_reason,
                "quality":          quality,
                "mem_type":         mem_type,
                "duration_s":       dur,
                "response_words":   len(response.split()),
                "domain":           domain,
            }
            results["prompts"][pid] = entry
            _save_results(results)

            mark  = "✓" if routing_correct else "✗"
            vmark = "✓" if verify_passed   else "✗"
            print(
                f"    → [{actual_agent}] {mark}route  "
                f"verify={vmark}  conf={confidence:.2f}  "
                f"q={quality:.2f}  {dur}s"
            )

            # Update domain stats
            ds = domain_stats.setdefault(domain, {"correct": 0, "total": 0, "verified": 0})
            ds["total"] += 1
            if routing_correct:
                ds["correct"] += 1
            if verify_passed:
                ds["verified"] += 1

        except KeyboardInterrupt:
            print("\n  Interrupted — results saved. Resume with --resume flag.")
            _save_results(results)
            return results, domain_stats

        except Exception as e:
            dur = round(time.time() - t0, 1)
            print(f"    ERROR ({dur}s): {e}")
            results["prompts"][pid] = {
                "prompt":         prompt,
                "expected_agent": expected_agent,
                "actual_agent":   "error",
                "routing_correct": False,
                "verify_passed":  False,
                "error":          str(e)[:200],
                "duration_s":     dur,
                "domain":         domain,
            }
            _save_results(results)

    return results, domain_stats


# ── Report ────────────────────────────────────────────────────

def print_report(results: dict, domain_stats: dict = None):
    entries = list(results.get("prompts", {}).values())
    if not entries:
        print("No results to report.")
        return

    n          = len(entries)
    correct    = sum(1 for e in entries if e.get("routing_correct"))
    verified   = sum(1 for e in entries if e.get("verify_passed"))
    avg_conf   = sum(e.get("confidence", 0) for e in entries) / n
    avg_q      = sum(e.get("quality", 0)    for e in entries) / n
    avg_dur    = sum(e.get("duration_s", 0) for e in entries) / n
    errors     = sum(1 for e in entries if e.get("error"))
    total_dur  = sum(e.get("duration_s", 0) for e in entries)

    print("\n" + "═"*60)
    print("  Auto-Training Results Report")
    print("═"*60)
    print(f"  Prompts completed:   {n}/{len(PROMPTS)}")
    print(f"  Routing accuracy:    {correct}/{n}  ({100*correct/n:.1f}%)")
    print(f"  Verification pass:   {verified}/{n}  ({100*verified/n:.1f}%)")
    print(f"  Avg confidence:      {avg_conf:.3f}")
    print(f"  Avg quality saved:   {avg_q:.3f}")
    print(f"  Avg inference time:  {avg_dur:.1f}s")
    print(f"  Total runtime:       {total_dur/60:.1f} min")
    print(f"  Errors:              {errors}")

    if not domain_stats:
        # Rebuild from entries
        domain_stats = {}
        for e in entries:
            d = e.get("domain", "?")
            ds = domain_stats.setdefault(d, {"correct": 0, "total": 0, "verified": 0})
            ds["total"] += 1
            if e.get("routing_correct"):
                ds["correct"] += 1
            if e.get("verify_passed"):
                ds["verified"] += 1

    print(f"\n  Routing accuracy by domain:")
    for domain in ["networking", "python", "dotnet", "ai_ml", "knowledge", "terse"]:
        ds = domain_stats.get(domain, {"correct": 0, "total": 1, "verified": 0})
        t  = ds["total"]
        c  = ds["correct"]
        v  = ds["verified"]
        bar = "█" * c + "░" * (t - c)
        pct = 100 * c / t if t else 0
        print(f"    {domain:12}  {bar}  {c}/{t}  ({pct:.0f}% routing  {v}/{t} verified)")

    # Routing mistakes
    mistakes = [(pid, e) for pid, e in results["prompts"].items() if not e.get("routing_correct") and not e.get("error")]
    if mistakes:
        print(f"\n  Routing mistakes ({len(mistakes)}):")
        for pid, e in mistakes:
            print(f"    {pid}  expected=[{e['expected_agent']}]  got=[{e['actual_agent']}]  "
                  f"conf={e.get('confidence', 0):.2f}")
            print(f"      \"{e['prompt'][:65]}\"")

    # Verify failures
    vfails = [(pid, e) for pid, e in results["prompts"].items()
              if not e.get("verify_passed") and not e.get("error") and e.get("actual_agent") != "error"]
    if vfails:
        print(f"\n  Verification failures ({len(vfails)}):")
        for pid, e in vfails:
            print(f"    {pid}  [{e.get('actual_agent')}]  reason: {e.get('verify_reason','?')}")
            print(f"      \"{e['prompt'][:65]}\"")

    print("═"*60)


# ── Main ─────────────────────────────────────────────────────

def main():
    args       = sys.argv[1:]
    seed_only  = "--seed-only"  in args
    eval_only  = "--eval-only"  in args
    resume     = "--resume"     in args
    report_only = "--report"    in args

    if report_only:
        r = _load_results()
        print_report(r)
        return

    run_seed = not eval_only
    run_eval = not seed_only

    if run_seed:
        phase_seed_memory()

    if run_eval:
        results, domain_stats = phase_routing_eval(resume=resume)
        print_report(results, domain_stats)
    elif run_seed:
        print("\n  Seeding complete. Run with --eval-only to run routing evaluation.")

    print(f"\n  Results saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
