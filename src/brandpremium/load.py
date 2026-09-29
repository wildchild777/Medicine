"""Load the raw A-Z dataset with predictable column names and an explicit encoding.

Everything downstream assumes the column names produced here, so this is the only
module that mentions the raw file's original headers.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

RAW_AZ = Path("data") / "raw" / "az" / "A_Z_medicines_dataset_of_India.csv"

# The raw price header is "price(<rupee sign>)". Dropping the non-ASCII character
# leaves a bare "price", which loses the currency, so name it explicitly.
EXPLICIT_RENAMES = {"price": "price_inr"}


def snake_case(name: str) -> str:
    """Normalise a column header to lowercase ASCII snake_case.

    Non-ASCII characters are dropped rather than transliterated, so the rupee sign
    disappears instead of turning into mojibake under cp1252.
    """
    ascii_only = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^0-9a-z]+", "_", ascii_only.lower()).strip("_")


def _text_columns(df: pd.DataFrame) -> list[str]:
    """Columns pandas is storing as text.

    pandas 3.x infers a dedicated str dtype where 2.x used object, so
    select_dtypes("object") silently matches nothing here.
    """
    return [c for c in df.columns if df[c].dtype.kind in ("O", "U", "T")]


def load_az(path: Path | str = RAW_AZ) -> pd.DataFrame:
    """Read the raw CSV with normalised columns and trimmed text."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. The raw data is not committed - see "
            "docs/data-sources.md for the Kaggle URL and the SHA256 to check against."
        )

    df = pd.read_csv(path, encoding="utf-8")
    df.columns = [snake_case(c) for c in df.columns]
    df = df.rename(columns=EXPLICIT_RENAMES)

    for col in _text_columns(df):
        df[col] = df[col].str.strip()

    return df
