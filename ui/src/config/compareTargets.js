// Shared cross-model comparison targets — used by both "Run Across Models"
// (PromptEditorTab) and "Consensus" (ConsensusTab) so the two features can't
// silently drift apart. Unconfigured providers just report their own error in
// the result slot (see routes/debug_prompt.py::_resolve_models) — that's the
// point of a debugger, not a bug to hide.
export const COMPARE_TARGETS = [
  { id: "ollama",    label: "Local · phi4-mini",  cfg: { provider: "ollama",    model: "phi4-mini:latest" } },
  { id: "anthropic", label: "Claude Sonnet 4.6",  cfg: { provider: "anthropic", model: "claude-sonnet-4-6" } },
  { id: "openai",    label: "GPT-4o-mini",        cfg: { provider: "openai",    model: "gpt-4o-mini", base_url: "https://api.openai.com/v1" } },
];
