#!/usr/bin/env python3
# ~/agentic-ai/patch_agents_memory.py (FIXED VERSION)
# Run: python3 patch_agents_memory.py

import shutil
from pathlib import Path

AGENTS_DIR = Path(__file__).parent.parent / "agents"

AGENT_CONFIGS = [
    {"file": "it_networking.py",      "agent_id": "it_networking",      "mem_type": "chat",     "prompt_var": "IT_SYSTEM_PROMPT"},
    {"file": "python_dev.py",          "agent_id": "python_dev",          "mem_type": "code",     "prompt_var": None},
    {"file": "blazor_dev.py",          "agent_id": "blazor_dev",          "mem_type": "code",     "prompt_var": None},
    {"file": "ai_ml.py",               "agent_id": "ai_ml",               "mem_type": "chat",     "prompt_var": None},
    {"file": "documents.py",           "agent_id": "documents",           "mem_type": "chat",     "prompt_var": None},
    {"file": "personal_projects.py",   "agent_id": "personal_projects",   "mem_type": "project",  "prompt_var": None},
    {"file": "research.py",            "agent_id": "research",            "mem_type": "research", "prompt_var": None},
    {"file": "knowledge_learning.py",  "agent_id": "knowledge_learning",  "mem_type": "lesson",   "prompt_var": None},
]

IMPORT_LINE = "from memory_context import get_memory_context, save_to_memory"

def find_prompt_var(content, hint=None):
    if hint:
        return hint
    import re
    m = re.search(r'SystemMessage\(content=([A-Z_]+)\)', content)
    if m:
        return m.group(1)
    m = re.search(r'^([A-Z_]+PROMPT)\s*=', content, re.MULTILINE)
    if m:
        return m.group(1)
    return None

def already_patched(content):
    return "get_memory_context" in content

def patch_agent(config):
    path = AGENTS_DIR / config["file"]
    if not path.exists():
        print(f"  SKIP  {config['file']} -- not found")
        return False

    content = path.read_text()

    if already_patched(content):
        print(f"  OK    {config['file']} -- already patched")
        return True

    shutil.copy2(path, path.with_suffix(".py.bak"))

    agent_id   = config["agent_id"]
    mem_type   = config["mem_type"]
    prompt_var = find_prompt_var(content, config["prompt_var"])

    if not prompt_var:
        print(f"  WARN  {config['file']} -- could not find prompt variable")
        return False

    lines = content.split("\n")
    out   = []
    import_added = False
    before_added = False
    after_added  = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Add import after last import block
        if not import_added and line.startswith(("from ", "import ")):
            next_line = lines[i+1] if i+1 < len(lines) else ""
            if not next_line.startswith(("from ", "import ")):
                out.append(line)
                out.append(IMPORT_LINE)
                import_added = True
                i += 1
                continue

        # After task = state.get(...) inject memory search
        if not before_added and "task = state.get(" in line:
            out.append(line)
            out.append("")
            out.append("    # -- Memory: search before responding --")
            out.append("    _mem_ctx = get_memory_context(task, \"" + agent_id + "\")")
            out.append("    _effective_prompt = " + prompt_var)
            out.append("    if _mem_ctx:")
            out.append("        _effective_prompt = " + prompt_var + " + chr(10) + chr(10) + _mem_ctx")
            out.append("    # ----------------------------------------")
            out.append("")
            before_added = True
            i += 1
            continue

        # Replace SystemMessage prompt reference
        if before_added and ("SystemMessage(content=" + prompt_var + ")") in line:
            line = line.replace(
                "SystemMessage(content=" + prompt_var + ")",
                "SystemMessage(content=_effective_prompt)"
            )

        # After response = llm.invoke( inject memory save
        if not after_added and "response = llm.invoke(" in line:
            out.append(line)
            out.append("")
            out.append("    # -- Memory: save after responding --")
            out.append("    save_to_memory(\"" + agent_id + "\", \"" + mem_type + "\", response.content,")
            out.append("                   {\"task\": task[:120] if task else \"\"})")
            out.append("    # ------------------------------------")
            out.append("")
            after_added = True
            i += 1
            continue

        out.append(line)
        i += 1

    if not import_added:
        print(f"  WARN  {config['file']} -- import not added")
    if not before_added:
        print(f"  WARN  {config['file']} -- memory search not added")
    if not after_added:
        print(f"  WARN  {config['file']} -- memory save not added")

    path.write_text("\n".join(out))
    print(f"  DONE  {config['file']}")
    return True

def verify(config):
    path = AGENTS_DIR / config["file"]
    if not path.exists():
        return False
    c = path.read_text()
    return all([
        "from memory_context import" in c,
        "get_memory_context" in c,
        "save_to_memory" in c,
        "_effective_prompt" in c,
    ])

def main():
    print("=" * 55)
    print("PATCHING AGENTS WITH MEMORY (fixed version)")
    print("=" * 55)

    for config in AGENT_CONFIGS:
        patch_agent(config)

    print()
    print("VERIFICATION")
    print("-" * 55)
    all_ok = True
    for config in AGENT_CONFIGS:
        ok = verify(config)
        print(f"  {'PASS' if ok else 'FAIL'}  {config['file']}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("ALL AGENTS PATCHED -- restart uvicorn now:")
        print("  uvicorn api:app --host 0.0.0.0 --port 8000")
    else:
        print("Some agents failed. Restore from .bak files:")
        print("  cd ~/agentic-ai/agents")
        print("  for f in *.py.bak; do cp \"$f\" \"${f%.bak}\"; done")

if __name__ == "__main__":
    main()
