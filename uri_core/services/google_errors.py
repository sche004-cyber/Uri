"""Safe, actionable descriptions of common Google setup failures."""

import re


CONSENT_URL = "https://console.cloud.google.com/auth/audience"
API_URLS = {
    "gmail": "gmail.googleapis.com",
    "drive": "drive.googleapis.com",
    "sheets": "sheets.googleapis.com",
    "docs": "docs.googleapis.com",
    "slides": "slides.googleapis.com",
    "forms": "forms.googleapis.com",
}


def api_enable_url(api: str, project: str | None = None) -> str:
    suffix = f"?project={project}" if project else ""
    return f"https://console.cloud.google.com/apis/library/{API_URLS[api]}{suffix}"


def classify_google_error(error: object, api: str = "gmail") -> dict:
    """Return an instruction without exposing request URLs, codes, or tokens."""
    value = str(error)
    lower = value.lower()
    project_match = re.search(r"project(?:\s+|%20)(\d+)", value, re.I)
    project = project_match.group(1) if project_match else None
    if ("accessnotconfigured" in lower or "service_disabled" in lower
            or "has not been used in project" in lower
            or ("api" in lower and "disabled" in lower)):
        link = api_enable_url(api, project)
        return {"kind": "api_disabled", "message": f"Google's {api.title()} API is switched off for your project. Enable it here: {link}, then retry.", "help_url": link}
    if "access_denied" in lower or "access denied" in lower:
        return {"kind": "test_user", "message": f"Google denied sign-in. If the OAuth consent screen is in Testing, add your Google account as a test user here: {CONSENT_URL}, then sign in again.", "help_url": CONSENT_URL}
    if "invalid_grant" in lower or "expired" in lower or "token has been revoked" in lower:
        return {"kind": "sign_in_again", "message": "Your Google sign-in has expired. Sign in with Google again.", "help_url": None}
    if "insufficient authentication scopes" in lower or "insufficientpermissions" in lower:
        return {"kind": "insufficient_scope", "message": "Your Google sign-in does not grant this operation. Reconnect Google in URI; if it still fails, this operation needs an additional permission URI does not request.", "help_url": None}
    return {"kind": "unknown", "message": f"Could not use Google {api.title()}. Check your Google setup and try again.", "help_url": api_enable_url(api)}
