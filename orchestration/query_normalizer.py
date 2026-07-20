"""
Pre-routing query normalization.

Converts raw query text into a structured QuerySignal before any routing
decision is made. Separates "what does the query contain" from "which agent
handles it" — routing becomes a table lookup on the signal rather than a
chain of heuristics.

No LLM calls. Pure function. O(n_keywords) per call.
"""

import math
import re
from dataclasses import dataclass


@dataclass
class QuerySignal:
    domain:       str    # "networking"|"python"|"dotnet"|"ai_ml"|"web"|"devops"|"data"|"writing"|"general"
    domain_conf:  float  # 0.0–1.0; >0.3 = confident enough for domain routing
    answer_shape: str    # "factual" | "explanation" | "code" | "debug" | "procedural" | "comparison" | "compute"
    verbosity:    str    # "terse" | "normal" | "detailed"
    action:       str    # carried from _detect_action() in core_brain


# Domain keyword sets — substring-matched against lowercased query.
# Confidence: c(hits) = 1 - exp(-0.40 * hits). Single hit → 0.33 (above routing
# threshold 0.30). Smooth saturation — no hard ceiling at multi-keyword queries.
# Cover both technical jargon and common phrasings to minimize misses.
_DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "networking": {
        "network", "wifi", "wi-fi", "router", "dns", "dhcp", "ssh", "ip address",
        "ping", "firewall", "vpn", "ethernet", "subnet", "vlan", "tcp", "udp",
        "bgp", "nginx", "ssl", "https", "http", "proxy", "wireguard", "packet",
        "bandwidth", "latency", "nat", "iptables", "firewalld", "certbot",
        "let's encrypt", "letsencrypt", "load balancer", "reverse proxy",
        "socket", "interface", "netstat", "traceroute", "autonomous system",
        "ospf", "switchport", "packet loss", "webrtc", "coturn", "turn server",
    },
    "python": {
        "python", "flask", "fastapi", "asyncio", "pytest", "pip", "django",
        "pydantic", "decorator", "numpy", "requests", "recursion",
        "async/await", "context manager", "dataclass", "namedtuple",
        "generator", "iterator", "coroutine", "type hint", "venv", "pypi",
        "__str__", "__repr__", "dunder", "lambda", "list comprehension",
        "dict comprehension", "f-string", "typeerror", "nameerror",
        "attributeerror", "importerror", "recursiondepth",
        "maximum recursion", "argparse", "csv",
        # pandas removed — data_analyst handles pandas/dataframe queries
    },
    "dotnet": {
        "blazor", "razor", "webassembly", "wasm", "dotnet", "csharp", "c#",
        "signalr", "nuget", "maui", ".net", "asp.net", "cascading parameter",
        "statehaschanged", "oninitialized", "editform", "validationmessage",
        "ijsruntime", "javascript interop", "blazor server", "blazor wasm",
    },
    "web": {
        "react", "vue", "angular", "svelte", "nextjs", "nuxt", "gatsby",
        "css", "html", "jsx", "tsx", "tailwind", "sass", "scss",
        "flexbox", "css grid", "responsive", "media query",
        "webpack", "vite", "rollup", "esbuild",
        "useeffect", "usestate", "usecontext", "usereducer", "useref",
        "react hook", "props", "state management",
        "dom", "event listener", "event bubbling", "event capturing",
        "web component", "service worker", "pwa", "spa",
        "frontend", "browser api", "localstorage", "sessionstorage",
        "fetch api", "axios", "lazy load", "code split",
    },
    "devops": {
        "docker", "container", "dockerfile", "docker compose",
        "kubernetes", "kubectl", "k8s", "helm", "pod", "cluster",
        "namespace", "ingress", "deployment", "statefulset", "daemonset",
        "terraform", "ansible", "infrastructure as code",
        "github actions", "gitlab ci", "jenkins", "circleci",
        "ci/cd", "pipeline", "build pipeline", "deploy",
        "prometheus", "grafana", "alertmanager", "loki",
        "crashloopbackoff", "oomkilled", "resource limit", "resource request",
        "image registry", "ghcr", "ecr", "docker hub",
        "service mesh", "istio", "envoy", "sidecar",
    },
    "data": {
        "pandas", "dataframe", "groupby", "pivot", "pivot_table",
        "merge", "concat", "join dataframe", "read_csv", "to_csv",
        "sql", "select from", "inner join", "left join", "outer join",
        "window function", "aggregate", "aggregation",
        "matplotlib", "seaborn", "plotly", "bokeh", "visualization",
        "data analysis", "data cleaning", "exploratory", "eda",
        "parquet", "feather", "jupyter", "notebook",
        "scipy", "statsmodels", "outlier", "rolling average",
        "time series", "resampling", "iloc", "loc",
    },
    "writing": {
        "blog post", "article", "write a post", "write an article",
        "rewrite", "draft a", "changelog", "release notes",
        "documentation", "technical writing", "copywriting",
        "linkedin post", "announcement", "press release",
        "professional email", "tone of voice", "audience",
        "edit this", "proofread", "paragraph", "readme section",
    },
    "ai_ml": {
        "neural network", "pytorch", "tensorflow", "machine learning", "deep learning",
        "llm", "embedding", "transformer", "dataset", "gradient", "huggingface",
        "langchain", "langgraph", "supervised", "unsupervised", "reinforcement",
        "classifier", "regression", "overfitting", "underfitting", "loss function",
        "backpropagation", "attention mechanism", "rag", "retrieval augmented",
        "fine-tun", "prompt engineering", "inference", "word embedding",
        "precision", "recall", "f1 score", "roc curve", "confusion matrix",
        "learning rate", "epoch", "batch size", "dropout", "weight decay",
        "binary classifier", "train a model", "model evaluation",
        # Model names
        "bert", "gpt", "gpt-4", "gpt-3", "chatgpt", "llama", "mistral",
        "gemini", "claude model", "stable diffusion", "whisper", "resnet",
        "vit", "vision transformer", "encoder", "decoder", "autoencoder",
        "tokenizer", "tokenization", "pre-train", "zero-shot", "few-shot",
        "chain of thought", "vector store", "vector database", "semantic search",
        # Agentic / multi-agent system queries
        "multi-agent", "agent-based", "agent simulation", "simulate agents",
        "autonomous agent", "llm agent", "agentic", "tool-using agent",
        "simulate four", "simulate multiple", "ai agent", "agent framework",
        "agent orchestrat", "agent workflow", "agent system",
        # Broader ML/AI operations language
        "ai operations", "mlops", "model deploy", "model serving",
        "ai pipeline", "inference pipeline", "ai product", "ai system",
    },
}

# Maps domain names (as used in QuerySignal) to agent identifiers.
DOMAIN_TO_AGENT: dict[str, str] = {
    "networking": "it_networking",
    "python":     "python_dev",
    "dotnet":     "dotnet_dev",
    "ai_ml":      "ai_ml",
    "web":        "web_dev",
    "devops":     "devops",
    "data":       "data_analyst",
    "writing":    "writer",
    "general":    "knowledge_learning",
}


def _kw_match(kw: str, q: str) -> bool:
    """
    Short keywords (≤4 chars) require word boundaries to prevent substring
    collisions: "nat" in "paginated", "rag" in "storage", "tcp" in "protcap", etc.
    Longer keywords use plain substring matching for speed.
    """
    if len(kw) <= 4:
        return bool(re.search(r'\b' + re.escape(kw) + r'\b', q))
    return kw in q


def detect_domain(query: str) -> tuple[str, float]:
    """
    Returns (domain, confidence). confidence > 0.3 is routing-worthy.
    Best domain wins; ties broken by hit count (longer keywords preferred as
    they're more specific and less likely to false-positive).
    """
    q = query.lower()
    best_domain = "general"
    best_conf   = 0.0
    best_max_kw = 0     # tie-break: prefer domain with the longest matched keyword
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        matched = [kw for kw in keywords if _kw_match(kw, q)]
        hits = len(matched)
        if hits > 0:
            conf       = 1.0 - math.exp(-0.40 * hits)
            max_kw_len = max(len(kw) for kw in matched)
            if conf > best_conf or (conf == best_conf and max_kw_len > best_max_kw):
                best_conf   = conf
                best_domain = domain
                best_max_kw = max_kw_len
    return best_domain, best_conf


# Exact-computation / enumeration / proof: the caller wants a *computed result*
# — a number, a sequence, a proof — not a prose description of the method. This
# is the shape the router previously lacked, so "Compute the first 12 terms …"
# was routed identically to "Explain X" and the model described the algorithm
# instead of running it (#184). Imperative computation verbs and enumeration /
# proof patterns only; bare exactness words ("exactly") are deliberately NOT
# sufficient, so "explain exactly how X works" stays an explanation.
_COMPUTE_CUE = re.compile(
    r"\b(compute|calculate|enumerate|tabulate|"
    r"factorial|factori[sz]e|"
    r"evaluate the (sum|product|expression|series|integral|value)|"
    r"first \d+ (terms?|primes?|numbers?|digits?|powers?|values?|multiples?|"
    r"fibonacci)|"
    r"list the first \d|"
    r"the \d+(st|nd|rd|th) (term|prime|digit|fibonacci|value|number)|"
    r"prove that|show that|derive the|"
    r"decimal (expansion|places)|to \d+ (decimal )?places)\b",
    re.IGNORECASE,
)


def detect_answer_shape(query: str) -> str:
    """
    Classify the expected shape of the response.

    factual     — single concrete fact; answer fits in a word or number
    code        — caller wants executable code produced
    debug       — caller has a broken state and wants a fix
    procedural  — step-by-step how-to or setup guide
    comparison  — contrast between two or more things
    compute     — caller wants an exact computed result / enumeration / proof
    explanation — default; prose description of a concept
    """
    q = query.lower()

    # Factual: short queries expecting a single numeric/term answer
    if len(query.split()) <= 10:
        if re.search(
            r"\b(what port|what is the (default\s+)?port|"
            r"what does .{1,30} stand for|"
            r"what does .{1,20} mean\??$|"
            r"what is \d[\d\s]*to the power|"
            r"what is \d[\d\s]*\^|"
            r"how many (hosts?|bits?|bytes?|ips?)\b)",
            q
        ):
            return "factual"

    # Code: explicit build intent + code artifact type
    if re.search(r"\b(write|implement|create|build|generate)\b", q):
        if re.search(
            r"\b(function|class|script|endpoint|component|module|program|snippet|"
            r"method|interface|controller|middleware|decorator|test)\b",
            q
        ):
            return "code"

    # Debug: error/broken state — also catches CamelCase exception names
    if re.search(
        r"\b(traceback|debug|fix|not working|fails?|crash|broken|"
        r"wrong output|why is .{1,40} not|how to fix)\b",
        q
    ) or re.search(r"(error|exception)\b", q):
        return "debug"

    # Procedural: how-to / setup guides
    if re.search(
        r"\b(how do i|how to|set up|configure|install|deploy|enable|disable|"
        r"add .{1,20} to|remove .{1,20} from|migrate|upgrade|create a)\b",
        q
    ):
        return "procedural"

    # Comparison
    if re.search(
        r"\b(difference between|differ|vs\.?|versus|compare|better than|pros and cons|"
        r"when (should|to) use|which is (better|faster|preferred))\b",
        q
    ):
        return "comparison"

    # Compute: exact computation / enumeration / proof. Placed last so every
    # other shape wins first — this only ever splits what would have been an
    # "explanation" into "explanation" vs "compute", never touching factual /
    # code / debug / procedural / comparison. "How do I compute …" is caught by
    # the procedural check above and stays procedural, as intended.
    if _COMPUTE_CUE.search(q):
        return "compute"

    return "explanation"


def detect_verbosity(query: str) -> str:
    """
    Token-count proxy for expected response length.

    terse    — ≤6 tokens: user wants a short answer
    normal   — 9–24 tokens
    detailed — ≥25 tokens: complex, multi-part query
    """
    n = len(query.split())
    if n <= 6:
        return "terse"
    if n >= 25:
        return "detailed"
    return "normal"


def normalize(query: str, action: str = "unknown") -> QuerySignal:
    """
    Convert raw query text into a structured routing signal.

    Pure function — no side effects, no LLM calls. Runs in < 1ms.
    Called by core_brain.think() before any agent selection.
    """
    domain, domain_conf = detect_domain(query)
    answer_shape        = detect_answer_shape(query)
    verbosity           = detect_verbosity(query)
    return QuerySignal(
        domain=domain,
        domain_conf=domain_conf,
        answer_shape=answer_shape,
        verbosity=verbosity,
        action=action,
    )


# ── STANDALONE TEST ──────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 65)
    print("query_normalizer.py — signal detection tests")
    print("=" * 65)

    cases = [
        # (query, exp_domain, exp_shape, exp_verbosity)
        ("What port does HTTPS use?",                                "networking", "factual",     "terse"),
        ("What does HTTP status 429 mean?",                          "networking", "factual",     "terse"),
        ("What is 2 to the power of 10?",                           "general",    "factual",     "normal"),
        ("What does SQL stand for?",                                 "general",    "factual",     "terse"),
        ("What is the default port for PostgreSQL?",                 "general",    "factual",     "normal"),
        # "difference between" → comparison (not explanation); 7 tokens → normal
        ("Explain the difference between TCP and UDP",               "networking", "comparison",  "normal"),
        ("What is BGP and how does autonomous system routing work?", "networking", "explanation", "normal"),
        # RecursionError has "error\b" suffix → debug; 8 tokens → normal
        ("I am getting RecursionError: maximum recursion depth exceeded", "python", "debug",     "normal"),
        ("How do I correctly use async/await in Python for concurrent", "python",  "procedural", "normal"),
        ("How do dataclasses differ from regular classes and namedtuples", "python", "comparison", "normal"),
        # Truncated prompts — actual auto_train prompts are longer; verbosity matches truncated form
        ("What is the difference between supervised, unsupervised",  "ai_ml",     "comparison",  "normal"),
        ("How do I evaluate a binary classifier beyond accuracy",    "ai_ml",     "procedural",  "normal"),
        ("How does Retrieval Augmented Generation RAG work",        "ai_ml",     "explanation", "normal"),
        ("What is the difference between fine-tuning a model",      "ai_ml",     "comparison",  "normal"),
        ("Create a Blazor component that displays a sortable table", "blazor",    "code",        "normal"),
        ("Write a FastAPI endpoint that accepts a JSON body",        "python",    "code",        "normal"),
        ("What is a transformer model",                              "ai_ml",     "explanation", "terse"),
        ("Explain how DNS works",                                    "networking","explanation", "terse"),
        # ── compute shape (#184): exact computation / enumeration / proof ──
        ("Compute the first 12 terms of the sequence a1=1, a2=2, a_n=a_{n-1}+a_{n-2}. Do not guess.",
                                                                     "general",   "compute",     "normal"),
        ("Enumerate the first 10 prime numbers. Do not guess.",      "general",   "compute",     "normal"),
        ("List the first 8 powers of 2 exactly.",                    "general",   "compute",     "normal"),
        ("Compute 17 factorial exactly. Do not guess.",              "general",   "compute",     "normal"),
        ("Prove that the sum of the first n odd numbers equals n squared.",
                                                                     "general",   "compute",     "normal"),
        # Guard: "how do I compute …" is a method question → procedural, NOT compute
        ("How do I compute a rolling average in pandas",             "data",      "procedural",  "normal"),
        # Guard: bare "exactly" in prose stays explanation
        ("Explain exactly how DNS resolution works",                 "networking","explanation", "terse"),
    ]

    passed = total = 0
    for query, exp_domain, exp_shape, exp_verb in cases:
        sig  = normalize(query)
        ok_d = sig.domain       == exp_domain
        ok_s = sig.answer_shape == exp_shape
        ok_v = sig.verbosity    == exp_verb
        all_ok = ok_d and ok_s and ok_v

        label = (query[:55] + "…") if len(query) > 55 else query
        print(f"\n  {'✓' if all_ok else '✗'} '{label}'")
        if not ok_d: print(f"      domain:  got={sig.domain!r:<15}  expected={exp_domain!r}  conf={sig.domain_conf}")
        if not ok_s: print(f"      shape:   got={sig.answer_shape!r:<15}  expected={exp_shape!r}")
        if not ok_v: print(f"      verbose: got={sig.verbosity!r:<10}  expected={exp_verb!r}")

        total  += 1
        passed += int(all_ok)

    print(f"\n{'='*65}")
    print(f"  Result: {passed}/{total} passed {'✅' if passed == total else '⚠'}")
