"""Decide which products can honestly be compared with each other.

The A-Z dataset stores composition in exactly two columns, so a product with three
or more ingredients is silently truncated to its first two. Rumatab SP (~5 rupees)
and Tenoflam Plus (~199 rupees) are different three-ingredient drugs that both
present as the same two-ingredient one, so grouping on composition alone would
compare products that are not substitutes.

We therefore analyse single-ingredient products only, which is the largest subset
the data describes completely. A product whose second column is empty has exactly
one ingredient and cannot have been truncated, so there is no separate truncation
check; name_claims_two_molecules only guards that assumption in case the data
changes.

Everything here works on plain values except filter_comparable, so the tests run
without the raw data.
"""

from __future__ import annotations

import re

import pandas as pd

_MASS = r"(?:mg|mcg|gm|g)"
_VOL = r"(?:ml|l)"

# A mass over a mass ("100mg/325mg") means the brand name is advertising two
# molecules. A mass over a volume ("200mg/5ml") is a single concentration.
NAME_CLAIMS_TWO_MOLECULES = re.compile(
    rf"\d+(?:\.\d+)?\s*{_MASS}\s*/\s*\d+(?:\.\d+)?\s*{_MASS}\b", re.IGNORECASE
)


def name_claims_two_molecules(name: str | None) -> bool:
    """True if the brand name advertises two separate molecule strengths.

    >>> name_claims_two_molecules("Lepod O 200mg/200mg Tablet")
    True
    >>> name_claims_two_molecules("Azithral Junior 200mg/5ml Drop")
    False

    False for every single-ingredient row in the 2022 snapshot.
    """
    return bool(name and NAME_CLAIMS_TWO_MOLECULES.search(name))


def ingredient_count(comp1: str | None, comp2: str | None) -> int:
    """How many ingredients the dataset records for a product: 0, 1 or 2.

    None, empty strings and whitespace-only strings all count as absent. Missing
    cells arrive from pandas as NaN rather than None, hence pd.isna.
    """
    count = 0
    if not pd.isna(comp1) and comp1.strip():
        count += 1
    if not pd.isna(comp2) and comp2.strip():
        count += 1
    return count


def is_comparable(
    comp1: str | None,
    comp2: str | None,
    is_discontinued: bool,
    price_inr: float | None,
) -> bool:
    """True if a product can enter a price comparison.

    It needs exactly one ingredient, has to still be on sale, and needs a usable
    price. Every comparison against NaN is False, so `price_inr > 0` covers
    missing, zero and negative prices in one condition.
    """
    return (
        ingredient_count(comp1, comp2) == 1
        and not is_discontinued
        and price_inr > 0
    )


def filter_comparable(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return the rows safe to compare, plus a count of what was dropped and why.

    The reasons are mutually exclusive, so they add up to total_in. These counts
    get reported rather than kept internally, so they have to stay honest.
    """
    # fillna("") keeps every value a real string, so the masks below can't pick up
    # a missing value.
    comp1 = df["short_composition1"].fillna("").str.strip()
    comp2 = df["short_composition2"].fillna("").str.strip()

    n_ingredients = (comp1 != "").astype(int) + (comp2 != "").astype(int)
    single = n_ingredients == 1
    live = ~df["is_discontinued"]
    priced = df["price_inr"] > 0  # NaN > 0 is False, so missing prices go too

    keep = single & live & priced

    counts = {
        "total_in": len(df),
        "no_composition": int((n_ingredients == 0).sum()),
        "combination": int((n_ingredients == 2).sum()),
        "discontinued": int((single & ~live).sum()),
        "bad_price": int((single & live & ~priced).sum()),
        "kept": int(keep.sum()),
    }
    return df[keep].copy(), counts
