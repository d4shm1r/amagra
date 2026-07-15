"""Single source of truth for the Amagra backend version.

Import this everywhere the running version is reported (the FastAPI app metadata,
/health) so a release bump touches exactly one Python file. The UI carries its own
marker in ui/src/config/constants.js (VERSION) — keep the two in lockstep on release.
"""

__version__ = "1.7.6"
