from __future__ import annotations

import argparse
import io
import logging
from pathlib import Path
from time import perf_counter

import pandas as pd
import psycopg

from app.config import DATABASE_URL, DATA_ROOT, LOAD_CHUNK_SIZE


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


def load_year(conn: psycopg.Connection, year_dir: Path) -> None:
    year = int(year_dir.name)
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
        LOGGER.info(
            "%s concluido: %s linhas em %.2fs",
            filename,
            f"{rows:,}",
            duration,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Carrega CSVs da PRF no PostgreSQL")
    parser.add_argument("years", nargs="*", type=int)
    args = parser.parse_args()

    root = Path(DATA_ROOT)
    requested = set(args.years)
    year_dirs = [
        path
        for path in sorted(root.iterdir())
        if path.is_dir()
        and path.name.isdigit()
        and (not requested or int(path.name) in requested)
    ]
    if not year_dirs:
        raise SystemExit(f"Nenhuma pasta anual encontrada em {root}")

    with psycopg.connect(DATABASE_URL) as conn:
        for year_dir in year_dirs:
            load_year(conn, year_dir)


if __name__ == "__main__":
    main()
