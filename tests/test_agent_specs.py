"""
Guards the agent layer: one spec per registered agent, one runner for all of
them (agents/runner.py).

This layer had NO tests before the specs landed. The reason is visible in
conftest.py, which MagicMocks langchain_core.messages for the whole suite —
a mocked SystemMessage has no readable .content, so nothing could assert on
what an agent actually sent the model, and nobody tried.

So these tests aim at the runner's *pure* stage instead: _prompt_for and
_probe_results both return plain strings and never touch a message class. That
is where the behaviour lives, and it is exactly where knowledge_learning had
been quietly shipping a literal "{user_profile}" to the model on every turn it
recalled a memory.
"""
import pytest

import agents.runner as runner
from agents.registry import AGENT_IDS
from agents.runner import Agent, _compose, _probe_results, _prompt_for
from agents.spec import AgentSpec, Probe


def _all_agents():
    import agents.python_dev, agents.dotnet_dev, agents.it_networking, agents.ai_ml
    import agents.web_dev, agents.devops, agents.data_analyst, agents.writer
    import agents.knowledge_learning, agents.terse
    return {
        "python_dev":         agents.python_dev.python_agent,
        "dotnet_dev":         agents.dotnet_dev.dotnet_agent,
        "it_networking":      agents.it_networking.it_agent,
        "ai_ml":              agents.ai_ml.ai_ml_agent,
        "web_dev":            agents.web_dev.web_dev_agent,
        "devops":             agents.devops.devops_agent,
        "data_analyst":       agents.data_analyst.data_analyst_agent,
        "writer":             agents.writer.writer_agent,
        "knowledge_learning": agents.knowledge_learning.knowledge_agent,
        "terse":              agents.terse.terse_agent,
    }


@pytest.fixture
def context(monkeypatch):
    """Stub the two live inputs to prompt building. These names are patched in
    the runner's namespace because that is where `from ... import` bound them."""
    monkeypatch.setattr(runner, "get_profile_context", lambda task: "PROFILE")
    monkeypatch.setattr(runner, "get_memory_context", lambda task, agent: "RECALLED")


def test_every_registered_agent_has_a_spec_on_the_shared_runner():
    built = _all_agents()
    assert set(built) == AGENT_IDS
    for name, agent in built.items():
        assert isinstance(agent, Agent)
        assert agent.spec.name == name, f"{name} spec disagrees with its export"


# ── the regression that motivated the collapse ──
@pytest.mark.parametrize("name", sorted(AGENT_IDS - {"terse"}))
def test_profile_survives_recalled_memory(name, context):
    """Recalling a memory must not cost an agent its user profile. The old
    knowledge_learning node rebuilt the prompt from the raw template on exactly
    this path and sent "{user_profile}" to the model verbatim."""
    spec = _all_agents()[name].spec
    prompt = _prompt_for(spec, "explain dns to me")

    assert "{user_profile}" not in prompt, f"{name} leaked the profile placeholder"
    assert "PROFILE" in prompt, f"{name} dropped the user profile"
    assert "RECALLED" in prompt, f"{name} dropped the recalled memory"


def test_memory_is_appended_not_substituted(context):
    """The persona must survive recall, not be replaced by it."""
    spec = AgentSpec(name="writer", prompt="{user_profile}\nPERSONA")
    assert _prompt_for(spec, "t") == "PROFILE\nPERSONA\n\nRECALLED"


# ── probes ──
def test_probe_fires_only_on_its_triggers():
    seen = []
    spec = AgentSpec(
        name="python_dev", prompt="p",
        probes=(Probe(triggers=("gpu",), label="GPU",
                      run=lambda t: seen.append(t) or "GPU-OUT"),),
    )
    assert _probe_results(spec, "write a loop") == ""
    assert not seen, "probe ran on a task that never mentions its trigger"

    assert _probe_results(spec, "check the GPU now") == "\n[GPU]\nGPU-OUT"
    assert seen == ["check the GPU now"], "a probe receives the raw task text"


def test_empty_probe_result_contributes_no_block():
    """A probe may match a keyword and still have nothing to say. knowledge's
    roadmap depends on this: "give me a roadmap" with no recognized subject must
    not emit a bare [ROADMAP] header."""
    spec = AgentSpec(
        name="writer", prompt="p",
        probes=(Probe(triggers=("roadmap",), label="ROADMAP", run=lambda t: ""),),
    )
    assert _probe_results(spec, "give me a roadmap") == ""


def test_probes_concatenate_in_spec_order():
    """dotnet_dev pairs two probes on one trigger set and depends on the order."""
    spec = AgentSpec(
        name="dotnet_dev", prompt="p",
        probes=(
            Probe(triggers=("sdk",), label=".NET SDK", run=lambda t: "A"),
            Probe(triggers=("sdk",), label=".NET RUNTIMES", run=lambda t: "B"),
        ),
    )
    assert _probe_results(spec, "which sdk") == "\n[.NET SDK]\nA\n[.NET RUNTIMES]\nB"


def test_probe_block_is_appended_only_when_it_has_content(context):
    spec = AgentSpec(
        name="python_dev", prompt="{user_profile} p",
        probes=(Probe(triggers=("gpu",), label="GPU", run=lambda t: "OUT"),),
    )
    quiet, _ = _compose(spec, "write a loop", history=[])
    loud, _ = _compose(spec, "check the gpu", history=[])
    assert len(quiet) == 1, "system message only"
    assert len(loud) == 2, "system message + the probe block"


# ── the opt-out agent ──
def test_terse_opts_out_of_profile_memory_and_tools(context):
    """terse is the one agent that takes none of the shared context: no profile,
    no recalled memory, no tool loop, a shorter window. Brevity is the product,
    and every one of those inputs would dilute it."""
    spec = _all_agents()["terse"].spec
    assert spec.uses_profile is False
    assert spec.remembers is False
    assert spec.uses_tools is False
    assert spec.max_messages == 4

    prompt = _prompt_for(spec, "git rebase syntax")
    assert prompt == spec.prompt, "terse's prompt must reach the model untouched"
    assert "PROFILE" not in prompt and "RECALLED" not in prompt


def test_terse_prompt_carries_no_profile_slot():
    """Pins the reason uses_profile is False: there is nowhere to put it. A later
    edit that adds a {user_profile} slot without flipping the flag would silently
    ship the literal placeholder — the bug this whole layer just got fixed for."""
    assert "{user_profile}" not in _all_agents()["terse"].spec.prompt


# ── per-agent settings the pipeline must not flatten ──
def test_memory_kind_is_preserved_per_agent():
    specs = {n: a.spec for n, a in _all_agents().items()}
    assert specs["python_dev"].memory_kind == "code"
    assert specs["knowledge_learning"].memory_kind == "lesson"
    assert specs["writer"].memory_kind == "chat"


def test_agents_keep_their_own_probe_wording():
    specs = {n: a.spec for n, a in _all_agents().items()}
    assert specs["it_networking"].probe_intro.startswith("Here are the live")
    assert specs["knowledge_learning"].probe_outro == "Teach accordingly."
    assert specs["ai_ml"].probe_intro == "System tool results:"


def test_knowledge_is_the_only_agent_with_an_after_hook():
    with_hook = {n for n, a in _all_agents().items() if a.spec.after}
    assert with_hook == {"knowledge_learning"}
