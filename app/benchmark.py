from __future__ import annotations

import argparse
import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

from app.config import DATA_ROOT
from app.loader import discover_year_dirs, load_dataset


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkRun:
    workers: int
    repetition: int
    years: str
    rows: int
    bytes: int
    duration_seconds: float
    rows_per_second: float
    execution_order: int = 0


def run_benchmark(
    worker_counts: list[int],
    repetitions: int,
    years: set[int],
) -> list[BenchmarkRun]:
    year_dirs = discover_year_dirs(Path(DATA_ROOT), years)
    if not year_dirs:
        raise ValueError(f"Nenhuma pasta anual encontrada em {DATA_ROOT}")
    if repetitions < 1:
        raise ValueError("A quantidade de repeticoes deve ser pelo menos 1")

    runs: list[BenchmarkRun] = []
    year_label = ",".join(path.name for path in year_dirs)
    for repetition in range(1, repetitions + 1):
        offset = (repetition - 1) % len(worker_counts)
        ordered_workers = worker_counts[offset:] + worker_counts[:offset]
        for execution_order, workers in enumerate(ordered_workers, start=1):
            LOGGER.info(
                "Benchmark: repeticao %s/%s, ordem %s com %s worker(s)",
                repetition,
                repetitions,
                execution_order,
                workers,
            )
            result = load_dataset(year_dirs, workers)
            runs.append(
                BenchmarkRun(
                    workers=result.workers,
                    repetition=repetition,
                    years=year_label,
                    rows=result.rows,
                    bytes=result.bytes,
                    duration_seconds=result.duration_seconds,
                    rows_per_second=result.rows_per_second,
                    execution_order=execution_order,
                )
            )
    return runs


def summarize(runs: list[BenchmarkRun]) -> list[dict]:
    grouped: dict[int, list[BenchmarkRun]] = {}
    for run in runs:
        grouped.setdefault(run.workers, []).append(run)

    baseline_workers = min(grouped)
    baseline_duration = mean(run.duration_seconds for run in grouped[baseline_workers])
    summary = []
    for workers in sorted(grouped):
        samples = grouped[workers]
        average_duration = mean(run.duration_seconds for run in samples)
        speedup = baseline_duration / average_duration
        summary.append(
            {
                "workers": workers,
                "repetitions": len(samples),
                "average_seconds": average_duration,
                "standard_deviation_seconds": (
                    stdev(run.duration_seconds for run in samples)
                    if len(samples) > 1
                    else 0.0
                ),
                "average_rows_per_second": mean(
                    run.rows_per_second for run in samples
                ),
                "speedup": speedup,
                "efficiency": speedup / workers,
            }
        )
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    path: Path,
    runs: list[BenchmarkRun],
    summary: list[dict],
) -> None:
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    first = runs[0]
    lines = [
        "# Resultado do benchmark",
        "",
        f"- Gerado em: `{generated_at}`",
        f"- Anos processados: `{first.years}`",
        f"- Linhas processadas por execucao: `{first.rows}`",
        f"- Volume lido por execucao: `{first.bytes}` bytes",
        f"- Repeticoes por configuracao: `{max(run.repetition for run in runs)}`",
        "- Ordem rotativa entre repeticoes para reduzir o efeito de cache",
        "",
        "| Workers | Tempo medio (s) | Desvio (s) | Linhas/s | Speedup | Eficiencia |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summary:
        lines.append(
            "| {workers} | {average_seconds:.3f} | "
            "{standard_deviation_seconds:.3f} | "
            "{average_rows_per_second:.2f} | {speedup:.3f} | "
            "{efficiency:.2%} |".format(**item)
        )

    best = min(summary, key=lambda item: item["average_seconds"])
    lines.extend(
        [
            "",
            "## Analise",
            "",
            (
                f"A melhor media foi obtida com **{best['workers']} worker(s)**, "
                f"com speedup de **{best['speedup']:.3f}** em relacao a "
                f"{min(item['workers'] for item in summary)} worker."
            ),
            "",
            (
                "A eficiencia abaixo de 100% e esperada porque os workers disputam "
                "CPU, leitura de disco, escrita nos indices e recursos do PostgreSQL. "
                "Por isso, aumentar workers pode deixar de produzir ganho linear."
            ),
            "",
            "Os arquivos `runs.csv` e `summary.csv` preservam os dados brutos e "
            "as medias usadas nesta tabela.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara a carga sequencial e a carga com multiplos workers"
    )
    parser.add_argument("years", nargs="*", type=int)
    parser.add_argument(
        "--workers",
        nargs="+",
        type=int,
        default=[1, 2, 3],
        help="Quantidades de workers avaliadas",
    )
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("/results"))
    args = parser.parse_args()
    logging.getLogger("app.loader").setLevel(logging.WARNING)

    worker_counts = sorted(set(args.workers))
    if any(workers < 1 for workers in worker_counts):
        raise SystemExit("A quantidade de workers deve ser pelo menos 1")

    try:
        runs = run_benchmark(worker_counts, args.repetitions, set(args.years))
    except ValueError as error:
        raise SystemExit(str(error)) from error

    run_rows = [
        {
            "workers": run.workers,
            "repetition": run.repetition,
            "execution_order": run.execution_order,
            "years": run.years,
            "rows": run.rows,
            "bytes": run.bytes,
            "duration_seconds": f"{run.duration_seconds:.6f}",
            "rows_per_second": f"{run.rows_per_second:.2f}",
        }
        for run in runs
    ]
    summary = summarize(runs)
    write_csv(args.output / "runs.csv", run_rows)
    write_csv(args.output / "summary.csv", summary)
    write_report(args.output / "RESULTS.md", runs, summary)
    LOGGER.info("Resultados gravados em %s", args.output)


if __name__ == "__main__":
    main()
