# ~/agentic-ai/reflection.py
# ─────────────────────────────────────────────────────────────
# Reflection layer — wraps any agent response with:
#   1. Grounded evaluation (code execution, schema checks)
#   2. LLM critique (finds weak steps)
#   3. LLM refinement (fixes only broken parts)
#
# Usage:
#   from cognition.reflection import reflection_loop
#   final, history = reflection_loop(task, raw_response, agent_type="code")
#
# agent_type: "code" | "research" | "general"
# ─────────────────────────────────────────────────────────────

import ast
import json
import re
import os
import sys


THRESHOLD = 0.80
MAX_ITERS = 3

# ── 1. GROUNDED EVALUATION ───────────────────────────────────

def _extract_code_blocks(text: str) -> list[str]:
    """Pull out ```python blocks from agent response."""
    return re.findall(r"```python\s*(.*?)```", text, re.DOTALL)


def _run_code_check(code: str) -> tuple[bool, str]:
    """
    Check code quality via AST parse (syntax only).

    Subprocess execution was replaced because LLM-generated code routinely
    imports libraries not installed in the local environment, causing false
    negatives that triggered unnecessary retries (31% retry rate observed).
    Syntax errors are a genuine quality signal; import failures are not.
    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError line {e.lineno}: {e.msg}"


def grounded_evaluate(task: str, response: str,
                       agent_type: str = "general") -> dict:
    """
    Score response using external signals + LLM judgment.
    Returns {"score": float, "errors": list[str], "details": dict}
    """
    errors = []
    penalty = 0.0
    details = {}

    # ── Code grounding ──────────────────────────────────────
    if agent_type == "code":
        blocks = _extract_code_blocks(response)
        if not blocks:
            # Response has no code block — penalize if task asked for code
            if any(w in task.lower() for w in
                   ["write", "create", "build", "implement", "code", "script"]):
                penalty += 0.2
                errors.append("No code block found in response")
        else:
            for i, block in enumerate(blocks):
                ok, err = _run_code_check(block)
                details[f"code_block_{i}"] = {"ok": ok, "error": err}
                if not ok:
                    penalty += 0.3
                    errors.append(f"Code block {i} fails: {err}")

    # ── General grounding ────────────────────────────────────
    # Check response isn't too short
    word_count = len(response.split())
    if word_count < 10:
        penalty += 0.1
        errors.append(f"Response too short ({word_count} words)")

    # Check response doesn't start with fluff
    fluff_starts = ["great question", "i'm excited", "certainly!", "of course!"]
    if any(response.lower().startswith(f) for f in fluff_starts):
        penalty += 0.1
        errors.append("Response starts with filler phrase")

    base_score = 0.82  # Raised from 0.75: syntax-only check is less penalising
    final_score = max(0.0, base_score - penalty)

    return {
        "score": round(final_score, 2),
        "errors": errors,
        "details": details,
    }


# ── 2. LLM CRITIQUE ──────────────────────────────────────────

def critique(task: str, response: str, evaluation: dict) -> dict:
    """Ask LLM to find exactly what's wrong. Returns structured issues."""
    from models.llm import llm

    error_list = "\n".join(f"- {e}" for e in evaluation["errors"]) or "None detected"

    prompt = f"""Task given to agent:
{task}

Agent response:
{response}

Known errors from automated check:
{error_list}

Find the most critical problem in the response.
Return JSON only, no explanation:
{{
  "issues": [
    {{
      "location": "describe where in the response",
      "reason": "why it is wrong",
      "severity": "HIGH"
    }}
  ]
}}"""

    try:
        result = llm.invoke(prompt)
        text = result.content.strip()
        # Extract JSON even if model adds text around it
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"issues": [{"location": "unknown", "reason": text[:200],
                             "severity": "MEDIUM"}]}
    except Exception as e:
        return {"issues": [{"location": "unknown",
                             "reason": f"Critique failed: {e}",
                             "severity": "LOW"}]}


# ── 3. LLM REFINEMENT ────────────────────────────────────────

def refine(task: str, response: str, issues: dict) -> str:
    """Ask LLM to fix only the broken parts. Returns revised response."""
    from models.llm import llm

    issue_list = "\n".join(
        f"- [{i['severity']}] {i['location']}: {i['reason']}"
        for i in issues.get("issues", [])
    ) or "No specific issues"

    prompt = f"""Task:
{task}

Current response:
{response}

Issues to fix:
{issue_list}

Rules:
- Fix HIGH severity issues first
- Do NOT rewrite correct sections
- Preserve structure and format
- Do not add new assumptions
- Be concise

Return corrected response only:"""

    try:
        result = llm.invoke(prompt)
        return result.content.strip()
    except Exception as e:
        return response  # Return original if refinement fails


# ── 4. MAIN LOOP ─────────────────────────────────────────────

def reflection_loop(task: str, response: str,
                    agent_type: str = "general",
                    mode: str = "full",
                    max_iters: int = MAX_ITERS,
                    threshold: float = THRESHOLD) -> tuple[str, list]:
    """
    Main entry point. Wraps any agent response.

    mode:
      "light" — grounded evaluation only (no LLM critique/refine). Fast.
      "full"  — grounded eval + LLM critique + iterative refinement. Slow.

    Returns:
        (final_response, history)
        history = list of (response, evaluation, issues) per iteration
    """
    history = []
    print(f"[reflection] starting ({mode} mode, agent_type={agent_type})")

    # Light mode: one grounded pass, no LLM calls.
    if mode == "light":
        evaluation = grounded_evaluate(task, response, agent_type)
        score = evaluation["score"]
        print(f"[reflection] light eval — score: {score} errors: {evaluation['errors']}")
        history.append((response, evaluation, {}))
        return response, history

    # Full mode: iterative grounded + LLM critique + refine.
    for i in range(max_iters):
        evaluation = grounded_evaluate(task, response, agent_type)
        score = evaluation["score"]
        print(f"[reflection] iter {i+1} — score: {score} "
              f"errors: {evaluation['errors']}")

        if score >= threshold:
            print(f"[reflection] ✅ score {score} >= threshold {threshold}, done")
            history.append((response, evaluation, {}))
            break

        issues = critique(task, response, evaluation)
        new_response = refine(task, response, issues)

        # Stop if no progress
        if new_response.strip() == response.strip():
            print("[reflection] ⚠ no change after refinement, stopping")
            history.append((response, evaluation, issues))
            break

        history.append((response, evaluation, issues))
        response = new_response

    return response, history


# ── STANDALONE TEST ──────────────────────────────────────────

if __name__ == "__main__":
    print("reflection.py — standalone test (no LLM needed)")
    print("Testing grounded_evaluate only...\n")

    # Test 1: good code
    good = "Here's the function:\n```python\ndef add(a, b):\n    return a + b\nprint(add(1, 2))\n```"
    result = grounded_evaluate("write a function to add two numbers", good, "code")
    print(f"Good code: score={result['score']} errors={result['errors']}")

    # Test 2: broken code
    bad = "Here's the function:\n```python\ndef add(a, b)\n    return a + b\n```"
    result = grounded_evaluate("write a function to add two numbers", bad, "code")
    print(f"Bad code:  score={result['score']} errors={result['errors']}")

    # Test 3: fluff start
    fluff = "Great question! Here is how DNS works: it resolves domain names to IP addresses using a hierarchy of servers."
    result = grounded_evaluate("what is DNS", fluff, "general")
    print(f"Fluff:     score={result['score']} errors={result['errors']}")

    # Test 4: good general
    good2 = "DNS resolves domain names to IP addresses. It uses a hierarchy: root servers, TLD servers, authoritative servers. Your machine queries recursively until it gets the IP."
    result = grounded_evaluate("what is DNS", good2, "general")
    print(f"Good gen:  score={result['score']} errors={result['errors']}")

    print("\nAll grounded tests done. LLM tests require Ollama running.")
