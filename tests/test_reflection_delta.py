"""Unit test for the pure answer-judge in the reflection on/off A/B harness."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workbench.evaluation import reflection_delta as rd


def test_judge_concrete_and_rubric():
    assert rd._judge("27017", "MongoDB uses 27017", None) is True
    assert rd._judge("27017", "no idea", None) is False
    assert rd._judge("27017", "", None) is None          # no text → ungradeable
    assert rd._judge("rubric", "anything", 0.7) is True
    assert rd._judge("rubric", "anything", 0.4) is False
    assert rd._judge("rubric", "anything", None) is None  # no quality → ungradeable
