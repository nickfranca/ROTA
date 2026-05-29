from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from time import perf_counter

import pandas as pd


REQUIRED_COLUMNS = {
    "linha",
    "data",
    "horario_previsto",
    "horario_realizado",
    "passageiros",
    "status",
}


def load_csv(path: str) -> pd.DataFrame:
    data = pd.read_csv(path)
    missing_columns = REQUIRED_COLUMNS - set(data.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"CSV sem colunas obrigatorias: {missing}")

    return data


def clean_data(data: pd.DataFrame) -> pd.DataFrame:
    cleaned = data.copy()
    cleaned = cleaned.dropna(subset=["linha", "data", "horario_previsto", "horario_realizado"])
    cleaned["linha"] = cleaned["linha"].astype(str).str.strip().str.upper()
    cleaned["status_viagem"] = cleaned["status"].astype(str).str.strip().str.lower()
    cleaned["passageiros"] = pd.to_numeric(cleaned["passageiros"], errors="coerce").fillna(0).astype(int)
    cleaned = cleaned[cleaned["passageiros"] >= 0]

    cleaned["data_viagem"] = pd.to_datetime(cleaned["data"], errors="coerce")
    cleaned = cleaned.dropna(subset=["data_viagem"])

    cleaned["previsto_datetime"] = pd.to_datetime(
        cleaned["data_viagem"].dt.strftime("%Y-%m-%d") + " " + cleaned["horario_previsto"],
        errors="coerce",
    )
    cleaned["realizado_datetime"] = pd.to_datetime(
        cleaned["data_viagem"].dt.strftime("%Y-%m-%d") + " " + cleaned["horario_realizado"],
        errors="coerce",
    )
    cleaned = cleaned.dropna(subset=["previsto_datetime", "realizado_datetime"])

    atraso = (cleaned["realizado_datetime"] - cleaned["previsto_datetime"]).dt.total_seconds() / 60
    cleaned["atraso_minutos"] = atraso.clip(lower=0).round().astype(int)

    return cleaned[
        [
            "linha",
            "data_viagem",
            "horario_previsto",
            "horario_realizado",
            "passageiros",
            "status_viagem",
            "atraso_minutos",
        ]
    ].reset_index(drop=True)


def summarize(data: pd.DataFrame, modo_processamento: str, elapsed_seconds: float) -> pd.DataFrame:
    summary = (
        data.groupby("linha")
        .agg(
            total_viagens=("linha", "size"),
            total_passageiros=("passageiros", "sum"),
            media_atraso_minutos=("atraso_minutos", "mean"),
            viagens_atrasadas=("atraso_minutos", lambda values: (values > 0).sum()),
        )
        .reset_index()
    )
    summary["percentual_atrasadas"] = (
        summary["viagens_atrasadas"] / summary["total_viagens"] * 100
    ).round(2)
    summary["media_atraso_minutos"] = summary["media_atraso_minutos"].round(2)
    summary["modo_processamento"] = modo_processamento
    summary["tempo_execucao_segundos"] = round(elapsed_seconds, 4)

    return summary.drop(columns=["viagens_atrasadas"])


def process_sequential(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    start = perf_counter()
    cleaned = clean_data(data)
    elapsed = perf_counter() - start
    summary = summarize(cleaned, "sequencial", elapsed)
    return cleaned, summary, elapsed


def process_parallel(data: pd.DataFrame, workers: int = 4) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    workers = max(1, workers)
    chunks = split_dataframe(data, workers)

    start = perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        cleaned_chunks = list(executor.map(clean_data, chunks))

    cleaned = pd.concat(cleaned_chunks, ignore_index=True)
    elapsed = perf_counter() - start
    summary = summarize(cleaned, "paralelo", elapsed)
    return cleaned, summary, elapsed


def split_dataframe(data: pd.DataFrame, parts: int) -> list[pd.DataFrame]:
    if data.empty:
        return [data]

    chunk_size = max(1, len(data) // parts)
    chunks = [data.iloc[start : start + chunk_size].copy() for start in range(0, len(data), chunk_size)]
    return [chunk for chunk in chunks if not chunk.empty]
