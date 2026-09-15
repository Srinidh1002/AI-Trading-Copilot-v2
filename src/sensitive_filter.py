"""Redact sensitive values (API keys, tokens, credentials) from log output."""
import logging


class SensitiveFilter(logging.Filter):
    """Logging filter that replaces any configured sensitive string with
    a redaction marker in the rendered log message.

    Usage:
        _sf = SensitiveFilter([api_key, password, totp_secret])
        for h in logging.root.handlers:
            h.addFilter(_sf)
    """

    REPLACEMENT = "***REDACTED***"

    def __init__(self, sensitive_values):
        super().__init__()
        # Drop None/empty, dedupe, and sort longest-first so overlapping
        # values redact fully before shorter substrings match.
        vals = {str(v) for v in (sensitive_values or []) if v}
        self._values = sorted(vals, key=len, reverse=True)

    def filter(self, record):
        """Always allow the record, but redact any sensitive value present
        in the fully-formatted message. Never raises."""
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = msg
        for v in self._values:
            if v and v in redacted:
                redacted = redacted.replace(v, self.REPLACEMENT)
        if redacted != msg:
            record.msg = redacted
            record.args = ()  # already interpolated into record.msg
        return True
