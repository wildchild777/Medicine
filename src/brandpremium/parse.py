"""Turn composition and pack-size strings into numbers.

Composition strings always end in a parenthesised strength. About 1% of them carry
a qualifier in a second set of brackets first - "Progesterone (Natural Micronized)
(25mg)" - so the strength is the last group, not the first.
"""

from __future__ import annotations


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
