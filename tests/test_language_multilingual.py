"""
Labeled multilingual evaluation of core/language.py (GitHub issue #18).

Issue #6 shipped a dependency-free heuristic (`is_probably_non_english`);
issue #18 asks for a labeled test set across the languages we actually expect
(EN + SQ/ES/DE/FR/PT/IT + non-Latin scripts) and a precision/recall
measurement so regressions in the heuristic are caught and improvements are
visible.

Two layers:
  1. Aggregate precision/recall gates over the labeled set (the issue's ask).
  2. Documented known-miss cases (short Latin phrases, no diacritics, no
     stopword collision) asserted as CURRENTLY missed — if the heuristic
     improves, those asserts fail loudly and the samples graduate into the
     labeled set.

Positive class = non-English. False positive (English flagged) is harmless by
design; false negative is the original profile-leak bug. So the recall gate is
the one that matters most.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.language import is_probably_non_english


# ── Labeled set: (text, language, expect_non_english=True) ────────────────────

NON_ENGLISH = [
    # Albanian (the reported regression language)
    ("Si je sot, çfarë po bën me projektin tim?",              "sq"),
    ("Përshëndetje, si mund të rregulloj rrjetin tim",         "sq"),
    ("A mund të më ndihmosh me këtë problem të serverit",      "sq"),
    ("Më trego çfarë ndodhi me aplikacionin dje",              "sq"),
    # Spanish
    ("¿Cómo está tu configuración de red?",                    "es"),
    ("Necesito ayuda con la instalación del servidor",         "es"),
    ("Explícame cómo funciona la memoria compartida",          "es"),
    ("Quiero configurar una red privada virtual en casa",      "es"),
    # German
    ("Wie kann ich meinen Server neu konfigurieren?",          "de"),
    ("Bitte erkläre mir die Netzwerkeinstellungen genauer",    "de"),
    ("Können Sie mir bei diesem Python-Skript helfen",         "de"),
    ("Warum funktioniert diese Schleife nicht richtig",        "de"),
    # French
    ("Bonjour comment configurer mon serveur web",             "fr"),
    ("Peux-tu m'expliquer cette fonction récursive",           "fr"),
    ("J'ai besoin d'aide avec ma base de données",             "fr"),
    ("Pourquoi mon réseau est-il si lent aujourd'hui",         "fr"),
    # Portuguese
    ("Como posso configurar minha rede doméstica?",            "pt"),
    ("Preciso de ajuda com este código em Python",             "pt"),
    ("Explique como funciona a memória do sistema",            "pt"),
    # Italian
    ("Come posso configurare la mia rete di casa",             "it"),
    ("Ho bisogno di aiuto con questo codice Python",           "it"),
    ("Perché il mio server non risponde più alle richieste",   "it"),
    # Non-Latin scripts
    ("Привет, как у тебя дела сегодня?",                       "ru"),
    ("Как настроить домашнюю сеть быстро",                     "ru"),
    ("你好，今天过得怎么样？",                                    "zh"),
    ("如何配置我的家庭网络",                                      "zh"),
    ("サーバーの設定を手伝ってください",                            "ja"),
    ("홈 네트워크를 어떻게 설정하나요",                             "ko"),
    ("كيف يمكنني إعداد شبكتي المنزلية",                        "ar"),
    ("Πώς μπορώ να ρυθμίσω το δίκτυό μου",                     "el"),
]

ENGLISH = [
    "How do I configure my home network?",
    "What is the default Python dict ordering?",
    "configure vlan trunking",
    "restart nginx service",
    "deploy staging build",
    "Explain how neural networks learn from data",
    "Can you help me debug this Python script?",
    "I love this café near my house",
    "My résumé needs a naïve Bayes section",       # loanword diacritics
    "Show me the git log for last week",
    "Why is my server not responding to requests?",
    "kubernetes pod restart loop",
    "Write a function that reverses a linked list",
    "The quick brown fox jumps over the lazy dog",
    "please summarize this document",
    "What port does HTTPS use?",
    "Fix the failing unit test in the auth module",
]

# Known false positives (by design, harmless): 5+ word English phrases with no
# function words trip the length fallback. Cost is only a skipped tone-profile
# plus a "reply in the user's language" line — see core/language.py docstring.
KNOWN_FALSE_POSITIVES = [
    "run database migration script now",
]

# Known limitation (issue #18): short Latin-script non-English phrases with no
# diacritics and no English-stopword collision are NOT flagged today. Kept out
# of the recall gate; asserted as missed so an improvement is surfaced.
KNOWN_MISSES = [
    ("instala el paquete",        "es"),   # 3 words, no diacritics
    ("mostra il file",            "it"),
    ("configura la red local",    "es"),
]


# ── Aggregate precision/recall gates ──────────────────────────────────────────

def _confusion():
    tp = sum(1 for text, _ in NON_ENGLISH if is_probably_non_english(text))
    fn = len(NON_ENGLISH) - tp
    fp = sum(1 for text in ENGLISH if is_probably_non_english(text))
    tn = len(ENGLISH) - fp
    return tp, fn, fp, tn


def test_recall_on_non_english():
    # The gate that matters: a false negative is the profile-leak bug (#6).
    tp, fn, _, _ = _confusion()
    recall = tp / (tp + fn)
    missed = [f"{lang}: {text!r}" for text, lang in NON_ENGLISH
              if not is_probably_non_english(text)]
    assert recall >= 0.95, (
        f"non-English recall {recall:.2%} below gate (95%) — missed: {missed}"
    )


def test_precision_on_flagged():
    # False positives are harmless by design, but must stay bounded so the
    # language directive doesn't degrade ordinary English sessions.
    tp, _, fp, _ = _confusion()
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    flagged_english = [t for t in ENGLISH if is_probably_non_english(t)]
    assert precision >= 0.90, (
        f"precision {precision:.2%} below gate (90%) — "
        f"English flagged: {flagged_english}"
    )


def test_no_english_false_positives():
    # Stronger than the precision gate: on this curated set the heuristic
    # currently produces zero English false positives. Keep it that way.
    flagged = [t for t in ENGLISH if is_probably_non_english(t)]
    assert not flagged, f"English wrongly flagged as non-English: {flagged}"


# ── Documented limitation trackers ────────────────────────────────────────────

def test_known_false_positives_still_flagged():
    """Stopword-free 5+ word English phrases are flagged — accepted trade-off.

    If this FAILS, the heuristic stopped over-flagging these — move them into
    ENGLISH and note the improvement on issue #18.
    """
    unflagged = [t for t in KNOWN_FALSE_POSITIVES
                 if not is_probably_non_english(t)]
    assert not unflagged, (
        f"Known false positives no longer flagged (improvement!): {unflagged} "
        "— promote them into ENGLISH."
    )


def test_known_misses_still_missed():
    """Short diacritic-free Latin phrases are a documented gap (issue #18).

    If this test FAILS, the heuristic now catches one of them — good news:
    move the sample into NON_ENGLISH and tighten the recall gate.
    """
    caught = [f"{lang}: {text!r}" for text, lang in KNOWN_MISSES
              if is_probably_non_english(text)]
    assert not caught, (
        f"Known-miss samples now caught (improvement!): {caught} — "
        "promote them into NON_ENGLISH."
    )
