"""Tests for the comparability filter.

The fixtures are verbatim rows from the A-Z dataset, mess included - the double
space in "Amoxycillin  (500mg)" is real. Nothing here reads data/raw, so the suite
runs on a fresh clone.
"""

import math

import pandas as pd
import pytest

from brandpremium.equivalence import (
    filter_comparable,
    ingredient_count,
    is_comparable,
    name_claims_two_molecules,
)

# name, short_composition1, short_composition2, pack_size_label, price_inr
ONE_INGREDIENT = [
    ("Babymol 500mg Tablet", "Paracetamol (500mg)", math.nan, "strip of 10 tablets", 2.50),
    ("Cefjoy 200mg Tablet", "Cefpodoxime Proxetil (200mg)", math.nan, "strip of 10 tablets", 1.25),
    ("Accardi MR Tablet MR", "Trimetazidine (35mg)", math.nan, "strip of 10 tablets", 110.00),
    ("Azithral Junior 200mg/5ml Drop", "Azithromycin (200mg/5ml)", math.nan, "bottle of 15 ml Drop", 28.61),
]

TWO_INGREDIENTS = [
    ("Augmentin 625 Duo Tablet", "Amoxycillin  (500mg)", "Clavulanic Acid (125mg)", "strip of 10 tablets", 223.42),
    ("Lepod O 200mg/200mg Tablet", "Cefpodoxime Proxetil (200mg)", "Ofloxacin (200mg)", "strip of 10 tablets", 22.00),
    # Actually three ingredients - the dataset drops serratiopeptidase. This row is
    # why the project is scoped to single ingredients.
    ("Rumatab SP 100 mg/325 mg/15 mg Tablet", "Aceclofenac (100mg)", "Paracetamol (325mg)", "strip of 10 tablets", 5.23),
]


class TestIngredientCount:
    def test_counts_one(self):
        for name, comp1, comp2, pack, price in ONE_INGREDIENT:
            assert ingredient_count(comp1, comp2) == 1, name

    def test_counts_two(self):
        for name, comp1, comp2, pack, price in TWO_INGREDIENTS:
            assert ingredient_count(comp1, comp2) == 2, name

    @pytest.mark.parametrize("absent", [None, "", "   ", math.nan])
    def test_absent_second_column(self, absent):
        assert ingredient_count("Paracetamol (500mg)", absent) == 1


class TestNameClaimsTwoMolecules:
    def test_mass_over_mass_is_two_molecules(self):
        assert name_claims_two_molecules("Lepod O 200mg/200mg Tablet") is True

    def test_mass_over_volume_is_one_concentration(self):
        assert name_claims_two_molecules("Azithral Junior 200mg/5ml Drop") is False


class TestIsComparable:
    def test_accepts_plain_single_ingredient(self):
        name, comp1, comp2, pack, price = ONE_INGREDIENT[0]
        assert is_comparable(comp1, comp2, False, price) is True

    def test_rejects_combination(self):
        # On sale and sensibly priced, so the second ingredient is the only thing
        # that can be causing the rejection.
        name, comp1, comp2, pack, price = TWO_INGREDIENTS[0]
        assert is_comparable(comp1, comp2, False, price) is False

    def test_rejects_discontinued(self):
        # Single ingredient and a good price, so the same isolation applies here.
        name, comp1, comp2, pack, price = ONE_INGREDIENT[0]
        assert is_comparable(comp1, comp2, True, price) is False

    @pytest.mark.parametrize("bad_price", [0.0, -1.0, math.nan])
    def test_rejects_unusable_price(self, bad_price):
        # is_discontinued has to be False, or the price is never reached.
        name, comp1, comp2, pack, price = ONE_INGREDIENT[0]
        assert is_comparable(comp1, comp2, False, bad_price) is False


class TestFilterComparable:
    """Eight hand-built rows, one per outcome."""

    # short_composition1, short_composition2, is_discontinued, price_inr
    ROWS = [
        ("Paracetamol (500mg)", None, False, 2.50),                          # keep
        ("Cefpodoxime Proxetil (200mg)", None, False, 1.25),                 # keep
        ("Amoxycillin  (500mg)", "Clavulanic Acid (125mg)", False, 223.42),  # combination
        ("Aceclofenac (100mg)", "Paracetamol (325mg)", True, 5.23),          # combination
        ("Pantoprazole (40mg)", None, True, 58.00),                          # discontinued
        ("Rabeprazole (20mg)", None, False, 0.0),                            # bad price
        ("Levocetirizine (5mg)", None, False, math.nan),                     # bad price
        ("", None, False, 33.00),                                            # no composition
    ]

    def frame(self):
        return pd.DataFrame(
            self.ROWS,
            columns=["short_composition1", "short_composition2",
                     "is_discontinued", "price_inr"],
        )

    def test_counts_every_reason(self):
        kept, counts = filter_comparable(self.frame())
        assert counts == {
            "total_in": 8,
            "no_composition": 1,
            "combination": 2,
            "discontinued": 1,
            "bad_price": 2,
            "kept": 2,
        }

    def test_reasons_add_up(self):
        # A failure here means a row is counted under two reasons at once.
        _, c = filter_comparable(self.frame())
        dropped = c["no_composition"] + c["combination"] + c["discontinued"] + c["bad_price"]
        assert dropped + c["kept"] == c["total_in"]

    def test_keeps_the_right_rows(self):
        kept, _ = filter_comparable(self.frame())
        assert kept["short_composition1"].tolist() == [
            "Paracetamol (500mg)",
            "Cefpodoxime Proxetil (200mg)",
        ]

    def test_a_discontinued_combination_is_counted_once(self):
        # Row 4 is both a combination and discontinued, and belongs in one bucket.
        _, c = filter_comparable(self.frame())
        assert c["combination"] == 2 and c["discontinued"] == 1

    def test_implausible_price_is_kept(self):
        # Cefjoy really is listed at 1.25 rupees against a group 1st percentile of
        # 90. That is a wrong price rather than an unusable one, and it belongs
        # wherever the spread gets computed, not deleted here.
        kept, _ = filter_comparable(self.frame())
        assert 1.25 in kept["price_inr"].tolist()

    def test_does_not_mutate_the_input(self):
        df = self.frame()
        before = len(df)
        filter_comparable(df)
        assert len(df) == before
