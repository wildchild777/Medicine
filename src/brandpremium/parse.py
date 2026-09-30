"""Turn composition and pack-size strings into numbers.

Composition strings always end in a parenthesised strength. About 1% of them carry
a qualifier in a second set of brackets first - "Progesterone (Natural Micronized)
(25mg)" - so the strength is the last group, not the first.

Strengths come in two shapes: a plain amount ("500mg") and a concentration
("200mg/5ml"), which needs the pack volume before it means anything. Parsing stops
at reading them; converting to a mass happens later, where the pack is known.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class Strength(NamedTuple):
    """An amount and its unit, plus the denominator when it's a concentration.

    "500mg"     -> Strength(500.0, "mg")
    "200mg/5ml" -> Strength(200.0, "mg", 5.0, "ml")
    "10mg/ml"   -> Strength(10.0, "mg", 1.0, "ml")
    """

    amount: float
    unit: str
    per_amount: float | None = None
    per_unit: str | None = None


# Spelled out in the data as "1Million IU", "2Billion Spores", "6Lac units".
MULTIPLIERS = {"million": 1e6, "billion": 1e9, "lac": 1e5}

# Same unit, different spellings.
UNIT_ALIASES = {"gm": "g", "i.u": "iu"}

_NUM = r"\d+(?:\.\d+)?"

# The "% w/w" alternative has to come before the bare "%", or the w/w half is left
# behind and the match fails. Everything after the slash is optional, and so is the
# number within it - "mg/ml" means the same as "mg/1ml".
_STRENGTH = re.compile(
    rf"^(?P<amount>{_NUM})\s*"
    rf"(?P<mult>million|billion|lac)?\s*"
    rf"(?P<unit>%\s*(?:w/w|w/v|v/v)|%|[a-z][a-z.]*)"
    rf"(?:\s*/\s*(?P<per_amount>{_NUM})?\s*(?P<per_unit>[a-z][a-z.]*))?$"
)


def split_composition(text: str) -> tuple[str, str] | None:
    """Split a composition string into (molecule, strength text).

    "Paracetamol (500mg)"                      -> ("Paracetamol", "500mg")
    "Progesterone (Natural Micronized) (25mg)" -> ("Progesterone (Natural Micronized)", "25mg")

    Returns None if there is no parenthesised group to take.
    """
    # rpartition splits on the last "(" rather than the first, which is what keeps
    # the qualifier with the molecule name instead of mistaking it for a strength.
    name, bracket, strength = text.strip().rpartition("(")
    if not bracket or not strength.endswith(")"):
        return None

    return name.strip(), strength[:-1].strip()


def _canonical_unit(unit: str) -> str:
    """Lowercase, no internal spaces, and one spelling per unit."""
    unit = re.sub(r"\s+", "", unit.lower())
    return UNIT_ALIASES.get(unit, unit)


def parse_strength(text: str) -> Strength | None:
    """Read a strength string into an amount and a unit.

    Returns None for anything that doesn't fit the grammar, which in this dataset
    means the literal "NA" plus a handful of exotic units like ccid50. Callers are
    expected to count those rather than guess at them.
    """
    match = _STRENGTH.match(" ".join(text.split()).lower())
    if match is None:
        return None

    amount = float(match["amount"]) * MULTIPLIERS.get(match["mult"], 1)

    per_amount = None
    per_unit = None
    if match["per_unit"]:
        # "mg/ml" leaves the number out, and means one of whatever follows.
        per_amount = float(match["per_amount"]) if match["per_amount"] else 1.0
        per_unit = _canonical_unit(match["per_unit"])

    return Strength(amount, _canonical_unit(match["unit"]), per_amount, per_unit)
