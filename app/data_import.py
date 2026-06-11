from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Callable

from app.loader import load_dataset
from prf_scraper import run as download_years


DownloadFunction = Callable[[list[int], Path], object]
LoadFunction = Callable[[list[Path]], object]


class ImportAlreadyRunningError(RuntimeError):
    """Uma importação já está em andamento."""


class DataImportManager:
    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root
        self._lock = Lock()
        self._status = {
            "estado": "ocioso",
            "anos": [],
            "etapa": None,
            "mensagem": "Nenhuma importação em andamento.",
            "erro": None,
        }

    @staticmethod
    def list_years(
        available_years: set[int],
        loaded_years: set[int],
    ) -> list[dict]:
        return [
            {"ano": year, "carregado": year in loaded_years}
            for year in sorted(available_years)
        ]

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def start(self, years: list[int]) -> dict:
        selected = sorted(set(years))
        with self._lock:
            if self._status["estado"] in {"baixando", "carregando"}:
                raise ImportAlreadyRunningError(
                    "Já existe uma importação em andamento."
                )
            self._status = {
                "estado": "baixando",
                "anos": selected,
                "etapa": "download",
                "mensagem": "Baixando os arquivos selecionados.",
                "erro": None,
            }
            return dict(self._status)

    def _update(self, **changes: object) -> None:
        with self._lock:
            self._status.update(changes)

    def run(
        self,
        download: DownloadFunction = download_years,
        load: LoadFunction | None = None,
    ) -> None:
        years = list(self.status()["anos"])
        load_selected = load or (
            lambda paths: load_dataset(paths, workers=1)
        )
        try:
            download(years, self.data_root)
            self._update(
                estado="carregando",
                etapa="carga",
                mensagem="Carregando os dados no PostgreSQL.",
            )
            year_dirs = [self.data_root / str(year) for year in years]
            load_selected(year_dirs)
            self._update(
                estado="concluido",
                etapa=None,
                mensagem="Download e carga concluídos.",
            )
        except Exception as error:
            self._update(
                estado="erro",
                etapa=None,
                mensagem="A importação não foi concluída.",
                erro=str(error),
            )
