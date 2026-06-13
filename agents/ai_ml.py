from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
import subprocess, sys
from memory_core.context import get_memory_context, save_to_memory
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.state import AgentState
from models.llm import llm
from core.context_tools import trim_messages

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

# ── Agent Node ────────────────────────────────────────────────
def ai_ml_agent_node(state: AgentState):
    """Main AI & ML agent node."""
    task = state.get("task", "")

    # -- Memory: search before responding --
    _mem_ctx = get_memory_context(task, "ai_ml")
    from core.user_profile import get_profile_context
    _effective_prompt = AI_ML_SYSTEM_PROMPT.format(user_profile=get_profile_context())
    if _mem_ctx:
        _effective_prompt += "\n\n" + _mem_ctx
    # ----------------------------------------

    tool_context = ""

    if any(w in task.lower() for w in ["installed", "packages", "framework", "torch", "tensorflow"]):
        tool_context += f"\n[ML PACKAGES]\n{check_ml_packages()}"

    if any(w in task.lower() for w in ["gpu", "cuda", "hardware", "device", "accelerat"]):
        tool_context += f"\n[GPU STATUS]\n{check_gpu()}"

    if any(w in task.lower() for w in ["which model", "recommend", "suggest", "best model", "what model"]):
        tool_context += f"\n[MODEL RECOMMENDATIONS]\n{suggest_model_for_task(task)}"

    messages = [
        SystemMessage(content=_effective_prompt),
        *trim_messages(state["messages"], max_messages=10),
    ]

    if tool_context:
        messages.append(HumanMessage(
            content=f"System tool results:\n{tool_context}\n\nUse these in your response."
        ))

    response = llm.invoke(messages)

    # -- Memory: save after responding --
    save_to_memory("ai_ml", "chat", response.content,
                   {"task": task[:120] if task else ""})
    # ------------------------------------


    return {
        "messages":     [response],
        "active_agent": "ai_ml",
        "result":       response.content,
    }

# ── Build Subgraph ────────────────────────────────────────────
def build_ai_ml_agent():
    graph = StateGraph(AgentState)
    graph.add_node("ai_ml_agent", ai_ml_agent_node)
    graph.add_edge(START, "ai_ml_agent")
    graph.add_edge("ai_ml_agent", END)
    return graph.compile()

ai_ml_agent = build_ai_ml_agent()

# ── Standalone Test ───────────────────────────────────────────
if __name__ == "__main__":
    print("🤖 Testing AI & ML Agent...\n")
    result = ai_ml_agent.invoke({
        "messages": [{"role": "user", "content": "What ML packages do I have installed, and what model would you recommend for building a text classification system on my hardware?"}],
        "active_agent": "",
        "task":         "check installed ml packages and recommend model for text classification",
        "result":       "",
        "next_agent":   "",
        "memory":       {},
    })
    print("── AI & ML AGENT RESPONSE ──")
    print(result["messages"][-1].content)
