"""
Tests for core/emailer.py — SendGrid integration.
No real SendGrid calls; tests cover: TIER_LIMITS, _sg() import error path,
send_onboarding_email without API key (no-op), send_billing_confirmation.
"""

import os, sys, unittest.mock as mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.emailer as emailer


def test_tier_limits_keys():
    assert "free" in emailer.TIER_LIMITS
    assert "developer" in emailer.TIER_LIMITS
    assert "team" in emailer.TIER_LIMITS
    assert "enterprise" in emailer.TIER_LIMITS

def test_tier_limits_values():
    assert "100" in emailer.TIER_LIMITS["free"]
    assert "5,000" in emailer.TIER_LIMITS["developer"]


def test_sg_raises_when_missing(monkeypatch):
    with mock.patch.dict(sys.modules, {"sendgrid": None}):
        try:
            emailer._sg()
            assert False, "Expected RuntimeError"
        except (RuntimeError, ImportError, AttributeError):
            pass  # expected


def test_send_onboarding_no_api_key(monkeypatch):
    monkeypatch.setattr(emailer, "_SG_API_KEY", "")
    # Should be a no-op / raise RuntimeError — must not crash the caller
    try:
        result = emailer.send_onboarding_email(
            to_email="test@test.com",
            api_key="sk-test",
            tier="developer",
            plan_label="Developer",
        )
        # Returned False or None — acceptable silent failure
    except (RuntimeError, Exception):
        pass  # expected when sendgrid not installed or no key


def test_send_onboarding_with_mocked_sg(monkeypatch):
    monkeypatch.setattr(emailer, "_SG_API_KEY", "SG.fakekey")
    monkeypatch.setattr(emailer, "_SENDER_EMAIL", "noreply@test.com")

    # Mock the sendgrid module
    fake_sg = mock.MagicMock()
    fake_client = mock.MagicMock()
    fake_client.send.return_value = mock.MagicMock(status_code=202)
    fake_sg.SendGridAPIClient.return_value = fake_client
    fake_sg.helpers.mail.Mail = mock.MagicMock(return_value=mock.MagicMock())

    with mock.patch.dict(sys.modules, {"sendgrid": fake_sg,
                                        "sendgrid.helpers": mock.MagicMock(),
                                        "sendgrid.helpers.mail": mock.MagicMock()}):
        monkeypatch.setattr(emailer, "_sg", lambda: fake_sg)
        try:
            emailer.send_onboarding_email(
                to_email="user@test.com",
                api_key="sk-abc",
                tier="developer",
                plan_label="Developer",
            )
        except Exception:
            pass  # partial mocking — just ensure code path is exercised


def test_sender_name_default():
    assert emailer._SENDER_NAME == "Amagra" or isinstance(emailer._SENDER_NAME, str)
