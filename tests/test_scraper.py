from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from prf_scraper import (
    InvalidArchiveError,
    discover_available_years,
    discover_datasets,
    extract_single_csv,
)


class ScraperTest(unittest.TestCase):
    def test_discovers_the_three_dataset_kinds(self) -> None:
        html = """
        <table>
          <tr><td>Documento CSV de acidentes 2025 agrupados por ocorrência</td>
              <td><a href="https://drive.google.com/a">Baixar planilha</a></td></tr>
          <tr><td>Documento CSV de acidentes 2025 agrupados por pessoa</td>
              <td><a href="https://drive.google.com/b">Baixar planilha</a></td></tr>
          <tr><td>Documento CSV de acidentes 2025 agrupados por pessoa -
                  todas as causas e tipos de acidentes</td>
              <td><a href="https://drive.google.com/c">Baixar planilha</a></td></tr>
        </table>
        """

        datasets = discover_datasets(html, 2025)

        self.assertEqual(
            set(datasets),
            {"ocorrencias", "pessoas", "pessoas_todas_causas"},
        )

    def test_extracts_a_single_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "data.zip"
            destination = root / "output.csv"
            with zipfile.ZipFile(archive, "w") as zip_file:
                zip_file.writestr("source.csv", "id;uf\n1;TO\n")

            extract_single_csv(archive, destination)

            self.assertEqual(destination.read_text(), "id;uf\n1;TO\n")

    def test_lists_only_years_with_all_dataset_kinds(self) -> None:
        html = """
        <table>
          <tr><td>Documento CSV de acidentes 2025 agrupados por ocorrência</td>
              <td><a href="https://drive.google.com/a">Baixar planilha</a></td></tr>
          <tr><td>Documento CSV de acidentes 2025 agrupados por pessoa</td>
              <td><a href="https://drive.google.com/b">Baixar planilha</a></td></tr>
          <tr><td>Documento CSV de acidentes 2025 agrupados por pessoa -
                  todas as causas e tipos de acidentes</td>
              <td><a href="https://drive.google.com/c">Baixar planilha</a></td></tr>
          <tr><td>Documento CSV de acidentes 2024 agrupados por ocorrência</td>
              <td><a href="https://drive.google.com/d">Baixar planilha</a></td></tr>
        </table>
        """

        self.assertEqual(discover_available_years(html), [2025])

    def test_rejects_archive_with_multiple_csv_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "data.zip"
            with zipfile.ZipFile(archive, "w") as zip_file:
                zip_file.writestr("one.csv", "id\n1\n")
                zip_file.writestr("two.csv", "id\n2\n")

            with self.assertRaises(InvalidArchiveError):
                extract_single_csv(archive, root / "output.csv")


if __name__ == "__main__":
    unittest.main()
