from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException

import app.api as api
from app.data_import import DataImportManager


AVAILABLE_HTML = """
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


class DataImportApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = DataImportManager(Path("/data"))
        self.manager_patch = patch.object(api, "DATA_IMPORT", self.manager)
        self.manager_patch.start()

    def tearDown(self) -> None:
        self.manager_patch.stop()

    @patch.object(api, "fetch_all", return_value=[{"ano": 2025}])
    @patch.object(api, "fetch_source_page", return_value=AVAILABLE_HTML)
    def test_lists_available_and_loaded_years(self, _, __) -> None:
        self.assertEqual(
            api.dados_anos(),
            [{"ano": 2025, "carregado": True}],
        )

    @patch.object(api, "fetch_source_page", return_value=AVAILABLE_HTML)
    def test_starts_import_as_a_background_task(self, _) -> None:
        tasks = BackgroundTasks()

        result = api.importar_dados(
            api.DataImportRequest(anos=[2025]),
            tasks,
        )

        self.assertEqual(result["estado"], "baixando")
        self.assertEqual(len(tasks.tasks), 1)

    @patch.object(api, "fetch_source_page", return_value=AVAILABLE_HTML)
    def test_rejects_an_unavailable_year(self, _) -> None:
        with self.assertRaises(HTTPException) as raised:
            api.importar_dados(
                api.DataImportRequest(anos=[2024]),
                BackgroundTasks(),
            )

        self.assertEqual(raised.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
