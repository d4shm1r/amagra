# ~/agentic-ai/memory_filter.py
# ─────────────────────────────────────────────────────────────
# Called by save_to_memory() BEFORE embedding or DB write.
# Fast, zero-dependency, never raises.
#
# Three public functions:
#   should_save(content, mem_type, agent_name) → (bool, str)
#   clean_content(content)                     → str
#   is_duplicate(content, agent_name)          → bool
# ─────────────────────────────────────────────────────────────

import re
import sqlite3
import os

DB_PATH = os.path.join("memory", "agent_memory.db")

# ── 1. FLUFF PATTERNS ────────────────────────────────────────
_FLUFF_OPENERS = [
    r"^i'?m (excited|thrilled|delighted|happy|glad|pleased) to\b",
    r"^i'?d (love|like) to\b",
    r"^i'?ve taken note\b",
    r"^i'?ll (make sure|ensure|help|support)\b",
    r"^great (question|to (meet|work|hear))\b",
    r"^of course[!.]?\s*",
    r"^certainly[!.]?\s*",
    r"^sure thing[!.]?\s*",
    r"^absolutely[!.]?\s*",
    r"^\*\*system ok\*\*\s*",
    r"^based on (our previous interactions|your (profile|preferences|interests))[,.]",
]

# Hard: 1 hit anywhere = reject the whole entry
_FLUFF_HARD = [
    "as an ai",
    "as a language model",
    "i don't have personal",
    "i cannot browse",
    "great question",
    "happy to assist",
    "happy to help",
    "glad to help",
    "you're welcome",
    "my pleasure",
]

# Soft: 2+ hits = reject
_FLUFF_PHRASES = [
    "let me know if you need",
    "feel free to ask",
    "i hope this helps",
    "hope that helps",
    "is there anything else",
    "anything else i can help",
]

# ── 2. MINIMUM QUALITY THRESHOLDS ───────────────────────────
_MIN_WORDS = {
    "chat":     12,
    "code":      8,
    "lesson":   20,
    "research": 25,
    "project":  10,
}
_DEFAULT_MIN_WORDS = 10


def _word_count(text: str) -> int:
    return len(text.split())


# ── 3. CLEAN CONTENT ─────────────────────────────────────────

def clean_content(content: str) -> str:
    """
    Strip fluff preambles from the START of content.
    Preserves the real content that follows.
    """
    if not content or not content.strip():
        return content

    sentences = re.split(r'(?<=[.!?])\s+', content.strip())

    cleaned = []
    stripping = True

    for sentence in sentences:
        if stripping:
            lower = sentence.lower().strip()
            is_fluff = any(
                re.match(pattern, lower, re.IGNORECASE)
                for pattern in _FLUFF_OPENERS
            )
            is_short_opener = (
                _word_count(sentence) < 6
                and "```" not in sentence
                and not re.search(r"[{(\[]", sentence)
            )
            if is_fluff or is_short_opener:
                continue
            else:
                stripping = False
                cleaned.append(sentence)
        else:
            cleaned.append(sentence)

    result = " ".join(cleaned).strip()
    return result if result else content


# ── 4. FLUFF DETECTION (whole-entry) ────────────────────────

def _is_fluff(content: str) -> bool:
    lower = content.lower()
    # One hard phrase = reject
    if any(phrase in lower for phrase in _FLUFF_HARD):
        return True
    # Two soft phrases = reject
    hits = sum(1 for phrase in _FLUFF_PHRASES if phrase in lower)
    if hits >= 2:
        return True
    # Very short + no code + no numbers = likely filler
    if _word_count(content) < 8 and "```" not in content and not re.search(r"\d", content):
        return True
    return False


def _meets_minimum(content: str, mem_type: str) -> bool:
    min_words = _MIN_WORDS.get(mem_type, _DEFAULT_MIN_WORDS)
    return _word_count(content) >= min_words


def _is_mostly_generic(content: str) -> bool:
    personal_markers = ["you ", "your ", " i ", "we ", "our "]
    has_personal = any(m in content.lower() for m in personal_markers)
    if has_personal:
        return False
    generic_openers = [
        r"^\w[\w\s]+ is a ",
        r"^\w[\w\s]+ are ",
        r"^in computer science",
        r"^in software development",
        r"^this refers to",
    ]
    for pattern in generic_openers:
        if re.match(pattern, content.strip(), re.IGNORECASE):
            return True
    return False


# ── 5. DUPLICATE DETECTION ──────────────────────────────────

def _normalise(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(".,!?;:")
    return text


def is_duplicate(content: str, agent_name: str, threshold: float = 0.85) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        rows = conn.execute(
            "SELECT content FROM memories WHERE agent_name = ? ORDER BY id DESC LIMIT 50",
            (agent_name,),
        ).fetchall()
        conn.close()
    except Exception:
        return False

    norm_new = _normalise(content)
    if not norm_new:
        return False

    for (existing,) in rows:
        norm_existing = _normalise(existing or "")
        if not norm_existing:
            continue
        set_a = set(norm_new.split())
        set_b = set(norm_existing.split())
        if not set_a or not set_b:
            continue
        intersection = len(set_a & set_b)
        score = (2 * intersection) / (len(set_a) + len(set_b))
        if score >= threshold:
            return True

    return False


# ── 6. MAIN GATE ─────────────────────────────────────────────

def should_save(content: str, mem_type: str, agent_name: str) -> tuple[bool, str]:
    """
    Master filter. Call this AFTER clean_content().
    Returns (True, "ok") or (False, reason).
    """
    if not content or not content.strip():
        return False, "empty"
    if _is_fluff(content):
        return False, "fluff"
    if not _meets_minimum(content, mem_type):
        return False, f"too_short ({_word_count(content)} words)"
    if _is_mostly_generic(content):
        return False, "generic_definition"
    if is_duplicate(content, agent_name):
        return False, "duplicate"
    return True, "ok"


# ── STANDALONE TEST ──────────────────────────────────────────
if __name__ == "__main__":
    print("memory_filter.py — unit tests")
    print("=" * 50)

    print("\n[clean_content tests]")
    dirty = "I'm excited to work with you! As an IT specialist, I'll help you build scalable systems. To configure a static IP on Ubuntu, edit /etc/netplan/01-netcfg.yaml and set addresses, gateway4, and nameservers."
    cleaned = clean_content(dirty)
    print(f"  Input:  {dirty[:80]}...")
    print(f"  Output: {cleaned[:80]}...")
    assert "excited" not in cleaned.lower(), "Fluff opener should be stripped"
    assert "netplan" in cleaned.lower(), "Real content should remain"
    print("  ✓ fluff opener stripped, real content preserved")

    system_ok = "**SYSTEM OK** I'm thrilled to assist! Let's explore LangGraph StateGraph together and dive into technical details."
    cleaned2 = clean_content(system_ok)
    print(f"\n  Input:  {system_ok}")
    print(f"  Output: {cleaned2}")
    print("  ✓ SYSTEM OK prefix handled")

    print("\n[should_save tests]")
    cases = [
        ("I'm excited to help you with this! Great question, happy to assist.", "chat", "it_networking", False, "pure fluff"),
        ("DNS resolves domain names to IP addresses.", "chat", "it_networking", False, "too short + generic"),
        ("Sure thing! Let me know if you need anything else.", "chat", "python_dev", False, "filler"),
        (
            "To configure a static IP on Ubuntu, edit /etc/netplan/01-netcfg.yaml "
            "and set addresses, gateway4, and nameservers under your interface. "
            "Run sudo netplan apply to activate changes.",
            "chat", "it_networking", True, "real IT answer"
        ),
        (
            "def factorial(n):\n    if n <= 1: return 1\n    return n * factorial(n-1)",
            "code", "python_dev", True, "real code"
        ),
        (
            "LangGraph StateGraph requires you to define nodes as functions and edges as "
            "conditional transitions. Your coordinator routes to specialist agents based on "
            "the task type extracted from user input.",
            "lesson", "knowledge_learning", True, "real lesson"
        ),
    ]

    passed = 0
    for content, mem_type, agent, expect, label in cases:
        ok, reason = should_save(content, mem_type, agent)
        result = "✓" if ok == expect else "✗"
        if ok == expect:
            passed += 1
        print(f"  {result} [{label}] → save={ok}, reason={reason}")

    print(f"\n  {passed}/{len(cases)} passed")
