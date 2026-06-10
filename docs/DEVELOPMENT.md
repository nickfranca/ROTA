# Guia de desenvolvimento

Este documento explica a arquitetura do ROTA, a responsabilidade de cada
arquivo e o procedimento recomendado para desenvolver, testar e manter a
aplicação.

## 1. Estrutura do projeto

```text
.
├── app/
│   ├── api.py             # API FastAPI e métricas HTTP
│   ├── config.py          # Variáveis de ambiente
│   ├── dashboard.py       # Dashboard complementar Streamlit
│   ├── db.py              # Pool de conexões PostgreSQL
│   └── loader.py          # ETL e carga dos CSVs
├── data/
│   └── ANO/*.csv          # Dados brutos, ignorados pelo Git
├── db/
│   └── init.sql           # Tabelas e índices
├── docs/
│   └── DEVELOPMENT.md     # Este documento
├── frontend/
│   ├── app.js             # Integração com a API e gráficos SVG
│   ├── index.html         # Estrutura da página inicial
│   ├── nginx.conf         # Arquivos estáticos e proxy /api
│   └── styles.css         # Identidade visual responsiva
├── monitoring/
│   ├── grafana/           # Provisionamento do datasource e dashboard
│   └── prometheus.yml     # Alvos coletados pelo Prometheus
├── requirements/
│   ├── api.txt
│   ├── dashboard.txt
│   ├── etl.txt
│   └── scraper.txt
├── docker-compose.yml
├── Dockerfile
├── prf_scraper.py
└── requirements.txt       # Agregador das dependências Python
```

## 2. Fluxo completo

### 2.1 Coleta

`prf_scraper.py`:

1. acessa a página de dados abertos da PRF;
2. analisa as linhas da tabela HTML;
3. encontra os links dos arquivos de cada ano;
4. baixa os arquivos ZIP por meio do `gdown`;
5. valida que cada ZIP possui exatamente um CSV;
6. extrai o CSV para `data/<ano>/`.

O scraper mantém três arquivos por ano:

- `ocorrencias.csv`;
- `pessoas.csv`;
- `pessoas_todas_causas.csv`.

### 2.2 ETL e carga

`app/loader.py` é responsável pela importação.

O Pandas lê os arquivos com:

```python
pd.read_csv(
    path,
    sep=";",
    encoding="ISO-8859-1",
    chunksize=LOAD_CHUNK_SIZE,
)
```

O uso de blocos evita colocar centenas de megabytes simultaneamente na
memória.

Para cada bloco, `_clean_chunk()`:

- converte `NA`, `N/A` e strings vazias para nulo;
- converte identificadores e contagens para inteiros;
- converte coordenadas, BR e quilômetro para números;
- converte `data_inversa` para data;
- adiciona `ano_fonte`.

`_copy_chunk()` utiliza o comando `COPY` do PostgreSQL. Ele é mais eficiente
que executar um `INSERT` individual para cada linha.

Antes de importar um arquivo, o loader remove os registros existentes daquele
ano na tabela de destino. A operação ocorre dentro de uma transação:

```text
DELETE do ano -> COPY dos novos registros -> registro em cargas -> COMMIT
```

Se a carga falhar, a transação é desfeita.

### 2.3 Banco de dados

`db/init.sql` é executado automaticamente quando o volume do PostgreSQL é
criado pela primeira vez.

Relacionamento simplificado:

```text
ocorrencias (ano_fonte, id)
        |
        +---- pessoas (ano_fonte, id)
        |
        +---- causas  (ano_fonte, id)
```

Cuidados importantes:

- `ocorrencias` tem uma linha por acidente;
- `pessoas` pode ter várias linhas para o mesmo acidente;
- `causas` pode repetir pessoa, veículo, causa e tipo;
- para contar acidentes após um `JOIN`, use `COUNT(DISTINCT id)`;
- não some mortos ou feridos depois de um `JOIN` sem reduzir para uma linha
  por ocorrência.

### 2.4 API

`app/api.py` contém as rotas FastAPI.

`app/db.py` mantém um pool de conexões:

```text
mínimo: 1 conexão
máximo: 10 conexões
```

Principais endpoints:

| Endpoint | Finalidade |
| --- | --- |
| `GET /health` | Verifica API e banco |
| `GET /api/resumo` | Indicadores consolidados |
| `GET /api/por-ano` | Comparação anual |
| `GET /api/por-uf` | Acidentes e mortes por UF |
| `GET /api/top-causas` | Causas mais frequentes |
| `GET /api/serie-mensal` | Evolução mensal |
| `GET /api/condicoes` | Condições meteorológicas |
| `GET /api/perfil-vitimas` | Faixa etária, sexo e estado físico |
| `GET /api/cargas` | Histórico e velocidade das importações |

Os filtros opcionais usam parâmetros SQL:

```text
/api/resumo?ano=2025
/api/serie-mensal?ano=2025&uf=TO
/api/top-causas?ano=2025&limite=10
```

Não monte SQL concatenando valores recebidos pela URL.

### 2.5 Frontend principal

O frontend é uma aplicação estática servida pelo Nginx.

Responsabilidades:

- `index.html`: conteúdo e estrutura semântica;
- `styles.css`: layout, identidade visual e responsividade;
- `app.js`: chamadas HTTP, filtros e renderização dos gráficos;
- `nginx.conf`: serve os arquivos e encaminha `/api/*` para o FastAPI.

O navegador chama:

```text
GET http://localhost:3001/api/resumo
```

O Nginx encaminha internamente para:

```text
http://api:8000/api/resumo
```

Isso evita depender de CORS ou de um endereço fixo da API no JavaScript.

Os gráficos da página principal são SVGs produzidos pelo próprio `app.js`.
Não há biblioteca JavaScript externa nem CDN.

### 2.6 Dashboard Streamlit

`app/dashboard.py` oferece análises complementares com Pandas e Plotly.

Ele não acessa o PostgreSQL diretamente. Assim como o frontend principal,
consulta a API:

```text
Streamlit -> FastAPI -> PostgreSQL
```

O cache do Streamlit possui TTL de 60 segundos.

### 2.7 Observabilidade

A API registra:

- total de requisições;
- status HTTP;
- duração por rota;
- histograma de latência;
- cabeçalho `X-Response-Time`.

Prometheus coleta:

| Job | Origem |
| --- | --- |
| `prf-api` | `/metrics` da API |
| `postgres` | PostgreSQL exporter |
| `containers` | cAdvisor |

Grafana usa o Prometheus como datasource e provisiona automaticamente o
dashboard de desempenho.

## 3. Containers

| Serviço | Responsabilidade | Porta |
| --- | --- | --- |
| `frontend` | Página inicial e proxy da API | `3001` |
| `api` | API e métricas HTTP | `8000` |
| `dashboard` | Análises em Streamlit | `8501` |
| `db` | PostgreSQL | `5432` |
| `prometheus` | Séries temporais | `9090` |
| `grafana` | Visualização das métricas | `3000` |
| `cadvisor` | Recursos dos containers | `8080` |
| `postgres-exporter` | Métricas do banco | apenas interno |
| `loader` | Processo de importação | perfil `load` |
| `scraper` | Processo de download | perfil `scrape` |

`loader` e `scraper` são tarefas, não serviços permanentes. Por isso ficam em
profiles e encerram depois da execução.

## 4. Variáveis de ambiente

| Variável | Padrão | Uso |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL local | API e loader |
| `API_URL` | `http://localhost:8000` | Streamlit |
| `DATA_ROOT` | `/data` | Diretório lido pelo loader |
| `LOAD_CHUNK_SIZE` | `25000` | Linhas por bloco |

No Compose, os nomes dos serviços funcionam como DNS:

```text
db:5432
api:8000
prometheus:9090
```

`localhost` dentro de um container aponta para o próprio container, não para
a máquina ou para outro serviço.

## 5. Dependências Python

Para instalar tudo:

```bash
pip install -r requirements.txt
```

Para trabalhar apenas na API:

```bash
pip install -r requirements/api.txt
```

Para scraper, loader ou dashboard:

```bash
pip install -r requirements/scraper.txt
pip install -r requirements/etl.txt
pip install -r requirements/dashboard.txt
```

Ao adicionar uma dependência:

1. coloque-a no arquivo do componente correto;
2. use uma versão fixa para componentes centrais;
3. use intervalo quando atualizações compatíveis forem aceitáveis;
4. confirme que `requirements.txt` continua instalando o conjunto completo;
5. reconstrua as imagens.

## 6. Rotina de desenvolvimento

### Alterar a API ou código Python

```bash
docker compose build api dashboard
docker compose up -d --force-recreate api dashboard
```

### Alterar o frontend

```bash
docker compose build frontend
docker compose up -d --force-recreate frontend
```

Depois, recarregue `http://localhost:3001` com `Ctrl+Shift+R`.

### Alterar o esquema do banco

`db/init.sql` só é executado na criação inicial do volume.

Em ambiente de desenvolvimento, para recriar:

```bash
docker compose down -v
docker compose up -d db
docker compose --profile load run --rm loader
```

Esse procedimento apaga o banco atual.

Para um ambiente que precise preservar dados, crie uma migração SQL em vez de
apagar o volume.

## 7. Validações

Validar sintaxe Python:

```bash
python3 -m compileall -q app prf_scraper.py
```

Validar JavaScript:

```bash
node --check frontend/app.js
```

Validar o Compose:

```bash
docker compose config --quiet
```

Validar espaços e conflitos no diff:

```bash
git diff --check
```

Verificar saúde dos serviços:

```bash
docker compose ps
```

Testar a API:

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/api/resumo?ano=2025"
```

## 8. Convenções

- mantenha consultas SQL parametrizadas;
- preserve `ano_fonte` nas tabelas importadas;
- não versione os CSVs de `data/`;
- não coloque credenciais reais no repositório;
- mantenha o frontend consumindo a API, nunca o banco;
- documente novas rotas e variáveis;
- prefira mudanças pequenas e verificáveis;
- considere que correlação não significa causalidade.

## 9. Problemas comuns

### A página abre, mas não mostra dados

Verifique:

```bash
docker compose ps
docker compose logs api
docker compose logs frontend
```

Confirme que o loader foi executado.

### `ModuleNotFoundError: No module named 'app'`

A imagem Python define:

```text
PYTHONPATH=/app
```

Reconstrua o serviço:

```bash
docker compose build dashboard
docker compose up -d --force-recreate dashboard
```

### Alterei `init.sql`, mas nada mudou

O volume do PostgreSQL já existia. Recrie o volume ou aplique a alteração
manualmente.

### Porta ocupada

Altere apenas o lado esquerdo do mapeamento:

```yaml
ports:
  - "3002:80"
```

### cAdvisor sem nomes dos containers no WSL2

É uma limitação comum do Docker Desktop com WSL2. As métricas da API e do
PostgreSQL continuam disponíveis.
