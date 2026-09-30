"""Tests for the composition and pack-size parsers.

Every string below is a real value from short_composition1, copied verbatim.
The unit tests never read data/raw; the one check at the bottom that does is
skipped automatically when the file isn't there.
"""

import pytest

from brandpremium.equivalence import filter_comparable
from brandpremium.load import RAW_AZ, load_az
from brandpremium.parse import Strength, parse_strength, split_composition

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


STRENGTHS = [
    # The ordinary case, and the other mass units.
    ("500mg", Strength(500.0, "mg")),
    ("2.5mg", Strength(2.5, "mg")),
    ("100mcg", Strength(100.0, "mcg")),
    ("1.4gm", Strength(1.4, "g")),          # gm and g are the same unit

    # Concentrations. The denominator is what makes these different from a plain
    # mass - 200mg/5ml in a 100ml bottle is not 200mg.
    ("200mg/5ml", Strength(200.0, "mg", 5.0, "ml")),
    ("10mg/ml", Strength(10.0, "mg", 1.0, "ml")),   # no number means one
    ("75mg/3 ml", Strength(75.0, "mg", 3.0, "ml")), # stray space inside
    ("0.25mg/gm", Strength(0.25, "mg", 1.0, "g")),

    # Percentages. w/w and w/v are not interchangeable: one is per gram of cream,
    # the other per millilitre of solution, so the distinction has to survive.
    ("20% w/w", Strength(20.0, "%w/w")),
    ("0.18% w/v", Strength(0.18, "%w/v")),
    ("20%", Strength(20.0, "%")),

    # Activity units, and the written-out multipliers.
    ("2.5IU", Strength(2.5, "iu")),
    ("75i.u", Strength(75.0, "iu")),        # same unit, different spelling
    ("1Million IU", Strength(1e6, "iu")),
    ("2Billion Spores", Strength(2e9, "spores")),
    ("6Lac units", Strength(600000.0, "units")),
    ("100000AU", Strength(100000.0, "au")),
]

# Everything in the dataset that parse_strength cannot read. "NA" is the dataset's
# own way of saying the strength is unknown; the rest are genuinely exotic units.
# Listing them here means a new failure shows up as a test failure.
UNPARSEABLE = {
    "NA",
    "6.5ccid50",
    "1000ccid50",
    "1000000ccid50",
    "300mg I/ml",
    "370mg I/ml",
}


class TestParseStrength:
    @pytest.mark.parametrize("text,expected", STRENGTHS)
    def test_reads_the_amount_and_unit(self, text, expected):
        assert parse_strength(text) == expected

    @pytest.mark.parametrize("text", sorted(UNPARSEABLE))
    def test_returns_none_for_what_it_cannot_read(self, text):
        assert parse_strength(text) is None

    def test_plain_strengths_have_no_denominator(self):
        result = parse_strength("500mg")
        assert result.per_amount is None and result.per_unit is None

    def test_concentration_keeps_both_halves(self):
        result = parse_strength("200mg/5ml")
        assert (result.amount, result.unit) == (200.0, "mg")
        assert (result.per_amount, result.per_unit) == (5.0, "ml")

    def test_units_are_lowercase_and_unspaced(self):
        for text, _ in STRENGTHS:
            unit = parse_strength(text).unit
            assert unit == unit.lower() and " " not in unit, text


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

    def test_only_the_known_strengths_are_unreadable(self):
        kept, _ = filter_comparable(load_az())
        strengths = kept["short_composition1"].map(lambda t: split_composition(t)[1])

        unreadable = {t for t in strengths.drop_duplicates() if parse_strength(t) is None}

        assert unreadable == UNPARSEABLE

    def test_parser_covers_almost_every_row(self):
        kept, _ = filter_comparable(load_az())
        strengths = kept["short_composition1"].map(lambda t: split_composition(t)[1])

        readable = strengths.map(lambda t: parse_strength(t) is not None)

        # 1.37% unreadable, nearly all of it the dataset's own "NA". If this drops,
        # something in the grammar has regressed.
        assert readable.mean() > 0.98
