from __future__ import annotations

import argparse
import io
import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

import pandas as pd
import psycopg

from app.config import DATABASE_URL, DATA_ROOT, LOAD_CHUNK_SIZE, LOAD_WORKERS


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger(__name__)

DATASETS = {
    "ocorrencias.csv": (
        "ocorrencias",
        [
            "id",
            "data_inversa",
            "dia_semana",
            "horario",
            "uf",
            "br",
            "km",
            "municipio",
            "causa_acidente",
            "tipo_acidente",
            "classificacao_acidente",
            "fase_dia",
            "sentido_via",
            "condicao_metereologica",
            "tipo_pista",
            "tracado_via",
            "uso_solo",
            "pessoas",
            "mortos",
            "feridos_leves",
            "feridos_graves",
            "ilesos",
            "ignorados",
            "feridos",
            "veiculos",
            "latitude",
            "longitude",
            "regional",
            "delegacia",
            "uop",
        ],
    ),
    "pessoas.csv": (
        "pessoas",
        [
            "id",
            "pesid",
            "id_veiculo",
            "data_inversa",
            "uf",
            "municipio",
            "tipo_veiculo",
            "ano_fabricacao_veiculo",
            "tipo_envolvido",
            "estado_fisico",
            "idade",
            "sexo",
        ],
    ),
    "pessoas_todas_causas.csv": (
        "causas",
        [
            "id",
            "pesid",
            "id_veiculo",
            "causa_principal",
            "causa_acidente",
            "ordem_tipo_acidente",
            "tipo_acidente",
        ],
    ),
}

INTEGER_COLUMNS = {
    "id",
    "pesid",
    "id_veiculo",
    "pessoas",
    "mortos",
    "feridos_leves",
    "feridos_graves",
    "ilesos",
    "ignorados",
    "feridos",
    "veiculos",
    "idade",
    "ano_fabricacao_veiculo",
    "ordem_tipo_acidente",
}
FLOAT_COLUMNS = {"br", "km", "latitude", "longitude"}


@dataclass(frozen=True)
class FileLoadResult:
    year: int
    filename: str
    table: str
    rows: int
    bytes: int
    duration_seconds: float


@dataclass(frozen=True)
class LoadResult:
    workers: int
    years: list[int]
    rows: int
    bytes: int
    duration_seconds: float
    files: list[FileLoadResult]

    @property
    def rows_per_second(self) -> float:
        return self.rows / self.duration_seconds if self.duration_seconds else 0.0

    def to_dict(self) -> dict:
        result = asdict(self)
        result["rows_per_second"] = self.rows_per_second
        return result


def _clean_chunk(chunk: pd.DataFrame, year: int) -> pd.DataFrame:
    chunk = chunk.replace({"NA": None, "N/A": None, "": None})
    for column in chunk.columns.intersection(INTEGER_COLUMNS):
        chunk[column] = pd.to_numeric(chunk[column], errors="coerce").astype("Int64")
    for column in chunk.columns.intersection(FLOAT_COLUMNS):
        values = chunk[column].astype("string").str.replace(",", ".", regex=False)
        chunk[column] = pd.to_numeric(values, errors="coerce")
    if "data_inversa" in chunk:
        chunk["data_inversa"] = pd.to_datetime(
            chunk["data_inversa"], errors="coerce"
        ).dt.date
    chunk.insert(0, "ano_fonte", year)
    return chunk


def _copy_chunk(
    conn: psycopg.Connection,
    table: str,
    chunk: pd.DataFrame,
) -> None:
    buffer = io.StringIO()
    chunk.to_csv(buffer, index=False, header=False, na_rep="\\N")
    buffer.seek(0)
    columns = ", ".join(chunk.columns)
    with conn.cursor() as cursor:
        with cursor.copy(
            f"COPY {table} ({columns}) FROM STDIN "
            "WITH (FORMAT CSV, NULL '\\N')"
        ) as copy:
            while data := buffer.read(1024 * 1024):
                copy.write(data)


def load_file(
    conn: psycopg.Connection,
    path: Path,
    table: str,
    columns: list[str],
    year: int,
) -> int:
    rows = 0
    for chunk in pd.read_csv(
        path,
        sep=";",
        encoding="ISO-8859-1",
        usecols=columns,
        dtype=str,
        chunksize=LOAD_CHUNK_SIZE,
        keep_default_na=False,
    ):
        cleaned = _clean_chunk(chunk, year)
        _copy_chunk(conn, table, cleaned)
        rows += len(cleaned)
        LOGGER.info("%s: %s linhas carregadas", path.name, f"{rows:,}")
    return rows


def load_year(conn: psycopg.Connection, year_dir: Path) -> list[FileLoadResult]:
    year = int(year_dir.name)
    results: list[FileLoadResult] = []
    for filename, (table, columns) in DATASETS.items():
        path = year_dir / filename
        if not path.exists():
            LOGGER.warning("Arquivo ausente: %s", path)
            continue

        started = perf_counter()
        with conn.transaction():
            conn.execute(f"DELETE FROM {table} WHERE ano_fonte = %s", (year,))
            rows = load_file(conn, path, table, columns, year)
            duration = perf_counter() - started
            conn.execute(
                """
                INSERT INTO cargas
                    (ano_fonte, arquivo, tabela_destino, linhas, bytes, duracao_segundos)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (year, filename, table, rows, path.stat().st_size, duration),
            )
        results.append(
            FileLoadResult(
                year=year,
                filename=filename,
                table=table,
                rows=rows,
                bytes=path.stat().st_size,
                duration_seconds=duration,
            )
        )
        LOGGER.info(
            "%s concluido: %s linhas em %.2fs",
            filename,
            f"{rows:,}",
            duration,
        )
    return results


def _load_year_worker(year_dir: str) -> list[FileLoadResult]:
    with psycopg.connect(DATABASE_URL) as conn:
        return load_year(conn, Path(year_dir))


def discover_year_dirs(root: Path, years: set[int] | None = None) -> list[Path]:
    requested = years or set()
    return [
        path
        for path in sorted(root.iterdir())
        if path.is_dir()
        and path.name.isdigit()
        and (not requested or int(path.name) in requested)
    ]


def load_dataset(year_dirs: list[Path], workers: int = 1) -> LoadResult:
    if workers < 1:
        raise ValueError("A quantidade de workers deve ser pelo menos 1")
    if not year_dirs:
        raise ValueError("Nenhuma pasta anual foi informada")

    effective_workers = min(workers, len(year_dirs))
    started = perf_counter()
    files: list[FileLoadResult] = []

    if effective_workers == 1:
        with psycopg.connect(DATABASE_URL) as conn:
            for year_dir in year_dirs:
                files.extend(load_year(conn, year_dir))
    else:
        LOGGER.info(
            "Distribuindo %s anos entre %s workers",
            len(year_dirs),
            effective_workers,
        )
        with ProcessPoolExecutor(max_workers=effective_workers) as executor:
            futures = {
                executor.submit(_load_year_worker, str(year_dir)): year_dir
                for year_dir in year_dirs
            }
            for future in as_completed(futures):
                year_dir = futures[future]
                try:
                    files.extend(future.result())
                except Exception:
                    LOGGER.exception("Falha no worker responsável por %s", year_dir.name)
                    raise

    duration = perf_counter() - started
    files.sort(key=lambda item: (item.year, item.filename))
    return LoadResult(
        workers=effective_workers,
        years=[int(path.name) for path in year_dirs],
        rows=sum(item.rows for item in files),
        bytes=sum(item.bytes for item in files),
        duration_seconds=duration,
        files=files,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Carrega CSVs da PRF no PostgreSQL")
    parser.add_argument("years", nargs="*", type=int)
    parser.add_argument(
        "--workers",
        type=int,
        default=LOAD_WORKERS,
        help="Anos processados simultaneamente (padrao: %(default)s)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Exibe o resumo final em JSON",
    )
    args = parser.parse_args()

    root = Path(DATA_ROOT)
    year_dirs = discover_year_dirs(root, set(args.years))
    if not year_dirs:
        raise SystemExit(f"Nenhuma pasta anual encontrada em {root}")

    try:
        result = load_dataset(year_dirs, args.workers)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    LOGGER.info(
        "Carga concluida com %s worker(s): %s linhas em %.2fs (%.2f linhas/s)",
        result.workers,
        f"{result.rows:,}",
        result.duration_seconds,
        result.rows_per_second,
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=True))


if __name__ == "__main__":
    main()
