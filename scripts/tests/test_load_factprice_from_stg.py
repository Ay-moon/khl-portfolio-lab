from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from load_factprice_from_stg import (
    StgPriceRow,
    canonical_security_name,
    deduplicate_rows,
    make_unique_ticker,
    parse_decimal_text,
    parse_volume_text,
)


class LoadFactPriceFromStgTests(unittest.TestCase):
    def test_parse_decimal_text_fr_formats(self) -> None:
        self.assertAlmostEqual(parse_decimal_text("2 034,500"), 2034.5, places=6)
        self.assertAlmostEqual(parse_decimal_text("158,000 (c)"), 158.0, places=6)
        self.assertAlmostEqual(parse_decimal_text("1.234,56"), 1234.56, places=6)
        self.assertIsNone(parse_decimal_text(""))

    def test_parse_volume_text(self) -> None:
        self.assertEqual(parse_volume_text("704373"), 704373)
        self.assertEqual(parse_volume_text("7 043"), 7043)
        self.assertIsNone(parse_volume_text("-1"))

    def test_canonical_security_name(self) -> None:
        name = canonical_security_name(
            libelle="SRD DASSAULT AVIATION",
            sous_jacent=None,
            ss_jacent=None,
            produit=None,
            isin="FR0000121725",
        )
        self.assertEqual(name, "DASSAULT AVIATION")

    def test_make_unique_ticker(self) -> None:
        existing = {"DANONE"}
        reserved = set()
        t1 = make_unique_ticker("Danone", existing, reserved, max_len=20)
        t2 = make_unique_ticker("Danone", existing, reserved, max_len=20)
        self.assertNotEqual(t1, t2)
        self.assertTrue(t1.startswith("DANONE"))
        self.assertTrue(t2.startswith("DANONE"))

    def test_deduplicate_rows_keeps_latest(self) -> None:
        older = StgPriceRow(
            stg_id=10,
            date_key=20260203,
            source_dt=datetime(2026, 2, 3, 12, 0, 0),
            canonical_name="DANONE",
            produit_type="ACTION",
            close_price=10.0,
            volume=1,
            load_ts=datetime(2026, 2, 3, 12, 1, 0),
        )
        newer = StgPriceRow(
            stg_id=11,
            date_key=20260203,
            source_dt=datetime(2026, 2, 3, 12, 0, 0),
            canonical_name="DANONE",
            produit_type="ACTION",
            close_price=11.0,
            volume=2,
            load_ts=datetime(2026, 2, 3, 12, 2, 0),
        )
        rows = deduplicate_rows([older, newer])
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].close_price, 11.0, places=6)


if __name__ == "__main__":
    unittest.main()

