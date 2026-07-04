"""
Input guardrails: candidate ID validation, HTML stripping,
prompt-injection detection and redaction, length enforcement.
"""
import re
from typing import Tuple

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|prior|above)\s+instructions?",
    r"disregard\s+(the|your|all)\s+(above|previous|prior|instructions?)",
    r"you\s+are\s+now\s+",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(?:if\s+you(?:'re| are)|a[n]?\s+\w+\s+(?:without|that))",
    r"forget\s+(?:everything|all|your|previous)\b",
    r"jailbreak",
    r"<\s*script[\s>]",
    r"\[INST\]",
    r"###\s*Human\s*:",
    r"<\|(?:system|im_start|endoftext)\|>",
    r"prompt\s*injection",
    r"new\s+instructions?\s*:",
    r"override\s+(the\s+)?(system|instructions?|prompt)",
]

_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)
_CANDIDATE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-\.]{1,60}$")

_MAX_LEN: dict = {
    "candidate_id": 60,
    "jd": 8000,
    "resume": 8000,
    "answer": 3000,
}


def validate_candidate_id(cid: str) -> Tuple[bool, str]:
    """Returns (is_valid, error_message). Allows alphanumeric, _ - . up to 60 chars."""
    cid = cid.strip()
    if not cid:
        return False, "Candidate ID cannot be empty."
    if not _CANDIDATE_ID_RE.match(cid):
        return False, "Candidate ID may only contain letters, numbers, _ - . (max 60 chars)."
    return True, ""


def sanitize(text: str, field: str = "answer") -> Tuple[str, list]:
    """
    Returns (clean_text, warnings).
    Steps: pre-truncate to 20 000 chars → strip HTML → detect/redact injection → enforce field limit.
    """
    warnings: list = []

    # Pre-truncate to avoid ReDoS on pathological inputs
    working = text[:20_000]

    # Strip HTML tags (bounded lookahead to avoid catastrophic backtracking)
    clean = re.sub(r"<[^>]{0,500}>", "", working)

    # Detect and redact injection patterns
    if _INJECTION_RE.search(clean):
        warnings.append("Suspicious input pattern detected and redacted.")
        clean = _INJECTION_RE.sub("[redacted]", clean)

    # Enforce field-level max length
    max_len = _MAX_LEN.get(field, 3000)
    if len(clean) > max_len:
        clean = clean[:max_len]
        warnings.append(f"Input truncated to {max_len} characters.")

    return clean.strip(), warnings
