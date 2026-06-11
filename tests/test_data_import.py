from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.data_import import DataImportManager, ImportAlreadyRunningError


class DataImportManagerTest(unittest.TestCase):
    def test_reports_available_and_loaded_years(self) -> None:
        manager = DataImportManager(Path("/data"))

        result = manager.list_years(
            available_years={2023, 2024, 2025},
            loaded_years={2024, 2025},
        )

        self.assertEqual(
            result,
            [
                {"ano": 2023, "carregado": False},
                {"ano": 2024, "carregado": True},
                {"ano": 2025, "carregado": True},
            ],
        )

    def test_rejects_a_second_import_while_one_is_running(self) -> None:
        manager = DataImportManager(Path("/data"))
        manager.start([2024])

        with self.assertRaises(ImportAlreadyRunningError):
            manager.start([2025])

    def test_downloads_before_loading_selected_years(self) -> None:
        events: list[tuple] = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager = DataImportManager(root)
            manager.start([2024, 2025])

            def download(years: list[int], output_root: Path) -> None:
                events.append(("download", years, output_root))
                for year in years:
                    (output_root / str(year)).mkdir(parents=True)

            def load(year_dirs: list[Path]) -> None:
                events.append(
                    ("load", [path.name for path in year_dirs])
                )

            manager.run(download=download, load=load)

        self.assertEqual(
            events,
            [
                ("download", [2024, 2025], root),
                ("load", ["2024", "2025"]),
            ],
        )
        self.assertEqual(manager.status()["estado"], "concluido")

    def test_records_import_errors(self) -> None:
        manager = DataImportManager(Path("/data"))
        manager.start([2024])

        def fail_download(_: list[int], __: Path) -> None:
            raise RuntimeError("falha simulada")

        manager.run(download=fail_download, load=lambda _: None)

        status = manager.status()
        self.assertEqual(status["estado"], "erro")
        self.assertEqual(status["erro"], "falha simulada")


if __name__ == "__main__":
    unittest.main()
