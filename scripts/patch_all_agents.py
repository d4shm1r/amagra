# ~/agentic-ai/patch_all_agents.py
# Patches all 7 remaining agents to inject user_profile.
# Safe to run multiple times — skips already-patched files.

import os

AGENTS_DIR = os.path.expanduser("~/agentic-ai/agents")

AGENTS = [
    ("ai_ml.py",             "AI_ML_SYSTEM_PROMPT"),
    ("blazor_dev.py",        "BLAZOR_SYSTEM_PROMPT"),
    ("documents.py",         "DOCUMENTS_SYSTEM_PROMPT"),
    ("it_networking.py",     "IT_SYSTEM_PROMPT"),
    ("personal_projects.py", "PERSONAL_PROJECTS_SYSTEM_PROMPT"),
    ("python_dev.py",        "PYTHON_SYSTEM_PROMPT"),
    ("research.py",          "RESEARCH_SYSTEM_PROMPT"),
]

patched = 0
skipped = 0

for filename, prompt_var in AGENTS:
    path = os.path.join(AGENTS_DIR, filename)

    with open(path) as f:
        content = f.read()

    # Skip if already patched
    if "get_profile_context" in content:
        print(f"  ⏭ {filename} — already patched")
        skipped += 1
        continue

    # 1. Add {user_profile} placeholder to the system prompt string
    old_prompt_start = f'{prompt_var} = """'
    new_prompt_start = f'{prompt_var} = """\n{{user_profile}}\n'

    if old_prompt_start not in content:
        print(f"  ✗ {filename} — prompt start not found, skipping")
        continue

    content = content.replace(old_prompt_start, new_prompt_start, 1)

    # 2. Inject profile at the _effective_prompt line
    old_line = f"    _effective_prompt = {prompt_var}"
    new_line  = (
        f"    from user_profile import get_profile_context\n"
        f"    _effective_prompt = {prompt_var}.format(user_profile=get_profile_context())"
    )

    if old_line not in content:
        print(f"  ✗ {filename} — _effective_prompt line not found, skipping")
        continue

    content = content.replace(old_line, new_line, 1)

    with open(path, "w") as f:
        f.write(content)

    print(f"  ✅ {filename} — patched")
    patched += 1

print(f"\n  Done. {patched} patched, {skipped} already done.")
print("  Restart the API to apply changes.")
