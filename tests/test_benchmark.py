from __future__ import annotations

import unittest

from app.benchmark import BenchmarkRun, summarize


class BenchmarkSummaryTest(unittest.TestCase):
    def test_calculates_speedup_and_efficiency(self) -> None:
        runs = [
            BenchmarkRun(1, 1, "2024,2025", 1000, 5000, 10.0, 100.0),
            BenchmarkRun(1, 2, "2024,2025", 1000, 5000, 12.0, 83.33),
            BenchmarkRun(2, 1, "2024,2025", 1000, 5000, 6.0, 166.67),
            BenchmarkRun(2, 2, "2024,2025", 1000, 5000, 5.0, 200.0),
        ]

        summary = summarize(runs)

        self.assertEqual([item["workers"] for item in summary], [1, 2])
        self.assertAlmostEqual(summary[0]["average_seconds"], 11.0)
        self.assertAlmostEqual(summary[1]["average_seconds"], 5.5)
        self.assertAlmostEqual(summary[1]["speedup"], 2.0)
        self.assertAlmostEqual(summary[1]["efficiency"], 1.0)


if __name__ == "__main__":
    unittest.main()
