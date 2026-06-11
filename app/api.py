from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel, Field

from app.config import DATA_ROOT
from app.data_import import DataImportManager, ImportAlreadyRunningError
from app.db import close_pool, fetch_all, fetch_one, open_pool
from prf_scraper import discover_available_years, fetch_source_page


REQUESTS = Counter(
    "prf_api_requests_total",
    "Total de requisicoes HTTP",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "prf_api_request_duration_seconds",
    "Duracao das requisicoes HTTP",
    ["method", "path"],
)
DATA_IMPORT = DataImportManager(Path(DATA_ROOT))


class DataImportRequest(BaseModel):
    anos: list[int] = Field(min_length=1)


@asynccontextmanager
async def lifespan(_: FastAPI):
    open_pool()
    yield
    close_pool()


app = FastAPI(
    title="API de acidentes da PRF",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.mount("/metrics", make_asgi_app())


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    started = perf_counter()
    response = await call_next(request)
    path = request.url.path
    REQUESTS.labels(request.method, path, response.status_code).inc()
    LATENCY.labels(request.method, path).observe(perf_counter() - started)
    response.headers["X-Response-Time"] = f"{perf_counter() - started:.6f}s"
    return response


@app.get("/health")
def health():
    result = fetch_one("SELECT 1 AS database")
    return {"status": "ok", **result}


@app.get("/api/resumo")
def resumo(ano: int | None = None):
    return fetch_one(
        """
        SELECT
            COUNT(*) AS acidentes,
            COALESCE(SUM(pessoas), 0) AS pessoas,
            COALESCE(SUM(feridos), 0) AS feridos,
            COALESCE(SUM(mortos), 0) AS mortos,
            MIN(data_inversa) AS primeira_data,
            MAX(data_inversa) AS ultima_data
        FROM ocorrencias
        WHERE (%s::smallint IS NULL OR ano_fonte = %s::smallint)
        """,
        (ano, ano),
    )


@app.get("/api/por-ano")
def por_ano():
    return fetch_all(
        """
        SELECT ano_fonte AS ano, COUNT(*) AS acidentes,
               SUM(feridos) AS feridos, SUM(mortos) AS mortos
        FROM ocorrencias
        GROUP BY ano_fonte
        ORDER BY ano_fonte
        """
    )


@app.get("/api/por-uf")
def por_uf(ano: int | None = None):
    return fetch_all(
        """
        SELECT uf, COUNT(*) AS acidentes, SUM(mortos) AS mortos
        FROM ocorrencias
        WHERE (%s::smallint IS NULL OR ano_fonte = %s::smallint)
        GROUP BY uf
        ORDER BY acidentes DESC
        """,
        (ano, ano),
    )


@app.get("/api/top-causas")
def top_causas(
    ano: int | None = None,
    limite: int = Query(15, ge=1, le=50),
):
    return fetch_all(
        """
        SELECT causa_acidente AS causa, COUNT(*) AS acidentes,
               SUM(mortos) AS mortos
        FROM ocorrencias
        WHERE (%s::smallint IS NULL OR ano_fonte = %s::smallint)
        GROUP BY causa_acidente
        ORDER BY acidentes DESC
        LIMIT %s
        """,
        (ano, ano, limite),
    )


@app.get("/api/serie-mensal")
def serie_mensal(ano: int | None = None, uf: str | None = None):
    return fetch_all(
        """
        SELECT DATE_TRUNC('month', data_inversa)::date AS mes,
               COUNT(*) AS acidentes, SUM(mortos) AS mortos
        FROM ocorrencias
        WHERE (%s::smallint IS NULL OR ano_fonte = %s::smallint)
          AND (%s::text IS NULL OR uf = %s::text)
        GROUP BY mes
        ORDER BY mes
        """,
        (ano, ano, uf, uf),
    )


@app.get("/api/condicoes")
def condicoes(ano: int | None = None):
    return fetch_all(
        """
        SELECT condicao_metereologica AS condicao,
               COUNT(*) AS acidentes,
               SUM(mortos) AS mortos,
               ROUND(AVG(mortos)::numeric, 4) AS media_mortos
        FROM ocorrencias
        WHERE (%s::smallint IS NULL OR ano_fonte = %s::smallint)
        GROUP BY condicao_metereologica
        ORDER BY acidentes DESC
        """,
        (ano, ano),
    )


@app.get("/api/perfil-vitimas")
def perfil_vitimas(ano: int | None = None):
    return fetch_all(
        """
        SELECT
            CASE
                WHEN idade < 18 THEN '0-17'
                WHEN idade < 30 THEN '18-29'
                WHEN idade < 45 THEN '30-44'
                WHEN idade < 60 THEN '45-59'
                WHEN idade >= 60 THEN '60+'
                ELSE 'Nao informado'
            END AS faixa_etaria,
            sexo,
            estado_fisico,
            COUNT(*) AS pessoas
        FROM pessoas
        WHERE (%s::smallint IS NULL OR ano_fonte = %s::smallint)
          AND pesid IS NOT NULL
          AND pesid <> 0
        GROUP BY faixa_etaria, sexo, estado_fisico
        ORDER BY pessoas DESC
        """,
        (ano, ano),
    )


@app.get("/api/cargas")
def cargas():
    return fetch_all(
        """
        SELECT ano_fonte, arquivo, tabela_destino, linhas, bytes,
               ROUND(duracao_segundos::numeric, 3) AS duracao_segundos,
               ROUND((linhas / NULLIF(duracao_segundos, 0))::numeric, 2)
                   AS linhas_por_segundo,
               carregado_em
        FROM cargas
        ORDER BY carregado_em DESC
        LIMIT 30
        """
    )


@app.get("/api/dados/anos")
def dados_anos():
    available = set(discover_available_years(fetch_source_page()))
    loaded = {
        int(item["ano"])
        for item in fetch_all(
            "SELECT DISTINCT ano_fonte AS ano FROM ocorrencias ORDER BY ano_fonte"
        )
    }
    return DATA_IMPORT.list_years(available, loaded)


@app.post("/api/dados/importar", status_code=status.HTTP_202_ACCEPTED)
def importar_dados(payload: DataImportRequest, tasks: BackgroundTasks):
    available = set(discover_available_years(fetch_source_page()))
    invalid = sorted(set(payload.anos) - available)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Anos indisponíveis: {', '.join(map(str, invalid))}",
        )
    try:
        result = DATA_IMPORT.start(payload.anos)
    except ImportAlreadyRunningError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    tasks.add_task(DATA_IMPORT.run)
    return result


@app.get("/api/dados/importacao")
def status_importacao():
    return DATA_IMPORT.status()
