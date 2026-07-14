import subprocess
import sys

from agents.runner import Agent
from agents.spec import AgentSpec, Probe

# ── System Prompt ─────────────────────────────────────────────
AI_ML_SYSTEM_PROMPT = """
{user_profile}
You are an expert AI & Machine Learning agent.
Your expertise covers:
- Machine learning fundamentals and algorithms
- Deep learning with PyTorch and TensorFlow/Keras
- LangChain and LangGraph for agentic AI systems
- Local LLM deployment with Ollama
- Hugging Face transformers and datasets
- RAG (Retrieval Augmented Generation) pipelines
- Model evaluation, metrics, and debugging
- Feature engineering and data preprocessing
- Scikit-learn for classical ML
- Prompt engineering and fine-tuning strategies

When explaining concepts:
- Start with intuition before math
- Give working code examples
- Compare approaches (when to use what)
- Always mention computational cost/requirements

When writing ML code always include:
- Data shape comments (# shape: batch x features)
- Training loop with loss logging
- Validation split
- Model save/load pattern"""

# ── Tools ─────────────────────────────────────────────────────
def check_ml_packages() -> str:
    """Check which ML frameworks are installed."""
    packages = [
        "torch", "tensorflow", "sklearn",
        "transformers", "datasets", "numpy",
        "pandas", "matplotlib", "langchain",
        "langgraph", "chromadb", "sentence_transformers"
    ]
    results = []
    for pkg in packages:
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"import {pkg}; print({pkg}.__version__)"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                results.append(f"  ✅ {pkg:<25} {version}")
            else:
                results.append(f"  ❌ {pkg:<25} not installed")
        except Exception:
            results.append(f"  ❌ {pkg:<25} not installed")
    return "ML Framework Status:\n" + "\n".join(results)

def check_gpu() -> str:
    """Check GPU availability for ML workloads."""
    try:
        # Check NVIDIA GPU
        nvidia = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if nvidia.returncode == 0:
            return f"✅ NVIDIA GPU detected:\n{nvidia.stdout}"

        # Check via PyTorch
        torch_check = subprocess.run(
            [sys.executable, "-c",
             "import torch; print('CUDA:', torch.cuda.is_available()); "
             "print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"],
            capture_output=True, text=True, timeout=5
        )
        if torch_check.returncode == 0:
            return torch_check.stdout

        return "⚠️ No GPU detected — running on CPU (12 cores available)"
    except Exception:
        return "⚠️ GPU check unavailable — assuming CPU only"

def suggest_model_for_task(task_description: str) -> str:
    """Suggest appropriate model size given available hardware."""
    # Based on user's 15GB RAM, no dedicated GPU confirmed
    suggestions = {
        "text_generation":   "phi4-mini via Ollama (already installed ✅)",
        "embeddings":        "nomic-embed-text via Ollama (lightweight, fast)",
        "classification":    "scikit-learn or distilbert (CPU-friendly)",
        "image_recognition": "mobilenet_v3 (low RAM) or resnet50",
        "code_generation":   "codellama:7b via Ollama",
        "summarization":     "phi4-mini via Ollama (already installed ✅)",
    }
    result = "Hardware profile: 15GB RAM, 12 CPU cores, no dedicated GPU\n\n"
    result += "Recommended models for your hardware:\n"
    for task, model in suggestions.items():
        result += f"  • {task:<20} → {model}\n"
    return result

# ── Spec ──────────────────────────────────────────────────────
SPEC = AgentSpec(
    name="ai_ml",
    prompt=AI_ML_SYSTEM_PROMPT,
    probe_intro="System tool results:",
    probes=(
        Probe(
            triggers=("installed", "packages", "framework", "torch", "tensorflow"),
            label="ML PACKAGES",
            run=lambda _task: check_ml_packages(),
        ),
        Probe(
            triggers=("gpu", "cuda", "hardware", "device", "accelerat"),
            label="GPU STATUS",
            run=lambda _task: check_gpu(),
        ),
        Probe(
            triggers=("which model", "recommend", "suggest", "best model", "what model"),
            label="MODEL RECOMMENDATIONS",
            run=suggest_model_for_task,
        ),
    ),
)

ai_ml_agent = Agent(SPEC)
