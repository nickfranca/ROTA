from __future__ import annotations

from typing import Iterable

import mysql.connector
import pandas as pd

from app.config import DatabaseConfig


def get_connection(config: DatabaseConfig):
    return mysql.connector.connect(
        host=config.host,
        port=config.port,
        database=config.database,
        user=config.user,
        password=config.password,
    )


def save_viagens(config: DatabaseConfig, viagens: pd.DataFrame) -> None:
    if not config.enabled:
        return

    rows = [
        (
            row.linha,
            row.data_viagem.date().isoformat(),
            row.horario_previsto,
            row.horario_realizado,
            int(row.passageiros),
            row.status_viagem,
            int(row.atraso_minutos),
        )
        for row in viagens.itertuples(index=False)
    ]

    sql = """
        INSERT INTO viagens_tratadas
        (linha, data_viagem, horario_previsto, horario_realizado, passageiros, status_viagem, atraso_minutos)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    execute_many(config, sql, rows)


def save_estatisticas(config: DatabaseConfig, estatisticas: pd.DataFrame) -> None:
    if not config.enabled:
        return

    rows = [
        (
            row.linha,
            int(row.total_viagens),
            int(row.total_passageiros),
            float(row.media_atraso_minutos),
            float(row.percentual_atrasadas),
            row.modo_processamento,
            float(row.tempo_execucao_segundos),
        )
        for row in estatisticas.itertuples(index=False)
    ]

    sql = """
        INSERT INTO estatisticas_linha
        (linha, total_viagens, total_passageiros, media_atraso_minutos,
         percentual_atrasadas, modo_processamento, tempo_execucao_segundos)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    execute_many(config, sql, rows)


def execute_many(config: DatabaseConfig, sql: str, rows: Iterable[tuple]) -> None:
    connection = get_connection(config)
    try:
        cursor = connection.cursor()
        cursor.executemany(sql, list(rows))
        connection.commit()
    finally:
        cursor.close()
        connection.close()
