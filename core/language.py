"""
language.py — dependency-free heuristic to flag non-English user input.

Motivation (GitHub issue #6): phi4-mini follows instructions poorly when the
English system prompt collides with non-English input — it drifts into mixed
language and, worse, leaks the private user-profile block. We cannot fix the
model, but we can detect non-English input cheaply and, when found, (a) strip
the profile injection and (b) tell the model to answer in the user's language.

This is a heuristic, not a classifier. It is tuned to be conservative: the cost
of a false positive (treating English as non-English) is only that the optional
tone-profile is skipped and a "reply in the user's language" line is added —
both harmless. The cost of a false negative is the original bug, i.e. no worse
than today. So we err toward catching foreign input.
"""

import re
import unicodedata

# Non-Latin scripts → unambiguously non-English when they dominate the letters.
_NON_LATIN_SCRIPT_PREFIXES = (
    "CYRILLIC", "GREEK", "ARABIC", "HEBREW", "HANGUL", "HIRAGANA",
    "KATAKANA", "CJK", "DEVANAGARI", "THAI", "ARMENIAN", "GEORGIAN",
)

# High-frequency English function words. Any real English sentence of a few
# words almost always contains at least one of these.
_ENGLISH_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "to", "of", "and",
    "or", "in", "on", "at", "for", "with", "my", "your", "you", "i", "me",
    "it", "this", "that", "how", "what", "why", "when", "where", "who",
    "do", "does", "did", "can", "could", "should", "would", "will", "have",
    "has", "had", "not", "no", "yes", "if", "but", "so", "as", "from",
    "please", "help", "give", "make", "want", "need", "show", "tell",
}

# Diacritics that English essentially never uses — even one is a decisive
# non-English signal that overrides an incidental English-stopword collision
# (e.g. Albanian "me" = "with" colliding with English "me").
_STRONG_DIACRITICS = set("ëçñßøåæąćęłńśźżãõœ")

# Diacritics that also show up in English loanwords (café, naïve, résumé). A
# weak signal only — it must not override genuine English stopwords.
_WEAK_DIACRITICS = set("àâêîôûéèùüöäíóúá")

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _letters(text: str) -> str:
    return "".join(ch for ch in text if ch.isalpha())


def _dominant_non_latin(text: str) -> bool:
    letters = _letters(text)
    if not letters:
        return False
    non_latin = 0
    for ch in letters:
        try:
            name = unicodedata.name(ch)
        except ValueError:
            continue
        if name.startswith(_NON_LATIN_SCRIPT_PREFIXES):
            non_latin += 1
    return non_latin / len(letters) > 0.30


def is_probably_non_english(text: str) -> bool:
    """
    Return True when `text` looks like it is written in a language other than
    English. Conservative by design — see module docstring.
    """
    if not text or not text.strip():
        return False

    # 1. Any dominant non-Latin script (Cyrillic, CJK, Arabic, …).
    if _dominant_non_latin(text):
        return True

    # 2. Latin script: lean on English stopwords + non-English diacritics.
    words = [w.lower() for w in _WORD_RE.findall(text)]
    if not words:
        return False

    chars = {ch for w in words for ch in w}

    # A strong (non-loanword) diacritic settles it, even if an English stopword
    # happens to collide with a foreign word.
    if chars & _STRONG_DIACRITICS and len(words) >= 2:
        return True

    if any(w in _ENGLISH_STOPWORDS for w in words):
        # Real English function words → treat as English even if a stray
        # accented loan-word ("café") slipped in.
        return False

    # No English stopwords at all. A weak diacritic now tips it; otherwise
    # require a longer phrase so we don't flag terse English commands like
    # "configure vlan trunking" or "restart nginx service".
    if chars & _WEAK_DIACRITICS and len(words) >= 2:
        return True
    if len(words) >= 5:
        return True
    return False
