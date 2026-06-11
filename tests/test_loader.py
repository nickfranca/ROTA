from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from app.loader import _clean_chunk, discover_year_dirs


class LoaderTest(unittest.TestCase):
    def test_clean_chunk_normalizes_types_and_adds_year(self) -> None:
        chunk = pd.DataFrame(
            {
                "id": ["1", "N/A"],
                "km": ["10,5", ""],
                "data_inversa": ["2025-01-02", "invalida"],
                "uf": ["TO", "GO"],
            }
        )

        cleaned = _clean_chunk(chunk, 2025)

        self.assertEqual(list(cleaned["ano_fonte"]), [2025, 2025])
        self.assertEqual(cleaned.loc[0, "id"], 1)
        self.assertTrue(pd.isna(cleaned.loc[1, "id"]))
        self.assertEqual(cleaned.loc[0, "km"], 10.5)
        self.assertTrue(pd.isna(cleaned.loc[1, "km"]))
        self.assertEqual(str(cleaned.loc[0, "data_inversa"]), "2025-01-02")
        self.assertTrue(pd.isna(cleaned.loc[1, "data_inversa"]))

    def test_discover_year_dirs_filters_and_orders_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "2025").mkdir()
            (root / "2024").mkdir()
            (root / "output").mkdir()

            all_years = discover_year_dirs(root)
            selected = discover_year_dirs(root, {2025})

        self.assertEqual([path.name for path in all_years], ["2024", "2025"])
        self.assertEqual([path.name for path in selected], ["2025"])


if __name__ == "__main__":
    unittest.main()
