from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from app.config import DatabaseConfig
from app.db import save_estatisticas, save_viagens
from app.etl import load_csv, process_parallel, process_sequential


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline ETL de mobilidade urbana.")
    parser.add_argument("--input", required=True, help="Caminho do arquivo CSV de entrada.")
    parser.add_argument("--output-dir", default="data/output", help="Diretorio de saida dos arquivos tratados.")
    parser.add_argument("--workers", type=int, default=4, help="Quantidade de processos no modo paralelo.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_data = load_csv(args.input)

    viagens_sequencial, stats_sequencial, sequential_time = process_sequential(raw_data)
    viagens_paralelo, stats_paralelo, parallel_time = process_parallel(raw_data, workers=args.workers)
    stats = pd.concat([stats_sequencial, stats_paralelo], ignore_index=True)

    viagens_paralelo.to_csv(output_dir / "viagens_tratadas.csv", index=False)
    stats.to_csv(output_dir / "estatisticas_linha.csv", index=False)

    db_config = DatabaseConfig()
    save_viagens(db_config, viagens_paralelo)
    save_estatisticas(db_config, stats)

    print("ETL finalizado")
    print(f"Registros lidos: {len(raw_data)}")
    print(f"Registros validos: {len(viagens_paralelo)}")
    print(f"Tempo sequencial: {sequential_time:.4f}s")
    print(f"Tempo paralelo: {parallel_time:.4f}s")
    print(f"Arquivos gerados em: {output_dir}")


if __name__ == "__main__":
    main()
