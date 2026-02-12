"""Text normalization for OCR/reference matching.

Implements normalize_strict and normalize_soft exactly per specification.

Security note: this module must not log raw text.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

# Regex required by spec: "[ ]*\n+[ ]*" -> " "
_NEWLINES_WITH_ASCII_SPACES_RE: Final[re.Pattern[str]] = re.compile(r"[ ]*\n+[ ]*", flags=re.UNICODE)

# Soft normalization: collapse ANY whitespace runs to a single ASCII space.
# (Applied only in normalize_soft, after strict.)
_WHITESPACE_RUN_RE: Final[re.Pattern[str]] = re.compile(r"\s+", flags=re.UNICODE)

# Curly quotes mapping per spec (curly -> straight).
# GAP: the spec doesn't enumerate all possible quote codepoints.
# We map the common Unicode curly single/double quotes and leave all others unchanged (fail-closed).
_QUOTES_MAP: Final[dict[str, str]] = {
    "\u2018": "'",  # LEFT SINGLE QUOTATION MARK
    "\u2019": "'",  # RIGHT SINGLE QUOTATION MARK
    "\u201A": "'",  # SINGLE LOW-9 QUOTATION MARK
    "\u201B": "'",  # SINGLE HIGH-REVERSED-9 QUOTATION MARK
    "\u201C": '"',  # LEFT DOUBLE QUOTATION MARK
    "\u201D": '"',  # RIGHT DOUBLE QUOTATION MARK
    "\u201E": '"',  # DOUBLE LOW-9 QUOTATION MARK
    "\u201F": '"',  # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
}


def _rstrip_ascii_space_only(text: str) -> str:
    """Remove only trailing U+0020 ASCII spaces.

    Must NOT remove tabs, NBSP, or other whitespace characters.
    """
    # Equivalent to rstrip(' ') but implemented explicitly for clarity.
    i = len(text)
    while i > 0 and text[i - 1] == " ":
        i -= 1
    return text[:i]


def map_quotes_to_ascii(text: str) -> str:
    """Map curly quotes to straight ASCII quotes.

    Only the characters defined in _QUOTES_MAP are replaced.
    """
    if not text:
        return text
    # translate is deterministic and efficient
    return text.translate(str.maketrans(_QUOTES_MAP))


def normalize_strict(text: str | None) -> str:
    """Strict normalization used for AUTO-PASS eligibility.

    MUST follow spec exactly:
      - unicode_nfc
      - rstrip ASCII space only
      - CRLF -> LF
      - CR -> LF
      - replace_regex("[ ]*\n+[ ]*", " ")
      - unicode_casefold
      - map_quotes_to_ascii

    Strict MUST NOT:
      - delete/normalize punctuation
      - collapse internal double spaces
      - change hyphens/dashes
      - "fix" OCR errors
    """
    if text is None:
        return ""

    # 1) unicode_nfc
    t = unicodedata.normalize("NFC", text)

    # 2) rstrip ASCII space only
    t = _rstrip_ascii_space_only(t)

    # 3) "\r\n" -> "\n"
    t = t.replace("\r\n", "\n")

    # 4) "\r" -> "\n"
    t = t.replace("\r", "\n")

    # 5) replace_regex("[ ]*\n+[ ]*", " ")
    t = _NEWLINES_WITH_ASCII_SPACES_RE.sub(" ", t)

    # 6) unicode_casefold
    t = t.casefold()

    # 7) map_quotes_to_ascii
    t = map_quotes_to_ascii(t)

    return t


def normalize_soft(text: str | None) -> str:
    """Soft normalization used for similarity/ranking ONLY.

    MUST follow spec:
      - normalize_strict
      - collapse_whitespace_runs_to_single_space

    Soft MUST NOT influence auto-pass decisions.
    """
    t = normalize_strict(text)
    # Collapse runs of ANY whitespace (tabs, NBSP, etc.) into a single ASCII space.
    # Do not add extra stripping beyond what strict already performed.
    t = _WHITESPACE_RUN_RE.sub(" ", t)
    return t
