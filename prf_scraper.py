from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unicodedata
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable

import requests


PRF_DATA_URL = (
    "https://www.gov.br/prf/pt-br/acesso-a-informacao/"
    "dados-abertos/dados-abertos-da-prf"
)
DATASET_FILENAMES = {
    "ocorrencias": "ocorrencias.csv",
    "pessoas": "pessoas.csv",
    "pessoas_todas_causas": "pessoas_todas_causas.csv",
}
REQUEST_TIMEOUT = (15, 60)
DatasetProgress = Callable[[int, str], None]
DownloadProgress = Callable[[int, str, int], None]


class ScraperError(RuntimeError):
    """Erro esperado durante descoberta, download ou extração."""


class DatasetDiscoveryError(ScraperError):
    """A página da PRF não contém todos os documentos solicitados."""


class DownloadError(ScraperError):
    """O download de um arquivo não foi concluído."""


class InvalidArchiveError(ScraperError):
    """O arquivo baixado não é um ZIP válido com exatamente um CSV."""


class _TableRowParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[str, list[tuple[str, str]]]] = []
        self._in_row = False
        self._row_text: list[str] = []
        self._links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_link_text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag == "tr":
            self._in_row = True
            self._row_text = []
            self._links = []
        elif tag == "a" and self._in_row:
            self._current_href = dict(attrs).get("href")
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        if not self._in_row:
            return
        self._row_text.append(data)
        if self._current_href is not None:
            self._current_link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href is not None:
            self._links.append(
                (self._current_href, " ".join(self._current_link_text))
            )
            self._current_href = None
            self._current_link_text = []
        elif tag == "tr" and self._in_row:
            row_text = " ".join(" ".join(self._row_text).split())
            self.rows.append((row_text, self._links.copy()))
            self._in_row = False


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().split())


def _dataset_kind(row_text: str, year: int) -> str | None:
    normalized = _normalize(row_text)
    if f"documento csv de acidentes {year}" not in normalized:
        return None
    if "agrupados por pessoa - todas as causas e tipos de acidentes" in normalized:
        return "pessoas_todas_causas"
    if "agrupados por ocorrencia" in normalized:
        return "ocorrencias"
    if "agrupados por pessoa" in normalized:
        return "pessoas"
    return None


def _preferred_download_link(links: list[tuple[str, str]]) -> str | None:
    drive_links = [
        (href, text)
        for href, text in links
        if "drive.google.com" in href
    ]
    for href, text in drive_links:
        if "baixar planilha" in _normalize(text):
            return href
    return drive_links[0][0] if drive_links else None


def discover_datasets(html: str, year: int) -> dict[str, str]:
    parser = _TableRowParser()
    parser.feed(html)

    datasets: dict[str, str] = {}
    for row_text, links in parser.rows:
        kind = _dataset_kind(row_text, year)
        link = _preferred_download_link(links)
        if kind and link:
            datasets[kind] = link

    missing = set(DATASET_FILENAMES) - set(datasets)
    if missing:
        missing_names = ", ".join(sorted(missing))
        raise DatasetDiscoveryError(
            f"Ano {year}: documentos não encontrados: {missing_names}"
        )
    return datasets


def discover_available_years(html: str) -> list[int]:
    parser = _TableRowParser()
    parser.feed(html)
    datasets_by_year: dict[int, set[str]] = {}
    for row_text, links in parser.rows:
        match = re.search(r"documento csv de acidentes\s+(\d{4})", _normalize(row_text))
        if not match or not _preferred_download_link(links):
            continue
        year = int(match.group(1))
        kind = _dataset_kind(row_text, year)
        if kind:
            datasets_by_year.setdefault(year, set()).add(kind)
    return sorted(
        year
        for year, kinds in datasets_by_year.items()
        if kinds == set(DATASET_FILENAMES)
    )


def fetch_source_page(url: str = PRF_DATA_URL) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": "PRF-data-downloader/1.0"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.text


def download_drive_file(url: str, destination: Path) -> Path:
    try:
        import gdown
    except ImportError as error:
        raise DownloadError(
            "A dependência gdown não está instalada. "
            "Execute: pip install -r requirements.txt"
        ) from error

    destination.parent.mkdir(parents=True, exist_ok=True)
    result = gdown.download(
        url=url,
        output=str(destination),
        fuzzy=True,
        quiet=False,
    )
    if result is None or not destination.is_file():
        raise DownloadError(f"Não foi possível baixar {url}")
    return destination


def extract_single_csv(archive: Path, destination: Path) -> Path:
    try:
        with zipfile.ZipFile(archive) as zip_file:
            csv_members = [
                member
                for member in zip_file.infolist()
                if not member.is_dir() and member.filename.lower().endswith(".csv")
            ]
            if len(csv_members) != 1:
                raise InvalidArchiveError(
                    f"{archive.name} deve conter exatamente um CSV; "
                    f"foram encontrados {len(csv_members)}"
                )

            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".part")
            try:
                with zip_file.open(csv_members[0]) as source, temporary.open(
                    "wb"
                ) as output:
                    shutil.copyfileobj(source, output)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
    except zipfile.BadZipFile as error:
        raise InvalidArchiveError(f"{archive.name} não é um ZIP válido") from error

    return destination


def download_year(
    year: int,
    datasets: dict[str, str],
    output_root: Path,
    progress: DatasetProgress | None = None,
) -> list[Path]:
    year_directory = output_root / str(year)
    year_directory.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    with tempfile.TemporaryDirectory(prefix=f"prf-{year}-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        for kind, filename in DATASET_FILENAMES.items():
            print(f"[{year}] Baixando {kind}...")
            archive = temporary_root / f"{kind}.zip"
            download_drive_file(datasets[kind], archive)
            destination = year_directory / filename
            extract_single_csv(archive, destination)
            extracted.append(destination)
            if progress:
                progress(year, kind)
            print(f"[{year}] Salvo em {destination}")

    return extracted


def run(
    years: Iterable[int],
    output_root: Path | None = None,
    progress: DownloadProgress | None = None,
) -> list[Path]:
    html = fetch_source_page()
    downloaded: list[Path] = []
    destination = output_root or Path(__file__).resolve().parent / "data"
    completed = 0

    def report_progress(year: int, kind: str) -> None:
        nonlocal completed
        completed += 1
        if progress:
            progress(year, kind, completed)

    for year in years:
        datasets = discover_datasets(html, year)
        downloaded.extend(
            download_year(
                year,
                datasets,
                destination,
                progress=report_progress,
            )
        )
    return downloaded


def main() -> int:
    arguments = sys.argv[1:]
    if not arguments:
        raise SystemExit("Uso: python prf_scraper.py ANO [ANO ...]")

    invalid_years = [value for value in arguments if not re.fullmatch(r"\d{4}", value)]
    if invalid_years:
        raise SystemExit(f"Anos inválidos: {', '.join(invalid_years)}")

    years = [int(value) for value in arguments]

    try:
        run(years)
    except (requests.RequestException, ScraperError) as error:
        raise SystemExit(f"Erro: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
