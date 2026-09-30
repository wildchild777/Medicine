"""Tests for the composition and pack-size parsers.

Every string below is a real value from short_composition1, copied verbatim.
The unit tests never read data/raw; the one check at the bottom that does is
skipped automatically when the file isn't there.
"""

import pytest

from brandpremium.equivalence import filter_comparable
from brandpremium.load import RAW_AZ, load_az
from brandpremium.parse import split_composition

# text, expected molecule, expected strength text
CASES = [
    # The ordinary shape - 98% of rows look like this.
    ("Paracetamol (500mg)", "Paracetamol", "500mg"),

    # Real row, real double space. The name must come back trimmed or grouping
    # will treat this as a different molecule from "Amoxycillin".
    ("Amoxycillin  (500mg)", "Amoxycillin", "500mg"),

    # 1,390 rows carry a qualifier in a first set of brackets. The strength is
    # the LAST group; the qualifier stays part of the name, brackets and all.
    ("Progesterone (Natural Micronized) (25mg)", "Progesterone (Natural Micronized)", "25mg"),
    ("Doxorubicin (Plain) (50mg)", "Doxorubicin (Plain)", "50mg"),

    # No space before the first bracket.
    ("Thiamine(Vitamin B1) (100mg)", "Thiamine(Vitamin B1)", "100mg"),

    # A concentration, not two values. Keep it in one piece - working out what
    # 200mg/5ml means needs the pack volume, and that happens later.
    ("Azithromycin (200mg/5ml)", "Azithromycin", "200mg/5ml"),

    # The dataset writes an unknown strength as the literal text "NA". Splitting
    # is still the right answer here; deciding it's unusable comes later.
    ("Cefixime (NA)", "Cefixime", "NA"),

    # A percentage, and a unit that isn't a mass at all.
    ("Azelaic Acid (20% w/w)", "Azelaic Acid", "20% w/w"),
    ("Rabies vaccine, Human (2.5IU)", "Rabies vaccine, Human", "2.5IU"),
]


class TestSplitComposition:
    @pytest.mark.parametrize("text,molecule,strength", CASES)
    def test_splits_correctly(self, text, molecule, strength):
        assert split_composition(text) == (molecule, strength)

    def test_returns_an_actual_tuple(self):
        assert isinstance(split_composition("Paracetamol (500mg)"), tuple)

    @pytest.mark.parametrize("text", ["no brackets here", "Paracetamol", ""])
    def test_returns_none_when_there_is_nothing_to_split(self, text):
        assert split_composition(text) is None

    def test_strength_never_contains_a_bracket(self):
        # Catches the qualifier bug: splitting on the wrong group leaves the
        # strength looking like "Natural Micronized (25mg".
        for text, _, _ in CASES:
            _, strength = split_composition(text)
            assert "(" not in strength and ")" not in strength, text

    def test_name_has_no_leading_or_trailing_space(self):
        for text, _, _ in CASES:
            name, _ = split_composition(text)
            assert name == name.strip(), repr(text)


@pytest.mark.skipif(not RAW_AZ.exists(), reason="raw data not downloaded")
class TestAgainstRealData:
    """Not a unit test - a check that the rules above hold across all 5,754
    distinct strings. Skipped on a fresh clone, where data/raw is empty."""

    def test_every_composition_parses(self):
        kept, _ = filter_comparable(load_az())

        unparsed = [
            text
            for text in kept["short_composition1"].drop_duplicates()
            if split_composition(text) is None
        ]

        # Collecting them first means a failure lists every bad string at once
        # rather than stopping at the first.
        assert unparsed == []
