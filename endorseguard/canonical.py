"""Value canonicalisation: the same value must compare equal no matter how it is written,
and look-alike values (homoglyphs) must be detectable."""

import re
import unicodedata

ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)

# Small subset of Unicode TR39 confusables: characters that render like Latin letters.
CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "і": "i",
    "ј": "j", "ԁ": "d", "ӏ": "l", "һ": "h", "ѕ": "s", "ԛ": "q", "ԝ": "w",
    "А": "a", "В": "b", "Е": "e", "К": "k", "М": "m", "Н": "h", "О": "o", "Р": "p",
    "С": "c", "Т": "t", "Х": "x",
    "α": "a", "ο": "o", "ν": "v", "ρ": "p", "ι": "i", "κ": "k", "τ": "t",
    "0": "o", "1": "l", "I": "l", "|": "l",
})

EMAIL_RE = re.compile(r"[^\s<>\"',;:()]+@[^\s<>\"',;:()]+\.[^\s<>\"',;:()]+")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?\b")


def canonical(value: str, kind: str) -> str:
    """Normal form used for every comparison (NFKC, no invisible characters)."""
    v = unicodedata.normalize("NFKC", str(value)).translate(ZERO_WIDTH).strip()
    if kind == "email":
        return v.lower().rstrip(".")
    if kind == "iban":
        return v.replace(" ", "").upper()
    return v


def skeleton(value: str, kind: str) -> str:
    """Visual skeleton: two values with the same skeleton look the same to a human."""
    return canonical(value, kind).translate(CONFUSABLES).lower()


def has_non_ascii(value: str) -> bool:
    return any(ord(ch) > 127 for ch in value)


def iban_checksum_ok(iban: str) -> bool:
    """ISO 13616 mod-97 check."""
    s = canonical(iban, "iban")
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{8,30}", s):
        return False
    digits = "".join(str(int(ch, 36)) for ch in s[4:] + s[:4])
    return int(digits) % 97 == 1


def find_values(text: str, kind: str) -> list[str]:
    """Extract candidate emails / IBANs from free text, in canonical form."""
    text = unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH)
    pattern = EMAIL_RE if kind == "email" else IBAN_RE
    return [canonical(m, kind) for m in pattern.findall(text)]
