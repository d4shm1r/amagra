"""
Central LLM accessor.

All agent and coordinator code does: from models.llm import llm
That import path is preserved here — llm is still a ChatOllama-compatible
object. Internally it is the chat_model attribute of an OllamaProvider, so
the provider abstraction is active from the first request.

To swap the inference backend, replace the provider below or set env vars:
  OLLAMA_MODEL      — model name (default: phi4-mini:latest)
  OLLAMA_BASE_URL   — Ollama server (default: http://localhost:11434)
"""

from providers.ollama import OllamaProvider

_provider = OllamaProvider(
    temperature=0.7,
    num_ctx=2048,
    num_thread=6,
    num_predict=256,
)

# llm is the LangChain ChatOllama instance — existing agent code imports this
# directly and calls llm.invoke(messages). No agent changes required.
llm = _provider.chat_model
