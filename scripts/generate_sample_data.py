from __future__ import annotations

import argparse
import csv
import random
from datetime import date, time
from pathlib import Path

from app.loader import DATASETS


UFS = ["GO", "MG", "PR", "RJ", "RS", "SC", "SP", "TO"]
CAUSES = [
    "Ausencia de reacao do condutor",
    "Velocidade incompativel",
    "Ingestao de alcool",
    "Falha mecanica",
]


def occurrence(row_id: int, year: int) -> dict[str, object]:
    people = random.randint(1, 5)
    dead = random.choices([0, 1], weights=[98, 2])[0]
    injured = random.randint(dead, people)
    return {
        "id": row_id,
        "data_inversa": date(year, random.randint(1, 12), random.randint(1, 28)),
        "dia_semana": "segunda-feira",
        "horario": time(random.randint(0, 23), random.randint(0, 59)),
        "uf": random.choice(UFS),
        "br": random.randint(1, 500),
        "km": f"{random.uniform(0, 900):.1f}".replace(".", ","),
        "municipio": "Municipio de teste",
        "causa_acidente": random.choice(CAUSES),
        "tipo_acidente": "Colisao",
        "classificacao_acidente": "Com Vitimas Feridas",
        "fase_dia": "Pleno dia",
        "sentido_via": "Crescente",
        "condicao_metereologica": "Ceu Claro",
        "tipo_pista": "Simples",
        "tracado_via": "Reta",
        "uso_solo": "Nao",
        "pessoas": people,
        "mortos": dead,
        "feridos_leves": injured,
        "feridos_graves": 0,
        "ilesos": people - injured,
        "ignorados": 0,
        "feridos": injured,
        "veiculos": random.randint(1, 3),
        "latitude": "-10,1000",
        "longitude": "-48,3000",
        "regional": "Teste",
        "delegacia": "Teste",
        "uop": "Teste",
    }


def person(row_id: int, year: int) -> dict[str, object]:
    return {
        "id": row_id,
        "pesid": year * 1_000_000 + row_id,
        "id_veiculo": year * 1_000_000 + row_id,
        "data_inversa": date(year, 1, 1),
        "uf": random.choice(UFS),
        "municipio": "Municipio de teste",
        "tipo_veiculo": "Automovel",
        "ano_fabricacao_veiculo": random.randint(2000, year),
        "tipo_envolvido": "Condutor",
        "estado_fisico": "Ileso",
        "idade": random.randint(18, 80),
        "sexo": random.choice(["Masculino", "Feminino"]),
    }


def cause(row_id: int, year: int) -> dict[str, object]:
    return {
        "id": row_id,
        "pesid": year * 1_000_000 + row_id,
        "id_veiculo": year * 1_000_000 + row_id,
        "causa_principal": "Sim",
        "causa_acidente": random.choice(CAUSES),
        "ordem_tipo_acidente": 1,
        "tipo_acidente": "Colisao",
    }


GENERATORS = {
    "ocorrencias.csv": occurrence,
    "pessoas.csv": person,
    "pessoas_todas_causas.csv": cause,
}


def generate(output: Path, years: list[int], rows: int, seed: int) -> None:
    random.seed(seed)
    for year in years:
        year_dir = output / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        for filename, (_, columns) in DATASETS.items():
            with (year_dir / filename).open(
                "w",
                encoding="ISO-8859-1",
                newline="",
            ) as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=columns,
                    delimiter=";",
                )
                writer.writeheader()
                generator = GENERATORS[filename]
                for row_id in range(1, rows + 1):
                    writer.writerow(generator(row_id, year))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera CSVs pequenos compativeis com o loader"
    )
    parser.add_argument("--output", type=Path, default=Path("data"))
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025, 2026])
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.rows < 1:
        raise SystemExit("--rows deve ser pelo menos 1")
    generate(args.output, args.years, args.rows, args.seed)


if __name__ == "__main__":
    main()
