"""
Unit tests for cognition/context_stratifier.py pure functions:
  routing_text, execution_text, weighted_text, stratify, PromptContext
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cognition.context_stratifier import (
    PromptContext, routing_text, execution_text, weighted_text, stratify
)


# ── routing_text ──────────────────────────────────────────────────────────────

def test_routing_text_returns_primary_task():
    ctx = PromptContext(primary_task="How do I configure nginx?")
    assert routing_text(ctx) == "How do I configure nginx?"

def test_routing_text_ignores_other_fields():
    ctx = PromptContext(
        primary_task="nginx config",
        dependency_outputs=["some output"],
        world_state="project context",
    )
    result = routing_text(ctx)
    assert result == "nginx config"
    assert "some output" not in result
    assert "project context" not in result


# ── execution_text ────────────────────────────────────────────────────────────

def test_execution_text_minimal():
    ctx = PromptContext(primary_task="How do I configure nginx?")
    result = execution_text(ctx)
    assert "How do I configure nginx?" in result
    assert result.startswith("Task:")

def test_execution_text_with_world_state():
    ctx = PromptContext(primary_task="deploy app", world_state="Flask project")
    result = execution_text(ctx)
    assert "Flask project" in result
    assert "Project context:" in result

def test_execution_text_with_dependencies():
    ctx = PromptContext(
        primary_task="deploy app",
        dependency_outputs=["build succeeded", "tests passed"]
    )
    result = execution_text(ctx)
    assert "build succeeded" in result
    assert "Previous step outputs:" in result

def test_execution_text_with_history():
    ctx = PromptContext(
        primary_task="deploy app",
        historical_context=["user asked about nginx", "configured SSL"]
    )
    result = execution_text(ctx)
    assert "Recent context:" in result
    assert "nginx" in result

def test_execution_text_truncates_history_to_3():
    ctx = PromptContext(
        primary_task="task",
        historical_context=[f"ctx {i}" for i in range(10)]
    )
    result = execution_text(ctx)
    # Only last 3 of 10 should appear
    assert "ctx 9" in result
    assert "ctx 0" not in result


# ── weighted_text ─────────────────────────────────────────────────────────────

def test_weighted_text_primary_task_repeated():
    ctx = PromptContext(primary_task="configure nginx")
    result = weighted_text(ctx)
    words = result.split()
    nginx_count = words.count("nginx")
    configure_count = words.count("configure")
    assert nginx_count == 3  # primary task repeated 3x
    assert configure_count == 3

def test_weighted_text_no_extras():
    ctx = PromptContext(primary_task="task")
    result = weighted_text(ctx)
    assert "task" in result
    assert "Previous" not in result

def test_weighted_text_with_deps():
    ctx = PromptContext(
        primary_task="deploy",
        dependency_outputs=["build output " * 5]
    )
    result = weighted_text(ctx)
    assert "deploy" in result
    assert "build" in result

def test_weighted_text_with_world_state():
    ctx = PromptContext(primary_task="task", world_state="python project " * 5)
    result = weighted_text(ctx)
    assert "python" in result


# ── stratify ─────────────────────────────────────────────────────────────────

def test_stratify_minimal():
    state = {}
    ctx = stratify(state, task="How do I set up DNS?")
    assert isinstance(ctx, PromptContext)
    assert "DNS" in ctx.primary_task

def test_stratify_with_history():
    state = {
        "history": [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
        ]
    }
    ctx = stratify(state, task="follow-up question")
    assert ctx.primary_task == "follow-up question"

def test_stratify_original_query_extraction():
    task_with_marker = "Implement this feature\n\nOriginal query: configure networking"
    state = {}
    ctx = stratify(state, task=task_with_marker)
    # original_task stores the raw task; primary_task extracts the original query
    assert ctx.original_task == task_with_marker
    assert ctx.primary_task == "configure networking"
    # Step desc goes to dependency_outputs
    assert any("Implement this feature" in dep for dep in ctx.dependency_outputs)

def test_stratify_world_summary():
    state = {}
    ctx = stratify(state, task="task", world_summary="Flask web app project")
    assert ctx.world_state == "Flask web app project"

def test_stratify_step_id_from_plan():
    class FakePlanStep:
        step_id = "step-42"
        success_criteria = "tests pass"
        uncertainty = 0.3

    state = {}
    ctx = stratify(state, task="implement feature", plan_step=FakePlanStep())
    assert ctx.step_id == "step-42"
    assert ctx.step_uncertainty == 0.3

def test_stratify_empty_state_empty_task():
    ctx = stratify({}, task="")
    assert isinstance(ctx, PromptContext)
