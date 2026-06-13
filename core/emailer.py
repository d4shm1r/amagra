"""
emailer.py — Transactional email delivery via SendGrid

Handles:
  - Onboarding email: API key delivery after successful payment
  - Billing confirmation: receipt summary

Environment variables required:
  SENDGRID_API_KEY   SG.xxxx
  SENDER_EMAIL       noreply@yourdomain.com  (must be verified in SendGrid)
  SENDER_NAME        Amagra  (optional, defaults to "Amagra")
"""

import os

_SG_API_KEY   = os.environ.get("SENDGRID_API_KEY", "")
_SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@amagra.ai")
_SENDER_NAME  = os.environ.get("SENDER_NAME", "Amagra")

TIER_LIMITS = {
    "free":       "100 requests/day",
    "developer":  "5,000 requests/day",
    "team":       "50,000 requests/day",
    "enterprise": "Unlimited",
}


def _sg():
    """Lazy import sendgrid so missing package doesn't break the whole API."""
    try:
        import sendgrid
        return sendgrid
    except ImportError:
        raise RuntimeError(
            "sendgrid package not installed. Run: pip install sendgrid"
        )


def send_onboarding_email(
    to_email: str,
    api_key:  str,
    tier:     str,
    plan_label: str = "Developer",
) -> None:
    """
    Send the API key delivery + onboarding email to a new customer.

    Args:
        to_email   — customer email address
        api_key    — raw API key (sk-...), shown once
        tier       — plan tier name ("developer" | "team" | "enterprise")
        plan_label — display name for the plan
    """
    if not _SG_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY not set — email delivery disabled")

    sg = _sg()
    from sendgrid.helpers.mail import Mail, To, From

    limit = TIER_LIMITS.get(tier, "5,000 requests/day")

    subject = f"Your Amagra API key — {plan_label} plan"

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; background: #F4F0E8; margin: 0; padding: 40px 20px; }}
    .card {{ background: #FEFCFA; border-radius: 8px; max-width: 540px; margin: 0 auto; padding: 36px 40px; }}
    h1 {{ font-size: 22px; color: #2E2010; margin: 0 0 8px; }}
    p {{ color: #5C4030; font-size: 14px; line-height: 1.7; margin: 16px 0; }}
    .key {{ background: #1E1E1E; color: #89D185; font-family: Consolas, monospace; font-size: 13px;
            padding: 14px 18px; border-radius: 5px; word-break: break-all; margin: 20px 0; }}
    .row {{ display: flex; gap: 24px; margin: 20px 0; }}
    .stat {{ background: #F4F0E8; border-radius: 5px; padding: 12px 16px; flex: 1; }}
    .stat-label {{ font-size: 10px; color: #9A7A60; text-transform: uppercase; letter-spacing: 0.1em; }}
    .stat-value {{ font-size: 16px; font-weight: 700; color: #2E2010; margin-top: 4px; }}
    .footer {{ font-size: 11px; color: #9A7A60; margin-top: 32px; border-top: 1px solid #EDE8DF; padding-top: 20px; }}
    a {{ color: #A87933; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Welcome to Amagra.</h1>
    <p>
      Your {plan_label} plan is active. Here is your API key — copy it now,
      it will not be shown again.
    </p>

    <div class="key">{api_key}</div>

    <div class="row">
      <div class="stat">
        <div class="stat-label">Plan</div>
        <div class="stat-value">{plan_label}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Daily limit</div>
        <div class="stat-value">{limit}</div>
      </div>
    </div>

    <p><strong>Getting started</strong></p>
    <p>
      Add the header <code>X-API-Key: {api_key[:12]}...</code> to every request.
      See the <a href="https://github.com/d4shm1r/amagra">documentation</a>
      for setup instructions and the full API reference.
    </p>

    <p>
      Check your usage at any time:<br />
      <code>GET /usage</code> with your key in the header.
    </p>

    <div class="footer">
      You are receiving this because you subscribed to Amagra.
      To manage your subscription, visit your Stripe billing portal.<br />
      Questions? Reply to this email.
    </div>
  </div>
</body>
</html>
"""

    text_body = f"""Welcome to Amagra — {plan_label} plan active.

Your API key (shown once — store it securely):
{api_key}

Plan:        {plan_label}
Daily limit: {limit}

Add header X-API-Key to every request.
Check usage: GET /usage

Questions? Reply to this email.
"""

    message = Mail(
        from_email=From(_SENDER_EMAIL, _SENDER_NAME),
        to_emails=To(to_email),
        subject=subject,
        html_content=html_body,
        plain_text_content=text_body,
    )

    sg_client = sg.SendGridAPIClient(_SG_API_KEY)
    response  = sg_client.send(message)

    if response.status_code >= 400:
        raise RuntimeError(
            f"SendGrid returned {response.status_code}: {response.body}"
        )

    print(f"[emailer] onboarding email sent to {to_email} (status {response.status_code})")


def send_billing_confirmation(to_email: str, amount: str, plan_label: str) -> None:
    """
    Send a simple billing receipt after a successful charge.
    amount: formatted string, e.g. "$39.00"
    """
    if not _SG_API_KEY:
        return  # silent no-op if email not configured

    sg = _sg()
    from sendgrid.helpers.mail import Mail, To, From

    message = Mail(
        from_email=From(_SENDER_EMAIL, _SENDER_NAME),
        to_emails=To(to_email),
        subject=f"Amagra — payment confirmed ({amount})",
        plain_text_content=(
            f"Payment of {amount} confirmed for the {plan_label} plan.\n\n"
            "Your access continues uninterrupted. Thank you.\n\n"
            "— Amagra"
        ),
    )

    sg_client = sg.SendGridAPIClient(_SG_API_KEY)
    sg_client.send(message)
