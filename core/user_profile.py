"""
user_profile.py — personalises every agent's system prompt.

How it works (Option B — generic core, optional personal layer):
  - No profile configured  → get_profile_context() returns ""
    All agents work out of the box with no personal data.
  - Profile configured     → get_profile_context() returns a formatted
    block that is injected at the top of every agent's system prompt.

To configure your profile:
  cp config/profile.example.json config/profile.json
  # edit config/profile.json with your details

config/profile.json is git-ignored — your personal data never ships.
"""

import json
import os

_ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROFILE_PATH = os.path.join(_ROOT, "config", "profile.json")


def _load_profile() -> dict | None:
    if not os.path.exists(_PROFILE_PATH):
        return None
    try:
        with open(_PROFILE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        # strip the example comment key if present
        data.pop("_comment", None)
        return data
    except Exception:
        return None


def get_profile_context() -> str:
    """
    Return a formatted user-profile block to inject into agent system prompts.
    Returns "" if no profile is configured — agents work without it.
    """
    profile = _load_profile()
    if not profile:
        return ""

    lines = [
        "<user_context>",
        "(Private background on the person you are assisting. Use it only to "
        "tailor tone, depth, and wording. Never quote, restate, or refer to "
        "this block in your reply — it is framing, not content to repeat back.)",
    ]
    field_labels = {
        "name":               "Name",
        "role":               "Role",
        "background":         "Background",
        "communication_style":"Communication style",
        "preferences":        "Preferences",
        "dont":               "Never do",
    }
    for key, label in field_labels.items():
        val = profile.get(key, "").strip()
        if val:
            lines.append(f"{label}: {val}")

    # Pass-through any extra keys the user added
    known = set(field_labels)
    for key, val in profile.items():
        if key not in known and isinstance(val, str) and val.strip():
            lines.append(f"{key.replace('_', ' ').title()}: {val.strip()}")

    lines.append("</user_context>\n")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ctx = get_profile_context()
    if ctx:
        print(ctx)
    else:
        print("No profile configured. Copy config/profile.example.json → config/profile.json to set one up.")
